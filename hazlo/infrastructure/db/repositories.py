from __future__ import annotations

import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from hazlo.domain.event import Event, EventStatus
from hazlo.domain.review import Review
from hazlo.domain.source import Source
from hazlo.infrastructure.db.models import (
    EventModel,
    ExtractionRunModel,
    LLMProviderModel,
    ReviewModel,
    SourceModel,
    event_to_model,
    model_to_event,
    model_to_review,
    model_to_source,
    review_to_model,
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
        include_expired: bool = True,
        sort_by: str = "created_at",
    ) -> list[Event]:
        order_col = EventModel.start_at if sort_by == "start_at" else EventModel.created_at
        stmt = (
            select(EventModel)
            .where(EventModel.status == status.value)
            .order_by(order_col.asc() if sort_by == "start_at" else order_col.desc())
            .limit(limit)
            .offset(offset)
        )
        if not include_expired:
            stmt = stmt.where(~EventModel.is_expired)
        result = await self._session.execute(stmt)
        return [model_to_event(m) for m in result.scalars().all()]

    async def list_existing_urls_for_dedup(self) -> set[str]:
        result = await self._session.execute(select(EventModel.source_url))
        return {url for url in result.scalars().all() if url}

    async def exists_by_idempotency_key(self, idempotency_key: str) -> bool:
        result = await self._session.execute(
            select(EventModel.id).where(EventModel.idempotency_key == idempotency_key).limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def list_existing_idempotency_keys(self, keys: set[str]) -> set[str]:
        if not keys:
            return set()
        result = await self._session.execute(
            select(EventModel.idempotency_key).where(EventModel.idempotency_key.in_(keys))
        )
        return {k for k in result.scalars().all() if k is not None}

    async def exists_by_content_hash(self, content_hash: str | None) -> bool:
        if content_hash is None:
            return False
        result = await self._session.execute(
            select(EventModel.id).where(EventModel.content_hash == content_hash).limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def list_existing_content_hashes(self, hashes: set[str]) -> set[str]:
        if not hashes:
            return set()
        result = await self._session.execute(select(EventModel.content_hash).where(EventModel.content_hash.in_(hashes)))
        return {h for h in result.scalars().all() if h is not None}

    async def save(self, event: Event) -> Event:
        dialect = self._session.bind.dialect.name

        if dialect == "postgresql":
            from sqlalchemy.dialects.postgresql import insert

            model = event_to_model(event)
            stmt = insert(EventModel).values(
                id=model.id,
                title=model.title,
                location=model.location,
                start_at=model.start_at,
                end_at=model.end_at,
                price=model.price,
                ticket_info=model.ticket_info,
                is_children_activity=model.is_children_activity,
                is_toddler_friendly=model.is_toddler_friendly,
                confidence_score=model.confidence_score,
                agent_review=model.agent_review,
                source_url=model.source_url,
                extracted_at=model.extracted_at,
                status=model.status,
                source_id=model.source_id,
                idempotency_key=model.idempotency_key,
                content_hash=model.content_hash,
                is_expired=model.is_expired,
                created_at=model.created_at,
                updated_at=model.updated_at,
            )

            # Upsert: if source_url exists, update the event
            stmt = stmt.on_conflict_do_update(
                index_elements=["source_url"],
                set_={
                    "title": stmt.excluded.title,
                    "location": stmt.excluded.location,
                    "start_at": stmt.excluded.start_at,
                    "end_at": stmt.excluded.end_at,
                    "price": stmt.excluded.price,
                    "ticket_info": stmt.excluded.ticket_info,
                    "is_children_activity": stmt.excluded.is_children_activity,
                    "is_toddler_friendly": stmt.excluded.is_toddler_friendly,
                    "confidence_score": stmt.excluded.confidence_score,
                    "agent_review": stmt.excluded.agent_review,
                    "extracted_at": stmt.excluded.extracted_at,
                    "status": stmt.excluded.status,
                    "source_id": stmt.excluded.source_id,
                    "idempotency_key": stmt.excluded.idempotency_key,
                    "content_hash": stmt.excluded.content_hash,
                    "is_expired": stmt.excluded.is_expired,
                    "updated_at": stmt.excluded.updated_at,
                },
            ).returning(EventModel)

            result = await self._session.execute(stmt)
            saved_model = result.scalar_one()
            await self._session.commit()
            return model_to_event(saved_model)
        else:
            # Fallback for SQLite (tests)
            model = await self._session.merge(event_to_model(event))
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

    async def save_with_review(self, event: Event, review: Review) -> tuple[Event, Review]:
        event_model = await self._session.merge(event_to_model(event))
        review_model = review_to_model(review)
        self._session.add(review_model)
        await self._session.commit()
        await self._session.refresh(event_model)
        return model_to_event(event_model), model_to_review(review_model)


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
        model = await self._session.merge(source_to_model(source))
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

    async def toggle_active(self, source_id: uuid.UUID) -> Source | None:
        from hazlo.infrastructure.db.models import _utcnow

        stmt = (
            update(SourceModel)
            .where(SourceModel.id == source_id)
            .values(
                is_active=~SourceModel.is_active,
                updated_at=_utcnow(),
            )
            .returning(SourceModel)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        await self._session.commit()
        return model_to_source(model)

    async def get_extraction_history(
        self,
        source_id: uuid.UUID,
        *,
        limit: int = 20,
    ) -> list[dict[str, object]]:
        result = await self._session.execute(
            select(ExtractionRunModel)
            .where(ExtractionRunModel.source_id == source_id)
            .order_by(ExtractionRunModel.started_at.desc())
            .limit(limit)
        )
        runs = result.scalars().all()
        return [
            {
                "id": r.id,
                "started_at": r.started_at,
                "finished_at": r.finished_at,
                "status": r.status,
                "events_found": r.events_found,
                "errors": r.errors,
            }
            for r in runs
        ]

    async def delete(self, source_id: uuid.UUID) -> bool:
        result = await self._session.execute(select(SourceModel).where(SourceModel.id == source_id))
        model = result.scalar_one_or_none()
        if model is None:
            return False

        await self._session.execute(update(EventModel).where(EventModel.source_id == source_id).values(source_id=None))
        run_result = await self._session.execute(
            select(ExtractionRunModel).where(ExtractionRunModel.source_id == source_id)
        )
        for run in run_result.scalars().all():
            await self._session.delete(run)

        await self._session.delete(model)
        await self._session.commit()
        return True


class ReviewRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, review: Review) -> Review:
        model = review_to_model(review)
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return model_to_review(model)

    async def list_by_event(self, event_id: uuid.UUID) -> list[Review]:
        result = await self._session.execute(
            select(ReviewModel).where(ReviewModel.event_id == event_id).order_by(ReviewModel.reviewed_at.desc())
        )
        return [model_to_review(m) for m in result.scalars().all()]


class LLMProviderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, provider_id: uuid.UUID) -> LLMProviderModel | None:
        result = await self._session.execute(select(LLMProviderModel).where(LLMProviderModel.id == provider_id))
        return result.scalar_one_or_none()

    async def list_all(self) -> list[LLMProviderModel]:
        result = await self._session.execute(select(LLMProviderModel).order_by(LLMProviderModel.priority))
        return list(result.scalars().all())

    async def get_active(self) -> LLMProviderModel | None:
        # Multiple providers may be active for fallback chains. Return the primary
        # one deterministically (lowest priority value first).
        result = await self._session.execute(
            select(LLMProviderModel)
            .where(LLMProviderModel.is_active)
            .order_by(LLMProviderModel.priority.asc(), LLMProviderModel.created_at.asc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def save(self, provider: LLMProviderModel) -> LLMProviderModel:
        provider = await self._session.merge(provider)
        await self._session.commit()
        await self._session.refresh(provider)
        return provider

    async def toggle_active(self, provider_id: uuid.UUID) -> LLMProviderModel | None:
        """Toggle the active status of a provider without affecting others."""
        from hazlo.infrastructure.db.models import _utcnow

        model = await self.get(provider_id)
        if model is None:
            return None

        stmt = (
            update(LLMProviderModel)
            .where(LLMProviderModel.id == provider_id)
            .values(is_active=not model.is_active, updated_at=_utcnow())
            .returning(LLMProviderModel)
        )
        result = await self._session.execute(stmt)
        updated_model = result.scalar_one_or_none()
        if updated_model:
            await self._session.commit()
        return updated_model

    async def delete(self, provider_id: uuid.UUID) -> bool:
        result = await self._session.execute(select(LLMProviderModel).where(LLMProviderModel.id == provider_id))
        model = result.scalar_one_or_none()
        if model is None:
            return False
        await self._session.delete(model)
        await self._session.commit()
        return True
