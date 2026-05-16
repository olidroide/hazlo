from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from hazlo.infrastructure.api.routes import admin_events, admin_sources

BASE_DIR = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="Hazlo",
    description="Smart event agenda with human review",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(admin_sources.router, prefix="/admin/sources", tags=["admin-sources"])
app.include_router(admin_events.router, prefix="/admin/events", tags=["admin-events"])

templates_dir = BASE_DIR / "templates"
static_dir = BASE_DIR / "static"

if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def root() -> dict[str, str]:
    return {"status": "ok", "service": "hazlo"}
