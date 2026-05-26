from __future__ import annotations

import os

import pytest

from hazlo.settings import get_settings

# Remove extra env vars that cause strict validation errors
os.environ.pop("APP_HOST_PORT", None)


@pytest.fixture(autouse=True)
def _disable_admin_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADMIN_PASSWORD", "")
    monkeypatch.setenv("ADMIN_USER", "")
    monkeypatch.setenv("HAZLO_SECRET_KEY", "test-secret-key-for-testing-only-32-bytes!!")
    get_settings.cache_clear()
