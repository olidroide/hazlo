from __future__ import annotations

from fastapi.testclient import TestClient

from hazlo.main import app


def test_root_returns_200() -> None:
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "hazlo"}
