from __future__ import annotations

import time
import uuid

from prefect import flow, task
from prefect.logging import get_run_logger

from hazlo.application.services import DedupService, EnrichmentService
from hazlo.application.use_cases.ingest_source import IngestSource
from hazlo.domain.event import EventStatus


@task(name="fetch-source", retries=2, retry_delay_seconds=30)
async def fetch_source_task(source_id: str) -> dict:
    logger = get_run_logger()
    t0 = time.monotonic()

    from hazlo.infrastructure.db.repositories import EventRepository, SourceRepository
    from hazlo.infrastructure.db.session import async_session_factory

    async with async_session_factory() as session:
        source_repo = SourceRepository(session)
        event_repo = EventRepository(session)

        source = await source_repo.get(uuid.UUID(source_id))
        if source is None:
            logger.error("Source %s not found", source_id)
            return {"source_id": source_id, "error": "Source not found"}

        logger.info(
            "[%s] %s (%s) — url=%s",
            source_id[:8],
            source.name,
            source.source_type.value,
            source.url or "IMAP",
        )

        pending = await event_repo.list_by_status(EventStatus.PENDING)
        existing_urls = {e.source_url for e in pending}

        classifier, review_engine, llm_enrichment = await _build_llm_infrastructure(session)

        if classifier is not None:
            logger.info("[%s] LLM classifier active", source_id[:8])
        else:
            logger.info("[%s] No LLM classifier — all events go to manual review", source_id[:8])

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

        duration = time.monotonic() - t0

        logger.info(
            "[%s] %s → found=%d new=%d skipped=%d approved=%d flagged=%d rejected=%d errors=%d (%.1fs)",
            source_id[:8],
            source.name,
            result.events_found,
            result.events_new,
            result.events_skipped,
            result.events_auto_approved,
            result.events_flagged,
            result.events_auto_rejected,
            len(result.errors),
            duration,
        )

        for err in result.errors:
            logger.warning("[%s] Error: %s", source_id[:8], err)

        return {
            "source_id": str(result.source_id),
            "source_name": source.name,
            "events_found": result.events_found,
            "events_new": result.events_new,
            "events_skipped": result.events_skipped,
            "events_auto_approved": result.events_auto_approved,
            "events_flagged": result.events_flagged,
            "events_auto_rejected": result.events_auto_rejected,
            "errors": result.errors,
            "health": health,
            "duration_s": round(duration, 1),
        }


async def _build_pydantic_model(provider, api_key: str):
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
    return None


async def _build_llm_infrastructure(session):
    """Build QualityClassifierAgent + ReviewEngine + LocationEnrichmentAgent from DB-configured LLM providers.

    Returns (None, None, None) if no active LLM provider is configured.
    """
    from pydantic_ai.models.fallback import FallbackModel
    from sqlalchemy import select

    from hazlo.application.services import ReviewEngine
    from hazlo.infrastructure.crypto import decrypt_value
    from hazlo.infrastructure.db.models import LLMProviderModel
    from hazlo.infrastructure.llm.agents import LocationEnrichmentAgent, QualityClassifierAgent
    from hazlo.settings import get_settings
    settings = get_settings()

    result = await session.execute(select(LLMProviderModel).where(LLMProviderModel.is_active))
    active_provider = result.scalar_one_or_none()

    if active_provider is None:
        return None, ReviewEngine(auto_approve_threshold=settings.auto_approve_threshold), None

    if not settings.hazlo_secret_key:
        return None, ReviewEngine(auto_approve_threshold=settings.auto_approve_threshold), None

    models = []
    api_key = decrypt_value(active_provider.api_key_encrypted, settings.hazlo_secret_key)
    model = await _build_pydantic_model(active_provider, api_key)
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
        fp_model = await _build_pydantic_model(fp, fp_api_key)
        if fp_model:
            models.append(fp_model)

    pydantic_model = models[0] if len(models) == 1 else FallbackModel(*models)

    classifier = QualityClassifierAgent(pydantic_model)
    review_engine = ReviewEngine(auto_approve_threshold=settings.auto_approve_threshold)
    llm_enrichment = LocationEnrichmentAgent(pydantic_model)

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
    t0 = time.monotonic()

    async with async_session_factory() as session:
        source_repo = SourceRepository(session)
        sources = await source_repo.list_all()
        active_sources = [s for s in sources if s.is_active]

    source_names = ", ".join(f"{s.name} ({s.source_type.value})" for s in active_sources)
    logger.info("Found %d active sources: %s", len(active_sources), source_names)

    results = await asyncio.gather(
        *[fetch_source_task(str(s.id)) for s in active_sources],
        return_exceptions=True,
    )

    total_found = 0
    total_new = 0
    total_skipped = 0
    total_auto_approved = 0
    total_flagged = 0
    total_auto_rejected = 0
    total_errors = 0
    source_breakdown = []

    for r in results:
        if isinstance(r, Exception):
            total_errors += 1
            logger.error("Source task failed: %s", r)
            source_breakdown.append({"name": "UNKNOWN", "status": "FAILED", "error": str(r)})
        elif isinstance(r, dict):
            name = r.get("source_name", r.get("source_id", "unknown"))
            found = r.get("events_found", 0)
            new = r.get("events_new", 0)
            skipped = r.get("events_skipped", 0)
            approved = r.get("events_auto_approved", 0)
            flagged = r.get("events_flagged", 0)
            rejected = r.get("events_auto_rejected", 0)
            errs = r.get("errors", [])
            duration = r.get("duration_s", 0)

            total_found += found
            total_new += new
            total_skipped += skipped
            total_auto_approved += approved
            total_flagged += flagged
            total_auto_rejected += rejected
            total_errors += len(errs)

            status = "OK" if not errs else f"ERRORS({len(errs)})"
            source_breakdown.append({
                "name": name, "found": found, "new": new,
                "skipped": skipped, "approved": approved,
                "flagged": flagged, "rejected": rejected,
                "errors": len(errs), "duration_s": duration, "status": status,
            })

    duration = time.monotonic() - t0

    logger.info("=" * 80)
    logger.info("INGESTION SUMMARY (%.1fs)", duration)
    logger.info("=" * 80)
    logger.info(
        "TOTAL → found=%d new=%d skipped=%d approved=%d flagged=%d rejected=%d errors=%d",
        total_found, total_new, total_skipped,
        total_auto_approved, total_flagged, total_auto_rejected,
        total_errors,
    )
    for sb in source_breakdown:
        if sb.get("error"):
            logger.error("  %-30s FAILED: %s", sb["name"], sb["error"])
        else:
            logger.info(
                "  %-30s found=%-5d new=%-4d skipped=%-5d "
                "approved=%-4d flagged=%-4d rejected=%-4d errors=%-3d (%.1fs) [%s]",
                sb["name"], sb["found"], sb["new"], sb["skipped"],
                sb["approved"], sb["flagged"], sb["rejected"],
                sb["errors"], sb["duration_s"], sb["status"],
            )
    logger.info("=" * 80)


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
