"""Factory: build RawDocumentStore from settings."""

from __future__ import annotations

from hazlo.domain.ports.raw_document_store import RawDocumentStore


def build_raw_document_store(settings) -> RawDocumentStore:
    from hazlo.infrastructure.storage.local_filesystem import LocalFilesystemStore

    backend = settings.raw_storage_backend

    if backend == "local":
        return LocalFilesystemStore(settings.raw_local_path)
    msg = f"Unknown storage backend: {backend}"
    raise ValueError(msg)
