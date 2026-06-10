"""Tests for build_raw_document_store factory."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from hazlo.infrastructure.storage.factory import build_raw_document_store
from hazlo.infrastructure.storage.local_filesystem import LocalFilesystemStore


def test_build_local_store() -> None:
    settings = MagicMock()
    settings.raw_storage_backend = "local"
    settings.raw_local_path = Path("/tmp/test-raw")  # noqa: S108

    store = build_raw_document_store(settings)
    assert isinstance(store, LocalFilesystemStore)


def test_build_unknown_backend_raises() -> None:
    settings = MagicMock()
    settings.raw_storage_backend = "s3"

    with pytest.raises(ValueError, match="Unknown storage backend"):
        build_raw_document_store(settings)
