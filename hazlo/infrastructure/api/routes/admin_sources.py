from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from hazlo.infrastructure.api.deps import get_db
from hazlo.infrastructure.db.repositories import SourceRepository

router = APIRouter()


class SourceCreate(BaseModel):
    model_config = ConfigDict(strict=True)

    name: str
    source_type: str
    url: str
    fetch_interval_minutes: int = 60


class SourceResponse(BaseModel):
    model_config = ConfigDict(strict=True)

    id: uuid.UUID
    name: str
    source_type: str
    url: str
    is_active: bool
    fetch_interval_minutes: int
    last_run_at: str | None = None
    last_run_status: str | None = None


@router.get("/", response_model=list[SourceResponse])
async def list_sources(db: AsyncSession = Depends(get_db)) -> list[SourceResponse]:
    repo = SourceRepository(db)
    sources = await repo.list_all()
    return [
        SourceResponse(
            id=s.id,
            name=s.name,
            source_type=s.source_type.value,
            url=s.url,
            is_active=s.is_active,
            fetch_interval_minutes=s.fetch_interval_minutes,
            last_run_at=str(s.last_run_at) if s.last_run_at else None,
            last_run_status=s.last_run_status,
        )
        for s in sources
    ]


@router.post("/", response_model=SourceResponse, status_code=201)
async def create_source(
    data: SourceCreate,
    db: AsyncSession = Depends(get_db),
) -> SourceResponse:
    from hazlo.domain.source import Source, SourceType

    repo = SourceRepository(db)
    source = Source(
        name=data.name,
        source_type=SourceType(data.source_type),
        url=data.url,
        fetch_interval_minutes=data.fetch_interval_minutes,
    )
    created = await repo.save(source)
    return SourceResponse(
        id=created.id,
        name=created.name,
        source_type=created.source_type.value,
        url=created.url,
        is_active=created.is_active,
        fetch_interval_minutes=created.fetch_interval_minutes,
    )


@router.get("/{source_id}", response_model=SourceResponse)
async def get_source(source_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> SourceResponse:
    repo = SourceRepository(db)
    source = await repo.get(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return SourceResponse(
        id=source.id,
        name=source.name,
        source_type=source.source_type.value,
        url=source.url,
        is_active=source.is_active,
        fetch_interval_minutes=source.fetch_interval_minutes,
        last_run_at=str(source.last_run_at) if source.last_run_at else None,
        last_run_status=source.last_run_status,
    )
