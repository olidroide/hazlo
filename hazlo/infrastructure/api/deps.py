from __future__ import annotations

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from hazlo.infrastructure.db.repositories import (
    EventRepository,
    LLMProviderRepository,
    ReviewRepository,
    SourceRepository,
)
from hazlo.infrastructure.db.session import get_session


def get_db(session: AsyncSession = Depends(get_session)) -> AsyncSession:
    return session


def get_event_repo(session: AsyncSession = Depends(get_session)) -> EventRepository:
    return EventRepository(session)


def get_source_repo(session: AsyncSession = Depends(get_session)) -> SourceRepository:
    return SourceRepository(session)


def get_review_repo(session: AsyncSession = Depends(get_session)) -> ReviewRepository:
    return ReviewRepository(session)


def get_llm_provider_repo(session: AsyncSession = Depends(get_session)) -> LLMProviderRepository:
    return LLMProviderRepository(session)


def get_base(request: Request) -> str:
    """Return the appropriate base template for full-page vs HTMX-boosted requests."""
    if request.headers.get("HX-Request"):
        return "base_htmx.html"
    return "base.html"
