from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Request

from hazlo.application.use_cases.review_event import InvalidTransitionError, ReviewEvent
from hazlo.domain.event import EventStatus
from hazlo.infrastructure.api.deps import get_event_repo, get_review_repo
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
        "confidence_score": event.confidence_score,
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
            "amount_cents": event.price.amount_cents if event.price and event.price.amount_cents is not None else None,
            "is_free": event.price.is_free if event.price else False,
            "notes": event.price.notes if event.price else None,
        }
        if event.price
        else None,
    }


PAGE_SIZE = 20


@router.get("/")
async def list_events(
    request: Request,
    status: str = "pending",
    confidence: str = "",
    page: int = 1,
    event_repo: EventRepository = Depends(get_event_repo),
):
    try:
        event_status = EventStatus(status)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=f"Invalid status: {status}") from err

    offset = (page - 1) * PAGE_SIZE
    events = await event_repo.list_by_status(event_status, limit=PAGE_SIZE, offset=offset)
    event_dicts = [_event_to_dict(e) for e in events]

    if confidence:
        event_dicts = _filter_by_confidence(event_dicts, confidence)

    has_more = len(event_dicts) == PAGE_SIZE

    return request.state.templates.TemplateResponse(
        request,
        "admin/events/list.html",
        {
            "events": event_dicts,
            "current_status": status,
            "confidence_filter": confidence,
            "page": page,
            "has_more": has_more,
            "page_size": PAGE_SIZE,
        },
    )


def _filter_by_confidence(events: list[dict], filter_value: str) -> list[dict]:
    match filter_value:
        case "high":
            return [e for e in events if e.get("confidence_score") is not None and e["confidence_score"] >= 0.9]
        case "medium":
            return [e for e in events if e.get("confidence_score") is not None and 0.7 <= e["confidence_score"] < 0.9]
        case "low":
            return [e for e in events if e.get("confidence_score") is not None and e["confidence_score"] < 0.7]
        case "none":
            return [e for e in events if e.get("confidence_score") is None]
        case _:
            return events


@router.get("/{event_id}")
async def get_event(
    request: Request,
    event_id: uuid.UUID,
    event_repo: EventRepository = Depends(get_event_repo),
):
    event = await event_repo.get(event_id)
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
    review_repo: ReviewRepository = Depends(get_review_repo),
):
    reviews = await review_repo.list_by_event(event_id)
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
    event_repo: EventRepository = Depends(get_event_repo),
):
    event = await event_repo.get(event_id)
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

    await event_repo.save_with_review(updated, review)

    return request.state.templates.TemplateResponse(
        request,
        "admin/events/_event_card.html",
        {"event": _event_to_dict(updated)},
    )
