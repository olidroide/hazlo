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


async def build_llm_infrastructure(
    session: AsyncSession,
) -> tuple[QualityClassifierAgent | None, ReviewEngine, LocationEnrichmentAgent | None, DateParserAgent | None]:
    """Build QualityClassifierAgent + ReviewEngine + LocationEnrichmentAgent + DateParserAgent.

    Returns (None, ReviewEngine, None, None) if no active LLM provider is configured.
    """
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

    settings = get_settings()

    result = await session.execute(select(LLMProviderModel).where(LLMProviderModel.is_active))
    active_provider = result.scalar_one_or_none()

    if active_provider is None:
        return (
            None,
            ReviewEngine(auto_approve_threshold=settings.auto_approve_threshold),
            None,
            None,
        )

    if not settings.hazlo_secret_key:
        return (
            None,
            ReviewEngine(auto_approve_threshold=settings.auto_approve_threshold),
            None,
            None,
        )

    models = []
    api_key = decrypt_value(active_provider.api_key_encrypted, settings.hazlo_secret_key)
    model = await build_pydantic_model(active_provider, api_key)
    if model:
        models.append(model)

    result = await session.execute(
        select(LLMProviderModel)
        .where(
            LLMProviderModel.is_active.is_(False),
            LLMProviderModel.id != active_provider.id,
        )
        .order_by(LLMProviderModel.priority)
    )
    fallback_providers = result.scalars().all()

    for fp in fallback_providers:
        fp_api_key = decrypt_value(fp.api_key_encrypted, settings.hazlo_secret_key)
        fp_model = await build_pydantic_model(fp, fp_api_key)
        if fp_model:
            models.append(fp_model)

    pydantic_model = models[0] if len(models) == 1 else FallbackModel(*models)

    classifier = QualityClassifierAgent(pydantic_model)
    review_engine = ReviewEngine(auto_approve_threshold=settings.auto_approve_threshold)
    llm_enrichment = LocationEnrichmentAgent(pydantic_model)
    date_parser = DateParserAgent(pydantic_model)

    return classifier, review_engine, llm_enrichment, date_parser
