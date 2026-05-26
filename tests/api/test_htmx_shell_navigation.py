from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from hazlo.domain.event import Event, EventStatus, Location, Price, TicketInfo
from hazlo.domain.source import Source, SourceType
from hazlo.infrastructure.api import deps
from hazlo.infrastructure.db.models import LLMProviderModel
from hazlo.main import app


@pytest.mark.asyncio
async def test_sources_list_hx_request_returns_fragment_not_full_shell() -> None:
    source = Source(
        id=uuid.uuid4(),
        name="Test Source",
        source_type=SourceType.RSS,
        url="https://example.com",
    )
    mock_repo = MagicMock()
    mock_repo.list_all = AsyncMock(return_value=[source])

    app.dependency_overrides[deps.get_source_repo] = lambda: mock_repo
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/admin/sources/", headers={"HX-Request": "true", "HX-Target": "main-content"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "<html" not in response.text
    assert "<head" not in response.text
    assert "<body" not in response.text
    assert "<nav" not in response.text


@pytest.mark.asyncio
async def test_events_list_hx_request_returns_fragment_not_full_shell() -> None:
    event = Event(
        id=uuid.uuid4(),
        title="Test Event",
        location=Location(address="A", neighborhood="B", metro="C"),
        start_at=datetime(2026, 6, 1, 10, 0, tzinfo=UTC),
        end_at=datetime(2026, 6, 1, 12, 0, tzinfo=UTC),
        price=Price(amount_cents=0, is_free=True, notes=None),
        ticket_info=TicketInfo(url=None, notes=None),
        source_url="https://example.com/event",
        extracted_at=datetime(2026, 6, 1, 8, 0, tzinfo=UTC),
        status=EventStatus.PENDING,
    )

    mock_repo = MagicMock()
    mock_repo.list_by_status = AsyncMock(return_value=[event])

    app.dependency_overrides[deps.get_event_repo] = lambda: mock_repo
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/admin/events/?status=pending",
                headers={"HX-Request": "true", "HX-Target": "main-content"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "<html" not in response.text
    assert "<head" not in response.text
    assert "<body" not in response.text
    assert "<nav" not in response.text


@pytest.mark.asyncio
async def test_llm_providers_list_hx_request_returns_fragment_not_full_shell() -> None:
    now = datetime.now(UTC)
    provider = LLMProviderModel(
        id=uuid.uuid4(),
        name="Provider",
        provider_type="gemini",
        model="gemini-2.5-flash",
        api_key_encrypted="enc",
        is_active=True,
        priority=0,
        max_calls_per_run=100,
        cost_per_1k_tokens_micros=0,
        created_at=now,
        updated_at=now,
    )

    mock_repo = MagicMock()
    mock_repo.list_all = AsyncMock(return_value=[provider])

    app.dependency_overrides[deps.get_llm_provider_repo] = lambda: mock_repo
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/admin/llm-providers/",
                headers={"HX-Request": "true", "HX-Target": "main-content"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "<html" not in response.text
    assert "<head" not in response.text
    assert "<body" not in response.text
    assert "<nav" not in response.text
