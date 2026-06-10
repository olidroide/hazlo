"""Tests for CSRF middleware."""

from __future__ import annotations

from starlette.testclient import TestClient

from hazlo.infrastructure.api.middleware.csrf import CSRFMiddleware, generate_csrf_token


def test_generate_csrf_token() -> None:
    token = generate_csrf_token()
    assert len(token) == 64
    assert token != generate_csrf_token()


def test_csrf_middleware_blocks_post_without_token() -> None:
    """POST without CSRF token should be blocked."""

    def dummy_app(scope, receive, send):
        async def inner():
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"OK"})

        return inner()

    middleware = CSRFMiddleware(app=dummy_app)
    client = TestClient(middleware)

    response = client.post("/admin/test", data={"title": "Test"})
    assert response.status_code == 403


def test_csrf_middleware_allows_get() -> None:
    """GET requests should pass through."""

    def dummy_app(scope, receive, send):
        async def inner():
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"OK"})

        return inner()

    middleware = CSRFMiddleware(app=dummy_app)
    client = TestClient(middleware)

    response = client.get("/admin/test")
    assert response.status_code == 200
