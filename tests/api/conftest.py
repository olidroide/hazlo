from __future__ import annotations

import pytest

from hazlo.settings import get_settings


@pytest.fixture(autouse=True)
def _disable_admin_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADMIN_PASSWORD", "")
    monkeypatch.setenv("ADMIN_USER", "")
    get_settings.cache_clear()
