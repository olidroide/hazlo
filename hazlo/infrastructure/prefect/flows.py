from __future__ import annotations

import uuid

from prefect import flow, task
from prefect.logging import get_run_logger

from hazlo.application.services import DedupService, EnrichmentService
from hazlo.application.use_cases.ingest_source import IngestSource
from hazlo.domain.event import EventStatus
from hazlo.infrastructure.llm.providers.base import LLMProvider


@task(name="fetch-source", retries=2, retry_delay_seconds=30)
async def fetch_source_task(source_id: str) -> dict:
    from hazlo.infrastructure.db.repositories import EventRepository, SourceRepository
    from hazlo.infrastructure.db.session import async_session_factory

    async with async_session_factory() as session:
        source_repo = SourceRepository(session)
        event_repo = EventRepository(session)

        source = await source_repo.get(uuid.UUID(source_id))
        if source is None:
            return {"source_id": source_id, "error": "Source not found"}

        pending = await event_repo.list_by_status(EventStatus.PENDING)
        existing_urls = {e.source_url for e in pending}

        classifier, review_engine, llm_enrichment = await _build_llm_infrastructure(session)

        use_case = IngestSource(
            adapter_registry=_get_adapter_registry(),
            enrichment_service=EnrichmentService(),
            dedup_service=DedupService(),
            quality_classifier=classifier,
            review_engine=review_engine,
            llm_enrichment_service=llm_enrichment,
            event_repo=event_repo,
        )
        result = await use_case.execute(source=source, existing_urls=existing_urls)

        for event in result.events_to_save:
            await event_repo.save(event)

        await _save_extraction_run(session, source.id, result)

        health = _compute_health(result)

        status = "success" if not result.errors else "error"
        await source_repo.update_last_run(source.id, status)
        await session.commit()

        return {
            "source_id": str(result.source_id),
            "events_found": result.events_found,
            "events_new": result.events_new,
            "events_skipped": result.events_skipped,
            "events_auto_approved": result.events_auto_approved,
            "events_flagged": result.events_flagged,
            "errors": result.errors,
            "health": health,
        }


async def _build_llm_infrastructure(session):
    """Build QualityClassifier + ReviewEngine + LLMEnrichmentService from DB-configured LLM providers.

    Returns (None, None, None) if no active LLM provider is configured.
    """
    from hazlo.application.services import QualityClassifier, ReviewEngine
    from hazlo.application.services.llm_enrichment_service import LLMEnrichmentService
    from hazlo.infrastructure.crypto import decrypt_value
    from hazlo.infrastructure.db.models import LLMProviderModel
    from hazlo.infrastructure.llm import LLMClient
    from hazlo.infrastructure.llm.providers import GeminiProvider, OpenRouterProvider
    from hazlo.settings import get_settings

    settings = get_settings()

    result = await session.execute(__import__("sqlalchemy").select(LLMProviderModel).where(LLMProviderModel.is_active))
    active_provider = result.scalar_one_or_none()

    if active_provider is None:
        return None, ReviewEngine(auto_approve_threshold=settings.auto_approve_threshold), None

    if not settings.hazlo_secret_key:
        return None, ReviewEngine(auto_approve_threshold=settings.auto_approve_threshold), None

    providers: list[tuple[LLMProvider, str]] = []
    api_key = decrypt_value(active_provider.api_key_encrypted, settings.hazlo_secret_key)

    match active_provider.provider_type:
        case "gemini":
            providers.append((GeminiProvider(api_key=api_key, model=active_provider.model), active_provider.name))
        case "openrouter":
            providers.append((OpenRouterProvider(api_key=api_key, model=active_provider.model), active_provider.name))

    result = await session.execute(
        __import__("sqlalchemy")
        .select(LLMProviderModel)
        .where(
            LLMProviderModel.is_active.is_(False),
            LLMProviderModel.id != active_provider.id,
        )
        .order_by(LLMProviderModel.priority)
    )
    fallback_providers = result.scalars().all()

    for fp in fallback_providers:
        fp_api_key = decrypt_value(fp.api_key_encrypted, settings.hazlo_secret_key)
        match fp.provider_type:
            case "gemini":
                providers.append((GeminiProvider(api_key=fp_api_key, model=fp.model), fp.name))
            case "openrouter":
                providers.append((OpenRouterProvider(api_key=fp_api_key, model=fp.model), fp.name))

    llm_client = LLMClient(
        providers,
        failure_threshold=settings.llm_circuit_breaker_failure_threshold,
        reset_timeout_seconds=settings.llm_circuit_breaker_reset_timeout_seconds,
    )
    classifier = QualityClassifier(llm_client)
    review_engine = ReviewEngine(auto_approve_threshold=settings.auto_approve_threshold)
    llm_enrichment = LLMEnrichmentService(llm_client)

    return classifier, review_engine, llm_enrichment


def _get_adapter_registry():
    """Get adapter registry, avoiding circular imports."""
    from hazlo.infrastructure.adapters import adapter_registry

    return adapter_registry


async def _save_extraction_run(session, source_id, result):
    """Persist ExtractionRunModel with metrics from ingestion."""
    from hazlo.infrastructure.db.models import ExtractionRunModel

    run = ExtractionRunModel(
        source_id=source_id,
        started_at=result.started_at,
        finished_at=result.finished_at,
        status="error" if result.errors else "success",
        events_found=result.events_found,
        documents_fetched=result.events_found,
        events_extracted=result.events_found,
        events_created=result.events_new,
        events_flagged=result.events_flagged,
        events_auto_approved=result.events_auto_approved,
        events_auto_rejected=result.events_auto_rejected,
        errors="\n".join(result.errors) if result.errors else None,
    )
    session.add(run)


@flow(name="ingest-all-sources", log_prints=True)
async def ingest_all_sources_flow() -> None:
    import asyncio

    from hazlo.infrastructure.db.repositories import SourceRepository
    from hazlo.infrastructure.db.session import async_session_factory

    logger = get_run_logger()

    async with async_session_factory() as session:
        source_repo = SourceRepository(session)
        sources = await source_repo.list_all()
        active_sources = [s for s in sources if s.is_active]

    logger.info(f"Found {len(active_sources)} active sources")

    results = await asyncio.gather(
        *[fetch_source_task(str(s.id)) for s in active_sources],
        return_exceptions=True,
    )

    total_found = 0
    total_new = 0
    total_auto_approved = 0
    total_flagged = 0
    total_errors = 0

    for r in results:
        if isinstance(r, Exception):
            total_errors += 1
            logger.error(f"Source failed: {r}")
        elif isinstance(r, dict):
            total_found += r.get("events_found", 0)
            total_new += r.get("events_new", 0)
            total_auto_approved += r.get("events_auto_approved", 0)
            total_flagged += r.get("events_flagged", 0)
            if r.get("errors"):
                total_errors += len(r["errors"])

    logger.info(
        f"Summary: {total_found} found, {total_new} new, "
        f"{total_auto_approved} auto-approved, {total_flagged} flagged, "
        f"{total_errors} errors"
    )


@flow(name="ingest-single-source")
async def ingest_single_source_flow(source_id: str) -> dict:
    result = await fetch_source_task(source_id)
    return result


def _compute_health(result) -> dict:
    """Compute source health metrics from ingestion result."""
    return {
        "events_found": result.events_found,
        "events_new": result.events_new,
        "events_skipped": result.events_skipped,
        "errors": len(result.errors),
        "status": "error" if result.errors else "success",
    }
