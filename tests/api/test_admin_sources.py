from __future__ import annotations

import uuid
from datetime import datetime
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from hazlo.domain.source import Source, SourceType
from hazlo.infrastructure.api import deps
from hazlo.infrastructure.api.deps import get_source_repo
from hazlo.infrastructure.db.repositories import SourceRepository
from hazlo.main import app

_NOT_SET = object()


def _make_source(
    id: uuid.UUID | object = _NOT_SET,
    name: str = "Test Source",
    source_type: SourceType = SourceType.RSS,
    url: str = "https://example.com",
    is_active: bool = True,
    fetch_interval_minutes: int = 60,
    last_run_at: datetime | None = None,
    last_run_status: str | None = None,
) -> Source:
    return Source(
        id=cast(uuid.UUID, id if id is not _NOT_SET else uuid.uuid4()),
        name=name,
        source_type=source_type,
        url=url,
        is_active=is_active,
        fetch_interval_minutes=fetch_interval_minutes,
        last_run_at=last_run_at,
        last_run_status=last_run_status,
    )


@pytest.mark.asyncio
async def test_list_sources_returns_200() -> None:
    source = _make_source()
    mock_repo = MagicMock()
    mock_repo.list_all = AsyncMock(return_value=[source])

    app.dependency_overrides[deps.get_source_repo] = lambda: mock_repo
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/admin/sources/",
                headers={"HX-Request": "true"},
            )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert "Test Source" in response.text


@pytest.mark.asyncio
async def test_create_source_returns_partial_html() -> None:
    source = _make_source()
    mock_repo = MagicMock()
    mock_repo.save = AsyncMock(return_value=source)

    app.dependency_overrides[deps.get_source_repo] = lambda: mock_repo
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/admin/sources/",
                data={
                    "name": "New Source",
                    "source_type": "rss",
                    "url": "https://new.example.com",
                    "fetch_interval_minutes": 30,
                },
                headers={"HX-Request": "true"},
            )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert "Test Source" in response.text
    assert "source-" in response.text


@pytest.mark.asyncio
async def test_toggle_source_updates_status() -> None:
    source = _make_source(is_active=False)
    mock_repo = MagicMock()
    mock_repo.toggle_active = AsyncMock(return_value=source)

    app.dependency_overrides[deps.get_source_repo] = lambda: mock_repo
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.patch(
                f"/admin/sources/{source.id}/toggle",
                headers={"HX-Request": "true"},
            )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert "Inactiva" in response.text


# ---------------------------------------------------------------------------
# Test Integration (SSE streaming)
# ---------------------------------------------------------------------------


def _make_source_sse(source_id: uuid.UUID | None = None) -> Source:
    return Source(
        id=source_id or uuid.uuid4(),
        name="Test RSS",
        source_type=SourceType.RSS,
        url="https://example.com/rss",
    )


@pytest.mark.asyncio
async def test_test_integration_stream_source_not_found() -> None:
    mock_repo = AsyncMock(spec=SourceRepository)
    mock_repo.get.return_value = None

    from fastapi import FastAPI

    from hazlo.infrastructure.api.routes.admin_sources import router

    fastapi_app = FastAPI()
    fastapi_app.include_router(router, prefix="/admin/sources")
    fastapi_app.dependency_overrides[get_source_repo] = lambda: mock_repo

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/admin/sources/{uuid.uuid4()}/test/stream")
        assert response.status_code == 200
        body = response.text
        assert "event: log_entry" in body
        assert "event: complete" in body


@pytest.mark.asyncio
async def test_test_integration_stream_returns_event_stream() -> None:
    mock_repo = AsyncMock(spec=SourceRepository)
    mock_repo.get.return_value = _make_source_sse()

    from fastapi import FastAPI

    from hazlo.infrastructure.api.routes.admin_sources import router

    fastapi_app = FastAPI()
    fastapi_app.include_router(router, prefix="/admin/sources")
    fastapi_app.dependency_overrides[get_source_repo] = lambda: mock_repo

    with patch(
        "hazlo.application.use_cases.ingest_source.IngestSource.execute",
        new_callable=AsyncMock,
    ) as mock_execute:
        from hazlo.application.use_cases.ingest_source import IngestionResult

        mock_execute.return_value = IngestionResult(
            source_id=_make_source_sse().id,
            events_found=3,
            events_new=2,
            events_skipped=1,
        )

        transport = ASGITransport(app=fastapi_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/admin/sources/{_make_source_sse().id}/test/stream")
            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", "")
            body = response.text
            assert "event: log_entry" in body
            assert "event: complete" in body


@pytest.mark.asyncio
async def test_test_integration_handles_adapter_error() -> None:
    mock_repo = AsyncMock(spec=SourceRepository)
    mock_repo.get.return_value = _make_source_sse()

    from fastapi import FastAPI

    from hazlo.infrastructure.api.routes.admin_sources import router

    fastapi_app = FastAPI()
    fastapi_app.include_router(router, prefix="/admin/sources")
    fastapi_app.dependency_overrides[get_source_repo] = lambda: mock_repo

    with patch(
        "hazlo.application.use_cases.ingest_source.IngestSource.execute",
        new_callable=AsyncMock,
    ) as mock_execute:
        from hazlo.application.use_cases.ingest_source import IngestionResult

        mock_execute.return_value = IngestionResult(
            source_id=_make_source_sse().id,
            events_found=0,
            errors=["Connection timeout"],
        )

        transport = ASGITransport(app=fastapi_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/admin/sources/{_make_source_sse().id}/test/stream")
            assert response.status_code == 200
            body = response.text
            assert "event: log_entry" in body
            assert "event: complete" in body
