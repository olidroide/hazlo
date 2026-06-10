"""Tests for RawDocument entity."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from hazlo.domain.raw_document import RawDocument


def test_compute_content_hash() -> None:
    body = b"test content"
    h = RawDocument.compute_content_hash(body)
    assert len(h) == 64
    assert h == RawDocument.compute_content_hash(body)
    assert h != RawDocument.compute_content_hash(b"different")


def test_raw_document_is_frozen() -> None:
    doc = RawDocument(
        event_id=uuid.uuid4(),
        source_url="https://example.com",
        adapter="rss",
        content_type="application/rss+xml",
        body=b"<xml/>",
        payload={"title": "Test"},
        content_hash="abc123",
        byte_size=10,
        fetched_at=datetime(2026, 6, 1, 10, 0, tzinfo=UTC),
    )
    import dataclasses

    assert dataclasses.is_dataclass(doc)
    assert dataclasses.fields(doc)
