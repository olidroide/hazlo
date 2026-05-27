from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Any, Protocol

from hazlo.application.services import (
    DedupService,
    EnrichmentService,
    ReviewEngine,
)
from hazlo.domain.event import Event, EventStatus
from hazlo.domain.llm_output import ClassificationResult
from hazlo.domain.source import Source
from hazlo.infrastructure.adapters.base import BaseSourceAdapter


class QualityClassifierProtocol(Protocol):
    async def execute(self, event: Event) -> ClassificationResult: ...


class LocationEnrichmentProtocol(Protocol):
    async def enrich_location(self, event: Event) -> Event: ...


class DateParserProtocol(Protocol):
    async def parse_dates(self, event: Event) -> Event: ...


logger = logging.getLogger(__name__)


@dataclass
class IngestionResult:
    source_id: uuid.UUID
    events_found: int = 0
    events_new: int = 0
    events_skipped: int = 0
    events_auto_approved: int = 0
    events_flagged: int = 0
    events_auto_rejected: int = 0
    events_to_save: list[Event] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None


class IngestSource:
    def __init__(
        self,
        adapter_registry: dict[str, BaseSourceAdapter],
        enrichment_service: EnrichmentService,
        dedup_service: DedupService,
        quality_classifier: QualityClassifierProtocol | None = None,
        review_engine: ReviewEngine | None = None,
        llm_enrichment_service: LocationEnrichmentProtocol | None = None,
        date_parser: DateParserProtocol | None = None,
        event_repo: object | None = None,
        event_queue: asyncio.Queue[dict[str, object]] | None = None,
    ) -> None:
        self._adapter_registry = adapter_registry
        self._enrichment = enrichment_service
        self._dedup = dedup_service
        self._classifier = quality_classifier
        self._review_engine = review_engine
        self._llm_enrichment = llm_enrichment_service
        self._date_parser = date_parser
        self._event_repo = event_repo
        self._event_queue = event_queue

    async def execute(
        self,
        *,
        source: Source,
        existing_urls: set[str],
    ) -> IngestionResult:
        result = IngestionResult(source_id=source.id)
        adapter = self._adapter_registry.get(source.source_type.value)
        if adapter is None:
            result.errors.append(f"No adapter for source type: {source.source_type.value}")
            result.finished_at = datetime.now(UTC)
            return result

        await self._emit("source_loaded", "info", msg=f"Source: {source.name}", type=source.source_type.value)
        await self._emit("fetch_start", "info", msg=f"Connecting to {source.url or 'IMAP'}...")

        fetch_t0 = time.monotonic()
        try:
            raw_events = await adapter.fetch(source)
        except Exception as exc:
            logger.exception("Fetch failed for source=%s (%s)", source.name, source.id)
            await self._emit("fetch_error", "error", msg=f"Error fetching data: {exc}")
            result.errors.append(f"Fetch failed: {exc}")
            result.finished_at = datetime.now(UTC)
            return result

        result.events_found = len(raw_events)
        await self._emit(
            "fetch_done",
            "success",
            msg=f"{len(raw_events)} events found in feed",
            duration_ms=int((time.monotonic() - fetch_t0) * 1000),
        )

        content_hashes = await self._load_existing_content_hashes(raw_events)

        normalize_ok = 0
        normalize_fail = 0

        for raw in raw_events:
            content_hash = Event.compute_content_hash(raw)
            if content_hash in content_hashes:
                result.events_skipped += 1
                continue

            try:
                event = await adapter.normalize(raw)
            except Exception as exc:
                normalize_fail += 1
                logger.exception(
                    "Normalize failed source=%s title=%s",
                    source.id,
                    raw.get("title", "unknown"),
                )
                await self._emit(
                    "normalize",
                    "error",
                    msg=f"Normalize error: {exc}",
                    title=raw.get("title", "unknown"),
                )
                result.errors.append(f"Normalize failed: {exc}")
                continue

            idempotency_key = event.compute_idempotency_key().value

            if event.source_url in existing_urls:
                result.events_skipped += 1
                continue

            normalize_ok += 1
            event = replace(event, source_id=source.id, idempotency_key=idempotency_key, content_hash=content_hash)

            await self._emit(
                "normalize",
                "success",
                msg=f"{event.title}",
                start_at=event.start_at.isoformat() if event.start_at else "",
                source_url=event.source_url,
            )

            event = self._apply_enrichment(event)

            if self._llm_enrichment:
                try:
                    event = await self._llm_enrichment.enrich_location(event)
                    await self._emit(
                        "llm_enrich",
                        "success",
                        msg=f"{event.title} → metro={event.location.metro if event.location else 'N/A'} "
                        f"neighborhood={event.location.neighborhood if event.location else 'N/A'}",
                    )
                except Exception as exc:
                    result.errors.append(f"LLM enrichment failed: {exc}")
                    await self._emit(
                        "llm_enrich",
                        "error",
                        msg=f"{event.title} → LLM error: {exc}",
                    )

            if self._date_parser:
                try:
                    event = await self._date_parser.parse_dates(event)
                    await self._emit(
                        "llm_date_parse",
                        "success",
                        msg=f"{event.title} → start={event.start_at.isoformat() if event.start_at else 'N/A'} "
                        f"end={event.end_at.isoformat() if event.end_at else 'N/A'}",
                    )
                except Exception as exc:
                    result.errors.append(f"Date parsing failed: {exc}")
                    await self._emit(
                        "llm_date_parse",
                        "error",
                        msg=f"{event.title} → LLM error: {exc}",
                    )

            if not event.is_valid():
                await self._emit(
                    "normalize",
                    "error",
                    msg=f"Invalid event (missing title/start_at/location): {event.title or 'unknown'}",
                )
                result.errors.append(f"Event invalid (missing title/start_at/location): {event.title or 'unknown'}")
                result.events_auto_rejected += 1
                continue

            if self._dedup.execute(event, existing_urls):
                result.events_skipped += 1
                continue

            if self._classifier:
                try:
                    classification = await self._classifier.execute(event)
                    event = replace(
                        event,
                        is_children_activity=classification.is_children_activity,
                        is_toddler_friendly=classification.is_toddler_friendly,
                        confidence_score=classification.confidence,
                        agent_review={"raw_response": classification.raw_response},
                    )
                    await self._emit(
                        "llm_classify",
                        "success",
                        msg=f"{event.title} → children={classification.is_children_activity} "
                        f"conf={classification.confidence:.2f}",
                        raw_json=classification.raw_response,
                    )
                except Exception as exc:
                    result.errors.append(f"LLM classification failed: {exc}")
                    event = replace(
                        event,
                        agent_review={**(event.agent_review or {}), "llm_error": str(exc)},
                    )
                    await self._emit(
                        "llm_classify",
                        "error",
                        msg=f"{event.title} → LLM error: {exc}",
                    )

            if self._review_engine:
                decision = self._review_engine.execute(event)
                if decision.action == EventStatus.APPROVED:
                    event = replace(event, status=EventStatus.APPROVED)
                    result.events_auto_approved += 1
                else:
                    event = replace(event, status=EventStatus.PENDING)
                    result.events_flagged += 1
                    event = replace(
                        event,
                        agent_review={
                            **(event.agent_review or {}),
                            "review_reason": decision.reason,
                        },
                    )
            else:
                event = replace(event, status=EventStatus.PENDING)
                result.events_flagged += 1

            if self._is_past(event):
                event = replace(event, is_expired=True)
                logger.info(
                    "Event %s marked expired (end_at=%s, start_at=%s)",
                    event.title,
                    event.end_at,
                    event.start_at,
                )

            result.events_to_save.append(event)
            existing_urls.add(event.source_url)

        result.events_new = len(result.events_to_save)
        result.finished_at = datetime.now(UTC)

        await self._emit(
            "dedup",
            "info",
            msg=f"Dedup: {normalize_ok + normalize_fail} total, {result.events_new} new, "
            f"{normalize_fail + len(result.errors)} errors",
        )

        duration_ms = int((result.finished_at - result.started_at).total_seconds() * 1000)
        await self._emit(
            "complete",
            "summary",
            found=result.events_found,
            new=result.events_new,
            skipped=result.events_skipped,
            approved=result.events_auto_approved,
            flagged=result.events_flagged,
            errors=len(result.errors),
            duration_ms=duration_ms,
        )

        return result

    async def _emit(self, step: str, level: str, **data: object) -> None:
        msg = str(data.get("msg", ""))
        payload = {k: v for k, v in data.items() if k != "msg"}
        extra = " ".join(f"{k}={v}" for k, v in payload.items() if v not in (None, ""))
        line = f"[{step}] {msg}" if msg else f"[{step}]"
        if extra:
            line = f"{line} | {extra}"

        match level:
            case "error":
                logger.error(line)
            case "warning":
                logger.warning(line)
            case "success" | "summary":
                logger.info(line)
            case _:
                logger.info(line)

        if self._event_queue is not None:
            await self._event_queue.put({"step": step, "level": level, **data})

    async def _load_existing_idempotency_keys(
        self,
        raw_events: list[dict],
        adapter: BaseSourceAdapter,
    ) -> set[str]:
        if self._event_repo is None:
            return set()

        repo: Any = self._event_repo

        keys_to_check: set[str] = set()
        for raw in raw_events:
            try:
                event = await adapter.normalize(raw)
                key = event.compute_idempotency_key().value
                keys_to_check.add(key)
            except Exception:
                logger.warning("Failed to normalize raw event for idempotency check", exc_info=True)
                continue

        if not keys_to_check:
            return set()

        return await repo.list_existing_idempotency_keys(keys_to_check)

    async def _load_existing_content_hashes(self, raw_events: list[dict]) -> set[str]:
        if self._event_repo is None:
            return set()

        repo: Any = self._event_repo

        hashes_to_check: set[str] = set()
        for raw in raw_events:
            try:
                content_hash = Event.compute_content_hash(raw)
                hashes_to_check.add(content_hash)
            except Exception:
                logger.warning("Failed to compute content hash for raw event", exc_info=True)
                continue

        if not hashes_to_check:
            return set()

        return await repo.list_existing_content_hashes(hashes_to_check)

    def _apply_enrichment(self, event: Event) -> Event:
        enriched = self._enrichment.execute(event.to_dict())
        return replace(
            event,
            title=enriched.get("title", event.title),
            location=enriched.get("location", event.location),
            start_at=enriched.get("start_at", event.start_at),
            end_at=enriched.get("end_at", event.end_at),
            price=enriched.get("price", event.price),
            ticket_info=enriched.get("ticket_info", event.ticket_info),
        )

    @staticmethod
    def _is_past(event: Event) -> bool:
        now = datetime.now(UTC)
        if event.end_at:
            return event.end_at < now
        if event.start_at:
            return event.start_at < now
        return False
