from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from hazlo.application.use_cases.review_event import InvalidTransitionError, ReviewEvent
from hazlo.domain.event import EventStatus
from hazlo.infrastructure.api.deps import get_db
from hazlo.infrastructure.db.repositories import EventRepository, ReviewRepository

router = APIRouter()


def _event_to_dict(event) -> dict:
    return {
        "id": event.id,
        "title": event.title,
        "status": event.status.value,
        "source_url": event.source_url,
        "is_children_activity": event.is_children_activity,
        "is_toddler_friendly": event.is_toddler_friendly,
        "location": {
            "address": event.location.address if event.location else "",
            "neighborhood": event.location.neighborhood if event.location else "",
            "metro": event.location.metro if event.location else None,
        }
        if event.location
        else None,
        "start_at": event.start_at,
        "end_at": event.end_at,
        "price": {
            "amount": str(event.price.amount) if event.price and event.price.amount else None,
            "is_free": event.price.is_free if event.price else False,
            "notes": event.price.notes if event.price else None,
        }
        if event.price
        else None,
    }


@router.get("/")
async def list_events(
    request: Request,
    status: str = "pending",
    db: AsyncSession = Depends(get_db),
):
    repo = EventRepository(db)
    try:
        event_status = EventStatus(status)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=f"Invalid status: {status}") from err

    events = await repo.list_by_status(event_status)
    event_dicts = [_event_to_dict(e) for e in events]

    return request.state.templates.TemplateResponse(
        request,
        "admin/events/list.html",
        {"events": event_dicts, "current_status": status},
    )


@router.get("/{event_id}")
async def get_event(
    request: Request,
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    repo = EventRepository(db)
    event = await repo.get(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    return request.state.templates.TemplateResponse(
        request,
        "admin/events/_event_card.html",
        {"event": _event_to_dict(event)},
    )


@router.get("/{event_id}/audit")
async def get_event_audit(
    request: Request,
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    repo = ReviewRepository(db)
    reviews = await repo.list_by_event(event_id)
    review_dicts = [
        {
            "id": r.id,
            "action": r.action.value,
            "reviewer_id": r.reviewer_id,
            "changes": r.changes,
            "reviewed_at": r.reviewed_at,
        }
        for r in reviews
    ]
    return request.state.templates.TemplateResponse(
        request,
        "admin/events/_audit_trail.html",
        {"reviews": review_dicts},
    )


@router.patch("/{event_id}/review")
async def review_event(
    request: Request,
    event_id: uuid.UUID,
    action: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    repo = EventRepository(db)
    event = await repo.get(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    use_case = ReviewEvent()
    try:
        updated, review = use_case.execute(
            event=event,
            reviewer_id=uuid.uuid4(),
            action=action,
        )
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await repo.save_with_review(updated, review)

    return request.state.templates.TemplateResponse(
        request,
        "admin/events/_event_card.html",
        {"event": _event_to_dict(updated)},
    )
