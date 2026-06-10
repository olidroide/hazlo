"""Phase 2: parse_raw — read RAW from disk + normalize + enrich + classify + save."""

from __future__ import annotations

import time
import uuid
from dataclasses import replace

from prefect import flow, task
from prefect.logging import get_run_logger

from hazlo.infrastructure.storage.factory import build_raw_document_store
from hazlo.settings import get_settings

_settings = get_settings()


@task(name="parse-raw-document", retries=2, retry_delay_seconds=30, timeout_seconds=300)
async def parse_raw_document_task(raw_document_id: str) -> dict:
    """Read RAW from disk, normalize, enrich, classify, and save Event."""
    logger = get_run_logger()
    t0 = time.monotonic()

    from hazlo.application.services import DedupService, EnrichmentService
    from hazlo.infrastructure.db.repositories import EventRepository, RawDocumentRepository
    from hazlo.infrastructure.db.session import async_session_factory
    from hazlo.infrastructure.llm.factory import build_llm_infrastructure

    async with async_session_factory() as session:
        raw_doc_repo = RawDocumentRepository(session)
        event_repo = EventRepository(session)

        raw_doc = await raw_doc_repo.get(uuid.UUID(raw_document_id))
        if raw_doc is None:
            logger.error("RawDocument %s not found", raw_document_id)
            return {"raw_document_id": raw_document_id, "error": "RawDocument not found"}

        logger.info("[%s] parsing RAW for %s", raw_document_id[:8], raw_doc.event_id)

        if raw_doc.event_id is None:
            logger.error("RawDocument %s has no event_id", raw_document_id)
            return {"raw_document_id": raw_document_id, "error": "No event_id"}

        store = build_raw_document_store(_settings)
        t_read = time.monotonic()
        doc = store.read(raw_doc.event_id)
        logger.info("[%s] read RAW in %.1fms", raw_document_id[:8], (time.monotonic() - t_read) * 1000)

        adapter = _get_adapter_registry()[doc.adapter]
        from typing import cast

        from hazlo.infrastructure.adapters.base import BaseSourceAdapter

        adapter = cast(BaseSourceAdapter, adapter)
        t_normalize = time.monotonic()
        event = await adapter.normalize(doc.payload)
        logger.info("[%s] normalized in %.1fms", raw_document_id[:8], (time.monotonic() - t_normalize) * 1000)

        existing_urls = await event_repo.list_existing_urls_for_dedup()
        classifier, review_engine, llm_enrichment, date_parser = await build_llm_infrastructure(session)

        enrichment = EnrichmentService()
        enriched = enrichment.execute(event.to_dict())
        event = replace(
            event,
            title=enriched.get("title", event.title),
            location=enriched.get("location", event.location),
            start_at=enriched.get("start_at", event.start_at),
            end_at=enriched.get("end_at", event.end_at),
            price=enriched.get("price", event.price),
            ticket_info=enriched.get("ticket_info", event.ticket_info),
        )

        if llm_enrichment:
            try:
                event = await llm_enrichment.enrich_location(event)
            except Exception as exc:
                logger.warning("[%s] LLM enrichment failed: %s", raw_document_id[:8], exc)

        if date_parser:
            try:
                event = await date_parser.parse_dates(event)
            except Exception as exc:
                logger.warning("[%s] Date parsing failed: %s", raw_document_id[:8], exc)

        if not event.is_valid():
            logger.error("[%s] event invalid after parsing", raw_document_id[:8])
            return {"raw_document_id": raw_document_id, "error": "Event invalid after parsing"}

        dedup = DedupService()
        if dedup.execute(event, existing_urls):
            logger.info("[%s] event deduped, skipping", raw_document_id[:8])
            return {"raw_document_id": raw_document_id, "deduped": True}

        if classifier:
            try:
                classification = await classifier.execute(event)
                event = replace(
                    event,
                    is_children_activity=classification.is_children_activity,
                    is_toddler_friendly=classification.is_toddler_friendly,
                    confidence_score=classification.confidence,
                    agent_review={"raw_response": classification.raw_response},
                )
            except Exception as exc:
                logger.warning("[%s] LLM classification failed: %s", raw_document_id[:8], exc)

        if review_engine:
            decision = review_engine.execute(event)
            event = replace(event, status=decision.action)
            if decision.action.value != "approved":
                event = replace(
                    event,
                    agent_review={**(event.agent_review or {}), "review_reason": decision.reason},
                )

        t_save = time.monotonic()
        await event_repo.save(event)
        logger.info("[%s] saved event in %.1fms", raw_document_id[:8], (time.monotonic() - t_save) * 1000)

        await raw_doc_repo.mark_parsed(raw_doc.id)

        logger.info("[%s] parse_raw completed in %.1fms", raw_document_id[:8], (time.monotonic() - t0) * 1000)
        return {"raw_document_id": raw_document_id, "event_id": str(event.id), "status": event.status.value}


def _get_adapter_registry() -> dict[str, object]:
    from collections.abc import Mapping

    from hazlo.infrastructure.adapters.base import BaseSourceAdapter
    from hazlo.infrastructure.adapters.rss_adapter import RssSourceAdapter

    registry: Mapping[str, BaseSourceAdapter] = {"rss": RssSourceAdapter()}
    return dict(registry)


@flow(name="parse_raw", timeout_seconds=_settings.prefect_ingest_flow_timeout_seconds)
async def parse_raw(raw_document_id: str) -> dict:
    """Phase 2: read RAW + normalize + enrich + classify + save."""
    return await parse_raw_document_task(raw_document_id)
