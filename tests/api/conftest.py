from __future__ import annotations

import pytest

from hazlo.settings import get_settings


@pytest.fixture(autouse=True)
def _disable_admin_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADMIN_PASSWORD", "")
    monkeypatch.setenv("ADMIN_USER", "")
    monkeypatch.setenv("HAZLO_SECRET_KEY", "test-secret-key-for-testing-only-32-bytes!!")
    get_settings.cache_clear()
