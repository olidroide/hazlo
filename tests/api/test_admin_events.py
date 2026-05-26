from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from hazlo.domain.event import Event, EventStatus, Location, Price, TicketInfo
from hazlo.infrastructure.api import deps
from hazlo.main import app

_NOT_SET = object()


def _make_event(
    id: uuid.UUID | object = _NOT_SET,
    title: str = "Test Event",
    location: Location | object = _NOT_SET,
    start_at: datetime | object = _NOT_SET,
    end_at: datetime | object = _NOT_SET,
    price: Price | object = _NOT_SET,
    ticket_info: TicketInfo | object = _NOT_SET,
    is_children_activity: bool = False,
    is_toddler_friendly: bool = False,
    source_url: str = "https://source.example.com/event",
    extracted_at: datetime | object = _NOT_SET,
    status: EventStatus = EventStatus.PENDING,
) -> Event:
    return Event(
        id=cast(uuid.UUID, id if id is not _NOT_SET else uuid.uuid4()),
        title=title,
        location=cast(
            Location,
            location
            if location is not _NOT_SET
            else Location(address="Calle Mayor 1", neighborhood="Centro", metro="Sol"),
        ),
        start_at=cast(datetime, start_at if start_at is not _NOT_SET else datetime(2026, 6, 1, 20, 0, tzinfo=UTC)),
        end_at=cast(datetime, end_at if end_at is not _NOT_SET else datetime(2026, 6, 1, 22, 0, tzinfo=UTC)),
        price=cast(Price, price if price is not _NOT_SET else Price(amount_cents=1000, is_free=False, notes=None)),
        ticket_info=cast(
            TicketInfo,
            ticket_info if ticket_info is not _NOT_SET else TicketInfo(url="https://tickets.example.com", notes=None),
        ),
        is_children_activity=is_children_activity,
        is_toddler_friendly=is_toddler_friendly,
        source_url=source_url,
        extracted_at=cast(
            datetime, extracted_at if extracted_at is not _NOT_SET else datetime(2026, 5, 16, 10, 0, tzinfo=UTC)
        ),
        status=status,
    )


@pytest.mark.asyncio
async def test_list_pending_events() -> None:
    event = _make_event()
    mock_repo = MagicMock()
    mock_repo.list_by_status = AsyncMock(return_value=[event])

    app.dependency_overrides[deps.get_event_repo] = lambda: mock_repo
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/admin/events/?status=pending",
                headers={"HX-Request": "true"},
            )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert "Test Event" in response.text


@pytest.mark.asyncio
async def test_approve_event_changes_status() -> None:
    event = _make_event(status=EventStatus.PENDING)
    approved_event = _make_event(id=event.id, status=EventStatus.APPROVED)
    mock_repo = MagicMock()
    mock_repo.get = AsyncMock(return_value=event)
    mock_repo.save_with_review = AsyncMock(return_value=(approved_event, MagicMock()))

    app.dependency_overrides[deps.get_event_repo] = lambda: mock_repo
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.patch(
                f"/admin/events/{event.id}/review",
                data={"action": "approve"},
                headers={"HX-Request": "true"},
            )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert "approved" in response.text.lower()


@pytest.mark.asyncio
async def test_reject_event_changes_status() -> None:
    event = _make_event(status=EventStatus.PENDING)
    rejected_event = _make_event(id=event.id, status=EventStatus.REJECTED)
    mock_repo = MagicMock()
    mock_repo.get = AsyncMock(return_value=event)
    mock_repo.save_with_review = AsyncMock(return_value=(rejected_event, MagicMock()))

    app.dependency_overrides[deps.get_event_repo] = lambda: mock_repo
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.patch(
                f"/admin/events/{event.id}/review",
                data={"action": "reject"},
                headers={"HX-Request": "true"},
            )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert "rejected" in response.text.lower()


@pytest.mark.asyncio
async def test_enrich_event_with_llm_enriches_location() -> None:
    event = _make_event(
        status=EventStatus.PENDING,
        location=Location(address="Calle Mayor 1", neighborhood="", metro=None),
    )
    enriched_event = _make_event(
        id=event.id,
        status=EventStatus.PENDING,
        location=Location(address="Calle Mayor 1", neighborhood="Centro", metro="Sol"),
    )
    mock_repo = MagicMock()
    mock_repo.get = AsyncMock(return_value=event)
    mock_repo.save = AsyncMock(return_value=enriched_event)

    mock_agent = AsyncMock()
    mock_agent.enrich_location = AsyncMock(return_value=enriched_event)

    app.dependency_overrides[deps.get_event_repo] = lambda: mock_repo
    try:
        with patch(
            "hazlo.infrastructure.llm.factory.build_llm_infrastructure",
            AsyncMock(return_value=(None, MagicMock(), mock_agent, None)),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    f"/admin/events/{event.id}/enrich",
                    headers={"HX-Request": "true"},
                )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert "Centro" in response.text
    assert "Calle Mayor 1" in response.text
    mock_repo.save.assert_called_once()


@pytest.mark.asyncio
async def test_enrich_event_without_llm_returns_unchanged() -> None:
    event = _make_event(status=EventStatus.PENDING)
    mock_repo = MagicMock()
    mock_repo.get = AsyncMock(return_value=event)

    app.dependency_overrides[deps.get_event_repo] = lambda: mock_repo
    try:
        with patch(
            "hazlo.infrastructure.llm.factory.build_llm_infrastructure",
            AsyncMock(return_value=(None, MagicMock(), None, None)),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    f"/admin/events/{event.id}/enrich",
                    headers={"HX-Request": "true"},
                )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    mock_repo.save.assert_not_called()


@pytest.mark.asyncio
async def test_enrich_event_not_found_returns_404() -> None:
    mock_repo = MagicMock()
    mock_repo.get = AsyncMock(return_value=None)

    app.dependency_overrides[deps.get_event_repo] = lambda: mock_repo
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/admin/events/{uuid.uuid4()}/enrich",
                headers={"HX-Request": "true"},
            )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_pending_events_excludes_expired_by_default() -> None:
    event = _make_event()
    mock_repo = MagicMock()
    mock_repo.list_by_status = AsyncMock(return_value=[event])

    app.dependency_overrides[deps.get_event_repo] = lambda: mock_repo
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/admin/events/?status=pending")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    mock_repo.list_by_status.assert_called_once()
    call_kwargs = mock_repo.list_by_status.call_args[1]
    assert call_kwargs["include_expired"] is False


@pytest.mark.asyncio
async def test_list_pending_events_includes_expired_when_requested() -> None:
    event = _make_event()
    mock_repo = MagicMock()
    mock_repo.list_by_status = AsyncMock(return_value=[event])

    app.dependency_overrides[deps.get_event_repo] = lambda: mock_repo
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/admin/events/?status=pending&include_expired=true")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    call_kwargs = mock_repo.list_by_status.call_args[1]
    assert call_kwargs["include_expired"] is True
