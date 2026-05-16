from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from hazlo.infrastructure.api.deps import get_db
from hazlo.infrastructure.db.models import SourceModel
from hazlo.infrastructure.db.repositories import SourceRepository

router = APIRouter()


class SourceCreate(BaseModel):
    model_config = ConfigDict(strict=True)

    name: str
    source_type: str
    url: str
    extraction_frequency_minutes: int = 60


class SourceResponse(BaseModel):
    model_config = ConfigDict(strict=True)

    id: uuid.UUID
    name: str
    source_type: str
    url: str
    status: str
    extraction_frequency_minutes: int
    last_run_at: str | None = None
    last_run_success: bool | None = None


@router.get("/", response_model=list[SourceResponse])
async def list_sources(db: AsyncSession = Depends(get_db)) -> list[SourceResponse]:
    repo = SourceRepository(db)
    sources = await repo.list_all()
    return [
        SourceResponse(
            id=s.id,
            name=s.name,
            source_type=s.source_type,
            url=s.url,
            status=s.status,
            extraction_frequency_minutes=s.extraction_frequency_minutes,
            last_run_at=str(s.last_run_at) if s.last_run_at else None,
            last_run_success=s.last_run_success,
        )
        for s in sources
    ]


@router.post("/", response_model=SourceResponse, status_code=201)
async def create_source(
    data: SourceCreate,
    db: AsyncSession = Depends(get_db),
) -> SourceResponse:
    repo = SourceRepository(db)
    model = SourceModel(
        name=data.name,
        source_type=data.source_type,
        url=data.url,
        extraction_frequency_minutes=data.extraction_frequency_minutes,
    )
    created = await repo.add(model)
    return SourceResponse(
        id=created.id,
        name=created.name,
        source_type=created.source_type,
        url=created.url,
        status=created.status,
        extraction_frequency_minutes=created.extraction_frequency_minutes,
    )


@router.get("/{source_id}", response_model=SourceResponse)
async def get_source(source_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> SourceResponse:
    repo = SourceRepository(db)
    source = await repo.get_by_id(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return SourceResponse(
        id=source.id,
        name=source.name,
        source_type=source.source_type,
        url=source.url,
        status=source.status,
        extraction_frequency_minutes=source.extraction_frequency_minutes,
        last_run_at=str(source.last_run_at) if source.last_run_at else None,
        last_run_success=source.last_run_success,
    )
