from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from hazlo.domain.source import Source, SourceType
from hazlo.main import app


def _make_source(**kwargs: object) -> Source:
    defaults: dict[str, object] = {
        "name": "Test Source",
        "source_type": SourceType.SCRAPER,
        "url": "https://example.com",
        "is_active": True,
        "fetch_interval_minutes": 60,
        "last_run_at": None,
        "last_run_status": None,
    }
    defaults.update(kwargs)
    return Source(**{k: v for k, v in defaults.items() if v is not None or k in defaults})


@pytest.mark.asyncio
async def test_list_sources_returns_200() -> None:
    source = _make_source()
    mock_repo = MagicMock()
    mock_repo.list_all = AsyncMock(return_value=[source])

    with patch("hazlo.infrastructure.api.routes.admin_sources.SourceRepository", return_value=mock_repo):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/admin/sources/",
                headers={"HX-Request": "true"},
            )
    assert response.status_code == 200
    assert "Test Source" in response.text


@pytest.mark.asyncio
async def test_create_source_returns_partial_html() -> None:
    source = _make_source()
    mock_repo = MagicMock()
    mock_repo.save = AsyncMock(return_value=source)

    with patch("hazlo.infrastructure.api.routes.admin_sources.SourceRepository", return_value=mock_repo):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/admin/sources/",
                data={
                    "name": "New Source",
                    "source_type": "scraper",
                    "url": "https://new.example.com",
                    "fetch_interval_minutes": 30,
                },
                headers={"HX-Request": "true"},
            )
    assert response.status_code == 200
    assert "Test Source" in response.text
    assert "source-" in response.text


@pytest.mark.asyncio
async def test_toggle_source_updates_status() -> None:
    source = _make_source(is_active=False)
    mock_repo = MagicMock()
    mock_repo.toggle_active = AsyncMock(return_value=source)

    with patch("hazlo.infrastructure.api.routes.admin_sources.SourceRepository", return_value=mock_repo):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.patch(
                f"/admin/sources/{source.id}/toggle",
                headers={"HX-Request": "true"},
            )
    assert response.status_code == 200
    assert "Inactiva" in response.text
