from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from hazlo.infrastructure.api.deps import get_db
from hazlo.infrastructure.db.repositories import SourceRepository

router = APIRouter()


@router.get("/")
async def list_sources(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    repo = SourceRepository(db)
    sources = await repo.list_all()
    source_dicts = [
        {
            "id": s.id,
            "name": s.name,
            "source_type": s.source_type.value,
            "url": s.url,
            "is_active": s.is_active,
            "fetch_interval_minutes": s.fetch_interval_minutes,
            "last_run_at": s.last_run_at,
            "last_run_status": s.last_run_status,
        }
        for s in sources
    ]
    return request.state.templates.TemplateResponse(
        request,
        "admin/sources/list.html",
        {"sources": source_dicts},
    )


@router.get("/_new")
async def new_source_form(request: Request):
    return request.state.templates.TemplateResponse(
        request,
        "admin/sources/_create_form.html",
    )


@router.post("/")
async def create_source(
    request: Request,
    name: str = Form(...),
    source_type: str = Form(...),
    url: str = Form(...),
    fetch_interval_minutes: int = Form(60),
    db: AsyncSession = Depends(get_db),
):
    from hazlo.domain.source import Source, SourceType

    repo = SourceRepository(db)
    source = Source(
        name=name,
        source_type=SourceType(source_type),
        url=url,
        fetch_interval_minutes=fetch_interval_minutes,
    )
    created = await repo.save(source)
    source_dict = {
        "id": created.id,
        "name": created.name,
        "source_type": created.source_type.value,
        "url": created.url,
        "is_active": created.is_active,
        "fetch_interval_minutes": created.fetch_interval_minutes,
        "last_run_at": created.last_run_at,
        "last_run_status": created.last_run_status,
    }
    return request.state.templates.TemplateResponse(
        request,
        "admin/sources/_row.html",
        {"source": source_dict},
    )


@router.get("/{source_id}")
async def get_source(
    request: Request,
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    repo = SourceRepository(db)
    source = await repo.get(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")

    history = await repo.get_extraction_history(source_id)

    source_dict = {
        "id": source.id,
        "name": source.name,
        "source_type": source.source_type.value,
        "url": source.url,
        "is_active": source.is_active,
        "fetch_interval_minutes": source.fetch_interval_minutes,
        "last_run_at": source.last_run_at,
        "last_run_status": source.last_run_status,
    }
    return request.state.templates.TemplateResponse(
        request,
        "admin/sources/detail.html",
        {"source": source_dict, "history": history},
    )


@router.patch("/{source_id}/toggle")
async def toggle_source(
    request: Request,
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    repo = SourceRepository(db)
    source = await repo.toggle_active(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")

    source_dict = {
        "id": source.id,
        "name": source.name,
        "source_type": source.source_type.value,
        "url": source.url,
        "is_active": source.is_active,
        "fetch_interval_minutes": source.fetch_interval_minutes,
        "last_run_at": source.last_run_at,
        "last_run_status": source.last_run_status,
    }
    return request.state.templates.TemplateResponse(
        request,
        "admin/sources/_row.html",
        {"source": source_dict},
    )


@router.post("/{source_id}/run-now")
async def run_source_now(
    request: Request,
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    try:
        import subprocess

        script = (
            f"import asyncio; "
            f"from hazlo.infrastructure.prefect.flows import ingest_single_source_flow; "
            f"asyncio.run(ingest_single_source_flow('{source_id}'))"
        )
        subprocess.Popen(["uv", "run", "python", "-c", script])
    except Exception:
        pass

    repo = SourceRepository(db)
    source = await repo.get(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")

    source_dict = {
        "id": source.id,
        "name": source.name,
        "source_type": source.source_type.value,
        "url": source.url,
        "is_active": source.is_active,
        "fetch_interval_minutes": source.fetch_interval_minutes,
        "last_run_at": source.last_run_at,
        "last_run_status": "running",
    }
    return request.state.templates.TemplateResponse(
        request,
        "admin/sources/_row.html",
        {"source": source_dict},
    )
