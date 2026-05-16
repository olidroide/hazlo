from __future__ import annotations

import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from hazlo.domain.event import Event, EventStatus
from hazlo.domain.source import Source
from hazlo.infrastructure.db.models import (
    EventModel,
    SourceModel,
    event_to_model,
    model_to_event,
    model_to_source,
    source_to_model,
)


class EventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, event_id: uuid.UUID) -> Event | None:
        result = await self._session.execute(select(EventModel).where(EventModel.id == event_id))
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return model_to_event(model)

    async def list_by_status(
        self,
        status: EventStatus,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Event]:
        result = await self._session.execute(
            select(EventModel)
            .where(EventModel.status == status.value)
            .order_by(EventModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [model_to_event(m) for m in result.scalars().all()]

    async def save(self, event: Event) -> Event:
        model = event_to_model(event)
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return model_to_event(model)

    async def update_status(self, event_id: uuid.UUID, status: EventStatus) -> Event | None:
        from hazlo.infrastructure.db.models import _utcnow

        stmt = (
            update(EventModel)
            .where(EventModel.id == event_id)
            .values(status=status.value, updated_at=_utcnow())
            .returning(EventModel)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        await self._session.commit()
        return model_to_event(model)


class SourceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, source_id: uuid.UUID) -> Source | None:
        result = await self._session.execute(select(SourceModel).where(SourceModel.id == source_id))
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return model_to_source(model)

    async def list_all(self) -> list[Source]:
        result = await self._session.execute(select(SourceModel).order_by(SourceModel.name))
        return [model_to_source(m) for m in result.scalars().all()]

    async def save(self, source: Source) -> Source:
        model = source_to_model(source)
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return model_to_source(model)

    async def update_last_run(self, source_id: uuid.UUID, status: str) -> Source | None:
        from hazlo.infrastructure.db.models import _utcnow

        stmt = (
            update(SourceModel)
            .where(SourceModel.id == source_id)
            .values(last_run_status=status, last_run_at=_utcnow())
            .returning(SourceModel)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        await self._session.commit()
        return model_to_source(model)
