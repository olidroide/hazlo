"""Raw document entity — the source of truth for event ingestion."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class RawDocument:
    event_id: UUID
    source_url: str
    adapter: str  # 'rss' | 'web' | 'email'
    content_type: str
    body: bytes
    payload: dict[str, object]
    content_hash: str
    byte_size: int
    fetched_at: datetime

    @staticmethod
    def compute_content_hash(body: bytes) -> str:
        return hashlib.sha256(body).hexdigest()
