from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware

from hazlo.infrastructure.api.routes import admin_events, admin_sources

BASE_DIR = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


class TemplateMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request.state.templates = templates
        session = request.scope.get("session", {})
        request.state.flash_messages = session.get("flash_messages", [])
        response = await call_next(request)
        return response


app = FastAPI(
    title="Hazlo",
    description="Smart event agenda with human review",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(TemplateMiddleware)

app.include_router(admin_sources.router, prefix="/admin/sources", tags=["admin-sources"])
app.include_router(admin_events.router, prefix="/admin/events", tags=["admin-events"])

templates_dir = BASE_DIR / "infrastructure" / "templates"
static_dir = BASE_DIR / "static"

templates = Jinja2Templates(directory=str(templates_dir))

if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def root(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "base.html")
