from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from hazlo.domain.event import Event, EventStatus
from hazlo.domain.source import Source
from hazlo.infrastructure.adapters.base import BaseSourceAdapter


@dataclass
class IngestionResult:
    source_id: uuid.UUID
    events_found: int = 0
    events_new: int = 0
    events_skipped: int = 0
    events_to_save: list[Event] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None


class IngestSource:
    def __init__(
        self,
        adapter_registry: dict[str, BaseSourceAdapter],
    ) -> None:
        self._adapter_registry = adapter_registry

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

        try:
            raw_events = await adapter.fetch(source.url)
        except Exception as exc:
            result.errors.append(f"Fetch failed: {exc}")
            result.finished_at = datetime.now(UTC)
            return result

        result.events_found = len(raw_events)

        for raw in raw_events:
            try:
                event = await adapter.normalize(raw)
            except Exception as exc:
                result.errors.append(f"Normalize failed: {exc}")
                continue

            if event.source_url in existing_urls:
                result.events_skipped += 1
                continue

            event.status = EventStatus.PENDING
            event.source_id = source.id
            result.events_to_save.append(event)
            existing_urls.add(event.source_url)

        result.events_new = len(result.events_to_save)
        result.finished_at = datetime.now(UTC)
        return result
