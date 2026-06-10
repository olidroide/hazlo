"""Tests for LocalFilesystemStore."""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from hazlo.domain.raw_document import RawDocument
from hazlo.infrastructure.storage.local_filesystem import LocalFilesystemStore


@pytest.fixture
def tmp_store(tmp_path: Path) -> LocalFilesystemStore:
    return LocalFilesystemStore(tmp_path)


def _make_doc(event_id: uuid.UUID | None = None) -> RawDocument:
    return RawDocument(
        event_id=event_id or uuid.uuid4(),
        source_url="https://example.com/event",
        adapter="rss",
        content_type="application/rss+xml",
        body=b"<service><name>Test Event</name></service>",
        payload={"title": "Test Event", "source_url": "https://example.com/event"},
        content_hash="abc123",
        byte_size=45,
        fetched_at=datetime(2026, 6, 1, 10, 0, tzinfo=UTC),
    )


def test_write_creates_file(tmp_store: LocalFilesystemStore) -> None:
    doc = _make_doc()
    path = tmp_store.write(doc.event_id, doc)
    assert path.exists()
    assert path.name == f"{doc.event_id}.raw.json"


def test_write_is_atomic(tmp_store: LocalFilesystemStore) -> None:
    doc = _make_doc()
    path = tmp_store.write(doc.event_id, doc)
    assert path.exists()
    assert not path.with_suffix(path.suffix + ".tmp").exists()


def test_read_returns_same_data(tmp_store: LocalFilesystemStore) -> None:
    doc = _make_doc()
    tmp_store.write(doc.event_id, doc)
    read_doc = tmp_store.read(doc.event_id)
    assert read_doc.event_id == doc.event_id
    assert read_doc.source_url == doc.source_url
    assert read_doc.adapter == doc.adapter
    assert read_doc.content_type == doc.content_type
    assert read_doc.body == doc.body
    assert read_doc.payload == doc.payload
    assert read_doc.content_hash == doc.content_hash
    assert read_doc.byte_size == doc.byte_size
    assert read_doc.fetched_at == doc.fetched_at


def test_read_raises_if_not_found(tmp_store: LocalFilesystemStore) -> None:
    with pytest.raises(FileNotFoundError):
        tmp_store.read(uuid.uuid4())


def test_exists(tmp_store: LocalFilesystemStore) -> None:
    doc = _make_doc()
    assert not tmp_store.exists(doc.event_id)
    tmp_store.write(doc.event_id, doc)
    assert tmp_store.exists(doc.event_id)


def test_delete(tmp_store: LocalFilesystemStore) -> None:
    doc = _make_doc()
    tmp_store.write(doc.event_id, doc)
    assert tmp_store.exists(doc.event_id)
    tmp_store.delete(doc.event_id)
    assert not tmp_store.exists(doc.event_id)


def test_delete_noop_if_not_exists(tmp_store: LocalFilesystemStore) -> None:
    tmp_store.delete(uuid.uuid4())


def test_get_uri(tmp_store: LocalFilesystemStore) -> None:
    doc = _make_doc()
    uri = tmp_store.get_uri(doc.event_id)
    assert str(doc.event_id) in uri
    assert uri.endswith(".raw.json")


def test_write_overwrites_existing(tmp_store: LocalFilesystemStore) -> None:
    doc1 = _make_doc()
    tmp_store.write(doc1.event_id, doc1)
    doc2 = replace(doc1, source_url="https://updated.com")
    tmp_store.write(doc2.event_id, doc2)
    read_doc = tmp_store.read(doc2.event_id)
    assert read_doc.source_url == "https://updated.com"


def test_body_with_unicode(tmp_store: LocalFilesystemStore) -> None:
    doc = _make_doc()
    doc = replace(doc, body="Café con leche 🎉".encode())
    tmp_store.write(doc.event_id, doc)
    read_doc = tmp_store.read(doc.event_id)
    assert read_doc.body == "Café con leche 🎉".encode()


def test_payload_with_nested_data(tmp_store: LocalFilesystemStore) -> None:
    doc = _make_doc()
    nested: dict[str, object] = {"key": "value", "list": [1, 2, 3]}
    doc = replace(doc, payload={"title": "Test", "nested": nested})
    tmp_store.write(doc.event_id, doc)
    read_doc = tmp_store.read(doc.event_id)
    assert read_doc.payload["title"] == "Test"
    assert read_doc.payload["nested"] == nested
