from __future__ import annotations

import time
import uuid

from prefect import flow, task
from prefect.logging import get_run_logger

from hazlo.application.services import DedupService, EnrichmentService
from hazlo.application.use_cases.ingest_source import IngestSource
from hazlo.infrastructure.llm.factory import build_llm_infrastructure
from hazlo.settings import get_settings

_settings = get_settings()


@task(
    name="fetch-source",
    retries=2,
    retry_delay_seconds=30,
    timeout_seconds=_settings.prefect_fetch_source_task_timeout_seconds,
)
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

        t_urls = time.monotonic()
        existing_urls = await event_repo.list_existing_urls_for_dedup()
        logger.info(
            "[%s] loaded existing URLs for dedup: %d (%.1fms)",
            source_id[:8],
            len(existing_urls),
            (time.monotonic() - t_urls) * 1000,
        )

        t_llm = time.monotonic()
        classifier, review_engine, llm_enrichment, date_parser = await build_llm_infrastructure(session)
        logger.info(
            "[%s] LLM infra ready (classifier=%s, location=%s, date_parser=%s) in %.1fms",
            source_id[:8],
            classifier is not None,
            llm_enrichment is not None,
            date_parser is not None,
            (time.monotonic() - t_llm) * 1000,
        )

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
            date_parser=date_parser,
            event_repo=event_repo,
        )
        t_execute = time.monotonic()
        result = await use_case.execute(source=source, existing_urls=existing_urls)
        logger.info("[%s] execute completed in %.1fms", source_id[:8], (time.monotonic() - t_execute) * 1000)

        t_save = time.monotonic()
        for event in result.events_to_save:
            await event_repo.save(event)
        logger.info(
            "[%s] persisted %d events in %.1fms",
            source_id[:8],
            len(result.events_to_save),
            (time.monotonic() - t_save) * 1000,
        )

        await _save_extraction_run(session, source.id, result)

        health = _compute_health(result)

        status = "success" if not result.errors else "error"
        await source_repo.update_last_run(source.id, status)
        t_commit = time.monotonic()
        await session.commit()
        logger.info("[%s] DB commit done in %.1fms", source_id[:8], (time.monotonic() - t_commit) * 1000)

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
