"""Tests for event detail endpoint."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from hazlo.domain.event import Event, EventStatus, Location, Price, TicketInfo
from hazlo.infrastructure.api import deps
from hazlo.main import app

_NOT_SET = object()


def _make_event(
    id: uuid.UUID | object = _NOT_SET,
    title: str = "Test Event Detail",
    location: Location | object = _NOT_SET,
    start_at: datetime | object = _NOT_SET,
    end_at: datetime | object = _NOT_SET,
    price: Price | object = _NOT_SET,
    ticket_info: TicketInfo | object = _NOT_SET,
    is_children_activity: bool = False,
    is_toddler_friendly: bool = False,
    confidence_score: float | None = None,
    agent_review: dict | None = None,
    source_url: str = "https://source.example.com/event",
    extracted_at: datetime | object = _NOT_SET,
    status: EventStatus = EventStatus.PENDING,
    content_hash: str | None = None,
    idempotency_key: str | None = None,
) -> Event:
    return Event(
        id=cast(uuid.UUID, id if id is not _NOT_SET else uuid.uuid4()),
        title=title,
        location=cast(
            Location,
            location
            if location is not _NOT_SET
            else Location(address="Test Street 123", neighborhood="Test Barrio", metro="Test Metro"),
        ),
        start_at=cast(datetime, start_at if start_at is not _NOT_SET else datetime(2026, 6, 1, 20, 0, tzinfo=UTC)),
        end_at=cast(datetime, end_at if end_at is not _NOT_SET else datetime(2026, 6, 1, 22, 0, tzinfo=UTC)),
        price=cast(
            Price,
            price if price is not _NOT_SET else Price(amount_cents=2500, is_free=False, notes="Early bird"),
        ),
        ticket_info=cast(
            TicketInfo,
            ticket_info
            if ticket_info is not _NOT_SET
            else TicketInfo(url="https://tickets.example.com/event123", notes="Online only"),
        ),
        is_children_activity=is_children_activity,
        is_toddler_friendly=is_toddler_friendly,
        confidence_score=confidence_score,
        agent_review=agent_review,
        source_url=source_url,
        extracted_at=cast(
            datetime, extracted_at if extracted_at is not _NOT_SET else datetime(2026, 5, 26, 10, 0, tzinfo=UTC)
        ),
        status=status,
        content_hash=content_hash,
        idempotency_key=idempotency_key,
    )


@pytest.mark.asyncio
async def test_get_event_detail_returns_200() -> None:
    """Test that GET /{event_id}/detail returns 200."""
    event = _make_event()
    mock_repo = MagicMock()
    mock_repo.get = AsyncMock(return_value=event)

    app.dependency_overrides[deps.get_event_repo] = lambda: mock_repo
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                f"/admin/events/{event.id}/detail",
                headers={"HX-Request": "true"},
            )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_event_detail_contains_title() -> None:
    """Test that detail view contains event title."""
    event = _make_event(title="Concierto de Jazz")
    mock_repo = MagicMock()
    mock_repo.get = AsyncMock(return_value=event)

    app.dependency_overrides[deps.get_event_repo] = lambda: mock_repo
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                f"/admin/events/{event.id}/detail",
                headers={"HX-Request": "true"},
            )
    finally:
        app.dependency_overrides.clear()
    assert "Concierto de Jazz" in response.text


@pytest.mark.asyncio
async def test_get_event_detail_contains_location() -> None:
    """Test that detail view contains location details."""
    event = _make_event(
        location=Location(address="Calle Mayor 1", neighborhood="Centro", metro="Sol"),
    )
    mock_repo = MagicMock()
    mock_repo.get = AsyncMock(return_value=event)

    app.dependency_overrides[deps.get_event_repo] = lambda: mock_repo
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                f"/admin/events/{event.id}/detail",
                headers={"HX-Request": "true"},
            )
    finally:
        app.dependency_overrides.clear()
    assert "Calle Mayor 1" in response.text
    assert "Centro" in response.text
    assert "Sol" in response.text


@pytest.mark.asyncio
async def test_get_event_detail_contains_price() -> None:
    """Test that detail view contains formatted price."""
    event = _make_event(price=Price(amount_cents=2500, is_free=False, notes="Early bird"))
    mock_repo = MagicMock()
    mock_repo.get = AsyncMock(return_value=event)

    app.dependency_overrides[deps.get_event_repo] = lambda: mock_repo
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                f"/admin/events/{event.id}/detail",
                headers={"HX-Request": "true"},
            )
    finally:
        app.dependency_overrides.clear()
    assert "25.00€" in response.text
    assert "Early bird" in response.text


@pytest.mark.asyncio
async def test_get_event_detail_contains_ticket_info() -> None:
    """Test that detail view contains ticket info."""
    event = _make_event(
        ticket_info=TicketInfo(url="https://tickets.example.com/123", notes="Online only"),
    )
    mock_repo = MagicMock()
    mock_repo.get = AsyncMock(return_value=event)

    app.dependency_overrides[deps.get_event_repo] = lambda: mock_repo
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                f"/admin/events/{event.id}/detail",
                headers={"HX-Request": "true"},
            )
    finally:
        app.dependency_overrides.clear()
    assert "https://tickets.example.com/123" in response.text
    assert "Online only" in response.text


@pytest.mark.asyncio
async def test_get_event_detail_contains_classification() -> None:
    """Test that detail view contains classification badges."""
    event = _make_event(is_children_activity=True, is_toddler_friendly=True)
    mock_repo = MagicMock()
    mock_repo.get = AsyncMock(return_value=event)

    app.dependency_overrides[deps.get_event_repo] = lambda: mock_repo
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                f"/admin/events/{event.id}/detail",
                headers={"HX-Request": "true"},
            )
    finally:
        app.dependency_overrides.clear()
    assert "Infantil" in response.text
    assert "Bebés" in response.text


@pytest.mark.asyncio
async def test_get_event_detail_contains_confidence_score() -> None:
    """Test that detail view shows confidence score."""
    event = _make_event(confidence_score=0.85)
    mock_repo = MagicMock()
    mock_repo.get = AsyncMock(return_value=event)

    app.dependency_overrides[deps.get_event_repo] = lambda: mock_repo
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                f"/admin/events/{event.id}/detail",
                headers={"HX-Request": "true"},
            )
    finally:
        app.dependency_overrides.clear()
    assert "85%" in response.text


@pytest.mark.asyncio
async def test_get_event_detail_contains_agent_review() -> None:
    """Test that detail view contains agent review section."""
    event = _make_event(
        agent_review={"raw_response": "Test LLM response", "reasoning": "Test reasoning"},
    )
    mock_repo = MagicMock()
    mock_repo.get = AsyncMock(return_value=event)

    app.dependency_overrides[deps.get_event_repo] = lambda: mock_repo
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                f"/admin/events/{event.id}/detail",
                headers={"HX-Request": "true"},
            )
    finally:
        app.dependency_overrides.clear()
    assert "Respuesta del clasificador" in response.text
    assert "Test LLM response" in response.text


@pytest.mark.asyncio
async def test_get_event_detail_contains_metadata() -> None:
    """Test that detail view contains metadata fields."""
    event = _make_event(
        source_url="https://example.com/event/456",
        content_hash="abc123def456789",
        idempotency_key="key123456789",
    )
    mock_repo = MagicMock()
    mock_repo.get = AsyncMock(return_value=event)

    app.dependency_overrides[deps.get_event_repo] = lambda: mock_repo
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                f"/admin/events/{event.id}/detail",
                headers={"HX-Request": "true"},
            )
    finally:
        app.dependency_overrides.clear()
    assert "https://example.com/event/456" in response.text
    assert "abc123def456789"[:16] in response.text
    assert "key123456789"[:16] in response.text


@pytest.mark.asyncio
async def test_get_event_detail_not_found() -> None:
    """Test that GET /{event_id}/detail returns 404 for non-existent event."""
    mock_repo = MagicMock()
    mock_repo.get = AsyncMock(return_value=None)

    app.dependency_overrides[deps.get_event_repo] = lambda: mock_repo
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                f"/admin/events/{uuid.uuid4()}/detail",
                headers={"HX-Request": "true"},
            )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 404
