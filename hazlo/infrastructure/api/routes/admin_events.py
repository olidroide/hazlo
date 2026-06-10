from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Request

from hazlo.application.use_cases.review_event import InvalidTransitionError, ReviewEvent
from hazlo.domain.event import EventStatus
from hazlo.infrastructure.api.deps import get_base, get_event_repo, get_review_repo
from hazlo.infrastructure.db.repositories import EventRepository, ReviewRepository
from hazlo.settings import get_settings

logger = logging.getLogger(__name__)
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
        "ticket_info": {
            "url": event.ticket_info.url if event.ticket_info else None,
            "notes": event.ticket_info.notes if event.ticket_info else None,
        }
        if event.ticket_info
        else None,
        "extracted_at": event.extracted_at,
        "created_at": event.created_at,
        "updated_at": event.updated_at,
        "agent_review": event.agent_review,
        "content_hash": event.content_hash,
        "idempotency_key": event.idempotency_key,
        "is_expired": event.is_expired,
    }


PAGE_SIZE = 20


@router.get("/")
async def list_events(
    request: Request,
    status: str = "pending",
    confidence: str = "",
    page: int = 1,
    include_expired: bool = False,
    event_repo: EventRepository = Depends(get_event_repo),
):
    try:
        event_status = EventStatus(status)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=f"Invalid status: {status}") from err

    offset = (page - 1) * PAGE_SIZE
    sort_by = "start_at" if status == "pending" else "created_at"
    events = await event_repo.list_by_status(
        event_status,
        limit=PAGE_SIZE,
        offset=offset,
        include_expired=include_expired,
        sort_by=sort_by,
    )
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
            "include_expired": include_expired,
            "base": get_base(request),
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


@router.get("/{event_id}/detail")
async def get_event_detail(
    request: Request,
    event_id: uuid.UUID,
    event_repo: EventRepository = Depends(get_event_repo),
):
    event = await event_repo.get(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    return request.state.templates.TemplateResponse(
        request,
        "admin/events/_event_detail.html",
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


@router.post("/{event_id}/enrich")
async def enrich_event(
    request: Request,
    event_id: uuid.UUID,
    event_repo: EventRepository = Depends(get_event_repo),
):
    event = await event_repo.get(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Evento no encontrado")

    loc = event.location
    logger.info(
        "Enriching event %s: %s (address=%s, neighborhood=%s, metro=%s)",
        event.id,
        event.title,
        loc.address if loc else "",
        loc.neighborhood if loc else "",
        loc.metro if loc else "",
    )

    from hazlo.infrastructure.db.session import async_session_factory
    from hazlo.infrastructure.llm.factory import build_llm_infrastructure

    async with async_session_factory() as session:
        _, _, llm_enrichment, _ = await build_llm_infrastructure(session)

    if llm_enrichment is None:
        logger.warning("LLM enrichment not available for event %s", event.id)
        return request.state.templates.TemplateResponse(
            request,
            "admin/events/_event_card.html",
            {"event": _event_to_dict(event)},
        )

    enriched = await llm_enrichment.enrich_location(event)

    old_loc = event.location
    new_loc = enriched.location
    logger.info(
        "Enrichment result for %s: address='%s'→'%s', neighborhood='%s'→'%s', metro='%s'→'%s'",
        event.id,
        old_loc.address if old_loc else "",
        new_loc.address if new_loc else "",
        old_loc.neighborhood if old_loc else "",
        new_loc.neighborhood if new_loc else "",
        old_loc.metro if old_loc else "",
        new_loc.metro if new_loc else "",
    )

    await event_repo.save(enriched)
    logger.info("Event %s saved after enrichment", event.id)
    return request.state.templates.TemplateResponse(
        request,
        "admin/events/_event_card.html",
        {"event": _event_to_dict(enriched)},
    )


@router.get("/{event_id}")
async def get_event_detail_page(
    request: Request,
    event_id: uuid.UUID,
    event_repo: EventRepository = Depends(get_event_repo),
):
    """Full event detail page."""
    event = await event_repo.get(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    return request.state.templates.TemplateResponse(
        request,
        "admin/events/event_detail.html",
        {
            "event": _event_to_dict(event),
            "base": get_base(request),
            "unified_reparse": get_settings().unified_reparse,
        },
    )


@router.post("/{event_id}/edit")
async def edit_event(
    request: Request,
    event_id: uuid.UUID,
    title: str = Form(default=""),
    description: str = Form(default=""),
    address: str = Form(default=""),
    neighborhood: str = Form(default=""),
    metro: str = Form(default=""),
    start_at: str = Form(default=""),
    end_at: str = Form(default=""),
    price_amount_cents: str = Form(default=""),
    is_free: str = Form(default="false"),
    price_notes: str = Form(default=""),
    ticket_url: str = Form(default=""),
    ticket_notes: str = Form(default=""),
    is_children_activity: str = Form(default="false"),
    is_toddler_friendly: str = Form(default="false"),
    event_repo: EventRepository = Depends(get_event_repo),
):
    """Save manual event edits."""
    from datetime import datetime as dt

    from hazlo.application.use_cases.edit_event import EditEvent, EditEventCommand

    event = await event_repo.get(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    command = EditEventCommand(
        title=title or None,
        description=description or None,
        address=address or None,
        neighborhood=neighborhood or None,
        metro=metro or None,
        start_at=dt.fromisoformat(start_at) if start_at else None,
        end_at=dt.fromisoformat(end_at) if end_at else None,
        price_amount_cents=int(price_amount_cents) if price_amount_cents else None,
        is_free=is_free == "true",
        price_notes=price_notes or None,
        ticket_url=ticket_url or None,
        ticket_notes=ticket_notes or None,
        is_children_activity=is_children_activity == "true",
        is_toddler_friendly=is_toddler_friendly == "true",
    )

    use_case = EditEvent()
    result = use_case.execute(event, command)
    await event_repo.save_with_review(result.event, result.review)

    logger.info("Event %s edited: %s", event_id, result.fields_changed)
    return request.state.templates.TemplateResponse(
        request,
        "admin/events/event_detail.html",
        {
            "event": _event_to_dict(result.event),
            "base": get_base(request),
            "edit_success": True,
            "unified_reparse": get_settings().unified_reparse,
        },
    )


@router.post("/{event_id}/reparse")
async def reparse_event(
    request: Request,
    event_id: uuid.UUID,
    event_repo: EventRepository = Depends(get_event_repo),
):
    """Reparse event from stored RAW using unified LLM agent."""
    from hazlo.application.use_cases.reparse_event import RawDocForReparse, ReparseEvent
    from hazlo.infrastructure.api.middleware.rate_limiter import reparse_limiter
    from hazlo.infrastructure.db.session import async_session_factory
    from hazlo.infrastructure.llm.factory import build_llm_infrastructure
    from hazlo.infrastructure.storage.factory import build_raw_document_store

    event = await event_repo.get(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    settings = get_settings()
    if not settings.unified_reparse:
        raise HTTPException(status_code=403, detail="Unified reparse is disabled")

    reparse_limiter.check("admin", event_id)

    async with async_session_factory() as session:
        _, _, _, _ = await build_llm_infrastructure(session)
        store = build_raw_document_store(settings)

    if not store.exists(event_id):
        logger.warning("No RAW document for event %s", event_id)
        return request.state.templates.TemplateResponse(
            request,
            "admin/events/event_detail.html",
            {
                "event": _event_to_dict(event),
                "base": get_base(request),
                "reparse_error": "No RAW document found",
                "unified_reparse": settings.unified_reparse,
            },
        )

    raw_doc = store.read(event_id)
    raw_doc_for_reparse = RawDocForReparse(
        payload=raw_doc.payload,
        body=raw_doc.body if isinstance(raw_doc.body, bytes) else raw_doc.body.encode("utf-8"),
    )

    from hazlo.infrastructure.llm.agents.reparse_event import ReparseEventAgent
    from hazlo.infrastructure.llm.factory import build_llm_infrastructure

    async with async_session_factory() as session:
        classifier, _, _, _ = await build_llm_infrastructure(session)

    if classifier is None:
        logger.warning("No LLM provider for reparse event %s", event_id)
        return request.state.templates.TemplateResponse(
            request,
            "admin/events/event_detail.html",
            {
                "event": _event_to_dict(event),
                "base": get_base(request),
                "reparse_error": "No LLM provider configured",
                "unified_reparse": settings.unified_reparse,
            },
        )

    from typing import cast

    from pydantic_ai.models import Model

    model = cast(Model, classifier._agent._model)
    agent = ReparseEventAgent(model, retries=1)

    class _RawStore:
        def read(self, event_id: uuid.UUID) -> RawDocForReparse:
            return raw_doc_for_reparse

    use_case = ReparseEvent(agent=agent, raw_store=_RawStore())

    result = await use_case.execute(event)
    await event_repo.save_with_review(result.event, result.review)

    logger.info("Event %s reparsed: %s", event_id, result.fields_changed)
    return request.state.templates.TemplateResponse(
        request,
        "admin/events/event_detail.html",
        {
            "event": _event_to_dict(result.event),
            "base": get_base(request),
            "reparse_success": True,
            "reparse_reasoning": result.reasoning,
            "unified_reparse": settings.unified_reparse,
        },
    )
