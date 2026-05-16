from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hazlo.infrastructure.db.models import EventModel, ExtractionRunModel, SourceModel


class EventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, event: EventModel) -> EventModel:
        self._session.add(event)
        await self._session.commit()
        await self._session.refresh(event)
        return event

    async def get_by_id(self, event_id: uuid.UUID) -> EventModel | None:
        result = await self._session.execute(select(EventModel).where(EventModel.id == event_id))
        return result.scalar_one_or_none()

    async def list_all(self, *, limit: int = 50, offset: int = 0) -> list[EventModel]:
        result = await self._session.execute(
            select(EventModel).order_by(EventModel.created_at.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars().all())


class SourceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, source: SourceModel) -> SourceModel:
        self._session.add(source)
        await self._session.commit()
        await self._session.refresh(source)
        return source

    async def get_by_id(self, source_id: uuid.UUID) -> SourceModel | None:
        result = await self._session.execute(select(SourceModel).where(SourceModel.id == source_id))
        return result.scalar_one_or_none()

    async def list_all(self) -> list[SourceModel]:
        result = await self._session.execute(select(SourceModel).order_by(SourceModel.name))
        return list(result.scalars().all())


class ExtractionRunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, run: ExtractionRunModel) -> ExtractionRunModel:
        self._session.add(run)
        await self._session.commit()
        await self._session.refresh(run)
        return run
