from __future__ import annotations

import os

import pytest

from hazlo.settings import get_settings

# Remove extra env vars that cause strict validation errors
os.environ.pop("APP_HOST_PORT", None)


@pytest.fixture(autouse=True)
def _disable_admin_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HAZLO_ADMIN_PASSWORD", "")
    monkeypatch.setenv("HAZLO_ADMIN_USER", "")
    monkeypatch.setenv("HAZLO_SECRET_KEY", "test-secret-key-for-testing-only-32-bytes!!")
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _disable_csrf(monkeypatch: pytest.MonkeyPatch) -> None:
    """Disable CSRF middleware for tests by patching the app middleware stack."""
    from hazlo.main import app

    app.user_middleware = [
        m for m in app.user_middleware if getattr(getattr(m, "cls", None), "__name__", "") != "CSRFMiddleware"
    ]
