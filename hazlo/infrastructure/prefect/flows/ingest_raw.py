"""Phase 1: ingest_raw — fetch + persist RAW. No parsing, no LLM."""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime

from prefect import flow, task
from prefect.logging import get_run_logger

from hazlo.domain.raw_document import RawDocument
from hazlo.infrastructure.storage.factory import build_raw_document_store
from hazlo.settings import get_settings

_settings = get_settings()


@task(name="ingest-raw-source", retries=2, retry_delay_seconds=30, timeout_seconds=300)
async def ingest_raw_source_task(source_id: str) -> dict:
    """Fetch events from source and persist RAW documents. No parsing."""
    logger = get_run_logger()
    t0 = time.monotonic()

    from hazlo.infrastructure.db.repositories import RawDocumentRepository, SourceRepository
    from hazlo.infrastructure.db.session import async_session_factory

    async with async_session_factory() as session:
        source_repo = SourceRepository(session)
        raw_doc_repo = RawDocumentRepository(session)

        source = await source_repo.get(uuid.UUID(source_id))
        if source is None:
            logger.error("Source %s not found", source_id)
            return {"source_id": source_id, "error": "Source not found", "persisted": 0}

        logger.info("[%s] %s (%s) — url=%s", source_id[:8], source.name, source.source_type.value, source.url or "IMAP")

        adapter = _get_adapter_registry()[source.source_type.value]
        from typing import cast

        from hazlo.infrastructure.adapters.base import BaseSourceAdapter

        adapter = cast(BaseSourceAdapter, adapter)
        store = build_raw_document_store(_settings)

        t_fetch = time.monotonic()
        raw_events = await adapter.fetch(source)
        logger.info(
            "[%s] fetched %d raw events in %.1fms", source_id[:8], len(raw_events), (time.monotonic() - t_fetch) * 1000
        )

        persisted = 0
        t_persist = time.monotonic()
        for raw_event in raw_events:
            source_url = raw_event.get("source_url", source.url or "")
            if not source_url:
                logger.warning("[%s] skipping event without source_url", source_id[:8])
                continue

            event_id = uuid.uuid4()
            body = _extract_body(raw_event, source.source_type.value)
            content_hash = RawDocument.compute_content_hash(body)

            if await raw_doc_repo.get(event_id) is not None:
                logger.info("[%s] RAW already exists for %s, skipping", source_id[:8], event_id)
                continue

            doc = RawDocument(
                event_id=event_id,
                source_url=source_url,
                adapter=source.source_type.value,
                content_type=_content_type_for_adapter(source.source_type.value),
                body=body,
                payload=raw_event,
                content_hash=content_hash,
                byte_size=len(body),
                fetched_at=datetime.now(UTC),
            )

            store.write(event_id, doc)
            await raw_doc_repo.create(
                event_id=event_id,
                storage_backend=_settings.raw_storage_backend,
                storage_uri=store.get_uri(event_id),
                content_type=doc.content_type,
                content_hash=content_hash,
                byte_size=doc.byte_size,
                fetched_at=doc.fetched_at,
                source_url=source_url,
                adapter=source.source_type.value,
            )
            persisted += 1

        logger.info(
            "[%s] persisted %d RAW documents in %.1fms", source_id[:8], persisted, (time.monotonic() - t_persist) * 1000
        )
        logger.info("[%s] ingest_raw completed in %.1fms", source_id[:8], (time.monotonic() - t0) * 1000)

        return {"source_id": source_id, "persisted": persisted, "total": len(raw_events)}


def _get_adapter_registry() -> dict[str, object]:
    from collections.abc import Mapping

    from hazlo.infrastructure.adapters.base import BaseSourceAdapter
    from hazlo.infrastructure.adapters.rss_adapter import RssSourceAdapter

    registry: Mapping[str, BaseSourceAdapter] = {"rss": RssSourceAdapter()}
    return dict(registry)


def _extract_body(raw_event: dict, adapter_type: str) -> bytes:
    """Extract raw body bytes from the raw event dict."""
    if adapter_type == "rss":
        return str(raw_event.get("raw_description", "")).encode("utf-8")
    return str(raw_event).encode("utf-8")


def _content_type_for_adapter(adapter_type: str) -> str:
    if adapter_type == "rss":
        return "application/rss+xml"
    if adapter_type == "web":
        return "text/html"
    if adapter_type == "email":
        return "message/rfc822"
    return "application/octet-stream"


@flow(name="ingest_raw", timeout_seconds=_settings.prefect_ingest_flow_timeout_seconds)
async def ingest_raw(source_id: str) -> dict:
    """Phase 1: fetch + persist RAW documents."""
    return await ingest_raw_source_task(source_id)
