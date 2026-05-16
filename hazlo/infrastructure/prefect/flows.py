from __future__ import annotations

import uuid

from prefect import flow, task
from prefect.logging import get_run_logger

from hazlo.application.use_cases.ingest_source import IngestSource
from hazlo.domain.event import EventStatus
from hazlo.infrastructure.adapters import adapter_registry


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

        use_case = IngestSource(adapter_registry=adapter_registry)
        result = await use_case.execute(source=source, existing_urls=existing_urls)

        for event in result.events_to_save:
            await event_repo.save(event)

        status = "success" if not result.errors else "error"
        await source_repo.update_last_run(source.id, status)
        await session.commit()

        return {
            "source_id": str(result.source_id),
            "events_found": result.events_found,
            "events_new": result.events_new,
            "events_skipped": result.events_skipped,
            "errors": result.errors,
        }


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
    total_errors = 0

    for r in results:
        if isinstance(r, Exception):
            total_errors += 1
            logger.error(f"Source failed: {r}")
        elif isinstance(r, dict):
            total_found += r.get("events_found", 0)
            total_new += r.get("events_new", 0)
            if r.get("errors"):
                total_errors += len(r["errors"])

    logger.info(f"Summary: {total_found} found, {total_new} new, {total_errors} errors")


@flow(name="ingest-single-source")
async def ingest_single_source_flow(source_id: str) -> dict:
    result = await fetch_source_task(source_id)
    return result
