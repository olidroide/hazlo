from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from hazlo.infrastructure.api.deps import get_db
from hazlo.infrastructure.db.repositories import EventRepository

router = APIRouter()


class EventResponse(BaseModel):
    model_config = ConfigDict(strict=True)

    id: uuid.UUID
    title: str
    status: str
    source_url: str | None = None
    is_children_activity: bool
    is_toddler_friendly: bool


@router.get("/", response_model=list[EventResponse])
async def list_events(db: AsyncSession = Depends(get_db)) -> list[EventResponse]:
    repo = EventRepository(db)
    events = await repo.list_all()
    return [
        EventResponse(
            id=e.id,
            title=e.title,
            status=e.status,
            source_url=e.source_url,
            is_children_activity=e.is_children_activity,
            is_toddler_friendly=e.is_toddler_friendly,
        )
        for e in events
    ]


@router.get("/{event_id}", response_model=EventResponse)
async def get_event(event_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> EventResponse:
    repo = EventRepository(db)
    event = await repo.get_by_id(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return EventResponse(
        id=event.id,
        title=event.title,
        status=event.status,
        source_url=event.source_url,
        is_children_activity=event.is_children_activity,
        is_toddler_friendly=event.is_toddler_friendly,
    )
