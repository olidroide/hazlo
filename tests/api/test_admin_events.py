from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from hazlo.domain.event import Event, EventStatus, Location, Price, TicketInfo
from hazlo.main import app


def _make_event(**kwargs: object) -> Event:
    return Event(
        id=kwargs.get("id", uuid.uuid4()),
        title=kwargs.get("title", "Test Event"),
        location=kwargs.get("location", Location(address="Calle Mayor 1", neighborhood="Centro", metro="Sol")),
        start_at=kwargs.get("start_at", datetime(2026, 6, 1, 20, 0, tzinfo=UTC)),
        end_at=kwargs.get("end_at", datetime(2026, 6, 1, 22, 0, tzinfo=UTC)),
        price=kwargs.get("price", Price(amount=Decimal("10.00"), is_free=False, notes=None)),
        ticket_info=kwargs.get("ticket_info", TicketInfo(url="https://tickets.example.com", notes=None)),
        is_children_activity=kwargs.get("is_children_activity", False),
        is_toddler_friendly=kwargs.get("is_toddler_friendly", False),
        source_url=kwargs.get("source_url", "https://source.example.com/event"),
        extracted_at=kwargs.get("extracted_at", datetime(2026, 5, 16, 10, 0, tzinfo=UTC)),
        status=kwargs.get("status", EventStatus.PENDING),
    )


@pytest.mark.asyncio
async def test_list_pending_events() -> None:
    event = _make_event()
    mock_repo = MagicMock()
    mock_repo.list_by_status = AsyncMock(return_value=[event])

    with patch("hazlo.infrastructure.api.routes.admin_events.EventRepository", return_value=mock_repo):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/admin/events/?status=pending",
                headers={"HX-Request": "true"},
            )
    assert response.status_code == 200
    assert "Test Event" in response.text


@pytest.mark.asyncio
async def test_approve_event_changes_status() -> None:
    event = _make_event(status=EventStatus.PENDING)
    approved_event = _make_event(id=event.id, status=EventStatus.APPROVED)
    mock_repo = MagicMock()
    mock_repo.get = AsyncMock(return_value=event)
    mock_repo.save_with_review = AsyncMock(return_value=(approved_event, MagicMock()))

    with patch("hazlo.infrastructure.api.routes.admin_events.EventRepository", return_value=mock_repo):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.patch(
                f"/admin/events/{event.id}/review",
                data={"action": "approve"},
                headers={"HX-Request": "true"},
            )
    assert response.status_code == 200
    assert "approved" in response.text.lower()


@pytest.mark.asyncio
async def test_reject_event_changes_status() -> None:
    event = _make_event(status=EventStatus.PENDING)
    rejected_event = _make_event(id=event.id, status=EventStatus.REJECTED)
    mock_repo = MagicMock()
    mock_repo.get = AsyncMock(return_value=event)
    mock_repo.save_with_review = AsyncMock(return_value=(rejected_event, MagicMock()))

    with patch("hazlo.infrastructure.api.routes.admin_events.EventRepository", return_value=mock_repo):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.patch(
                f"/admin/events/{event.id}/review",
                data={"action": "reject"},
                headers={"HX-Request": "true"},
            )
    assert response.status_code == 200
    assert "rejected" in response.text.lower()
