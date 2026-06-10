"""Port: raw document storage abstraction."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol
from uuid import UUID

from hazlo.domain.raw_document import RawDocument


class RawDocumentStore(Protocol):
    def write(self, event_id: UUID, data: RawDocument) -> Path: ...
    def read(self, event_id: UUID) -> RawDocument: ...
    def exists(self, event_id: UUID) -> bool: ...
    def delete(self, event_id: UUID) -> None: ...
    def get_uri(self, event_id: UUID) -> str: ...
