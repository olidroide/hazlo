from __future__ import annotations

from typing import TYPE_CHECKING

from hazlo.application.services import ReviewEngine

if TYPE_CHECKING:
    from pydantic_ai.models import Model
    from sqlalchemy.ext.asyncio import AsyncSession

    from hazlo.infrastructure.llm.agents import (
        DateParserAgent,
        LocationEnrichmentAgent,
        QualityClassifierAgent,
    )


async def build_pydantic_model(provider, api_key: str) -> Model | None:
    """Create a pydantic-ai model from an LLMProviderModel and decrypted key."""
    from pydantic_ai.models.google import GoogleModel, GoogleModelSettings
    from pydantic_ai.models.openrouter import OpenRouterModel
    from pydantic_ai.providers.google import GoogleProvider
    from pydantic_ai.providers.openrouter import OpenRouterProvider

    match provider.provider_type:
        case "gemini":
            return GoogleModel(
                provider.model,
                provider=GoogleProvider(api_key=api_key),
                settings=GoogleModelSettings(temperature=0.0, max_tokens=500),
            )
        case "openrouter":
            return OpenRouterModel(provider.model, provider=OpenRouterProvider(api_key=api_key))
        case "groq":
            from pydantic_ai.models.groq import GroqModel
            from pydantic_ai.providers.groq import GroqProvider

            return GroqModel(provider.model, provider=GroqProvider(api_key=api_key))
    return None


def _supports_tool_calling(provider_type: str, model: str) -> bool:
    """Check if a model supports tool calling (for structured output)."""
    # Models known to NOT support tool calling
    no_tools = {
        ("groq", "groq/compound-mini"),
    }
    return (provider_type, model) not in no_tools


async def build_llm_infrastructure(
    session: AsyncSession,
) -> tuple[QualityClassifierAgent | None, ReviewEngine, LocationEnrichmentAgent | None, DateParserAgent | None]:
    """Build QualityClassifierAgent + ReviewEngine + LocationEnrichmentAgent + DateParserAgent.

    Returns (None, ReviewEngine, None, None) if no active LLM provider is configured.

    Strategy: Use active provider first, then cascade through ALL other providers
    (sorted by priority) as fallbacks. This maximizes availability and handles rate limits gracefully.
    """
    import logging

    from pydantic_ai.models.fallback import FallbackModel
    from sqlalchemy import select

    from hazlo.infrastructure.crypto import decrypt_value
    from hazlo.infrastructure.db.models import LLMProviderModel
    from hazlo.infrastructure.llm.agents import (
        DateParserAgent,
        LocationEnrichmentAgent,
        QualityClassifierAgent,
    )
    from hazlo.settings import get_settings

    logger = logging.getLogger(__name__)
    settings = get_settings()

    # Fetch all active providers, sorted by priority
    result = await session.execute(
        select(LLMProviderModel)
        .where(LLMProviderModel.is_active)
        .order_by(LLMProviderModel.priority)
    )
    active_providers = list(result.scalars().all())

    if not active_providers:
        logger.warning("No active LLM provider configured")
        return (
            None,
            ReviewEngine(auto_approve_threshold=settings.auto_approve_threshold),
            None,
            None,
        )

    if not settings.hazlo_secret_key:
        logger.warning("No HAZLO_SECRET_KEY set, cannot decrypt provider credentials")
        return (
            None,
            ReviewEngine(auto_approve_threshold=settings.auto_approve_threshold),
            None,
            None,
        )

    models = []

    # Primary model (first active provider by priority)
    primary_provider = active_providers[0]
    api_key = decrypt_value(primary_provider.api_key_encrypted, settings.hazlo_secret_key)
    model = await build_pydantic_model(primary_provider, api_key)
    if model:
        logger.info("Loaded primary LLM: %s (%s)", primary_provider.model, primary_provider.provider_type)
        models.append((model, primary_provider.model, True))  # (model, name, supports_tools)

    # Fallback models: remaining active providers sorted by tool support
    # Prioritize models that support tool calling (for structured output)
    fallback_providers = active_providers[1:] if len(active_providers) > 1 else []

    # Sort: tool-supporting first, then by priority
    fallback_providers_sorted = sorted(
        fallback_providers,
        key=lambda p: (not _supports_tool_calling(p.provider_type, p.model), p.priority),
    )

    for fp in fallback_providers_sorted:
        fp_api_key = decrypt_value(fp.api_key_encrypted, settings.hazlo_secret_key)
        fp_model = await build_pydantic_model(fp, fp_api_key)
        if fp_model:
            supports_tools = _supports_tool_calling(fp.provider_type, fp.model)
            logger.info(
                "Loaded fallback LLM (priority=%d, tools=%s): %s (%s)",
                fp.priority,
                supports_tools,
                fp.model,
                fp.provider_type,
            )
            models.append((fp_model, fp.model, supports_tools))

    if not models:
        logger.error("No LLM models could be built from active providers")
        return (
            None,
            ReviewEngine(auto_approve_threshold=settings.auto_approve_threshold),
            None,
            None,
        )

    # Build pydantic model chain: extract just the model objects, sorted by tool support
    model_objects = [m for m, _, _ in models]
    pydantic_model = model_objects[0] if len(model_objects) == 1 else FallbackModel(*model_objects)
    logger.info(
        "LLM model chain ready: %d provider(s) [%s]",
        len(model_objects),
        " → ".join(name for _, name, _ in models),
    )

    classifier = QualityClassifierAgent(pydantic_model, retries=1 if len(model_objects) > 1 else 3)
    review_engine = ReviewEngine(auto_approve_threshold=settings.auto_approve_threshold)
    llm_enrichment = LocationEnrichmentAgent(pydantic_model, retries=1 if len(model_objects) > 1 else 3)
    date_parser = DateParserAgent(pydantic_model, retries=1 if len(model_objects) > 1 else 3)

    return classifier, review_engine, llm_enrichment, date_parser
