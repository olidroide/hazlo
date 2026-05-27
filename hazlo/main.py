from __future__ import annotations

import base64
import hmac
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, cast

import structlog
from alembic.config import Config
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.responses import Response

from alembic import command
from hazlo.infrastructure.api.routes import admin_events, admin_llm_providers, admin_sources
from hazlo.settings import get_settings

BASE_DIR = Path(__file__).resolve().parent

# Corporate proxy / Zscaler: CA_BUNDLE from settings (set in .env)
_ca_bundle = get_settings().ca_bundle
if _ca_bundle:
    os.environ["SSL_CERT_FILE"] = _ca_bundle
    os.environ["REQUESTS_CA_BUNDLE"] = _ca_bundle


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(0),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )

    _alembic_cfg = Config(str(BASE_DIR.parent / "alembic.ini"))
    _alembic_cfg.set_main_option("script_location", "alembic")
    if os.environ.get("HAZLO_AUTO_MIGRATE", "1") == "1":
        try:
            command.upgrade(_alembic_cfg, "head")
        except Exception:
            logging.getLogger("hazlo").warning("alembic upgrade failed — is the database running?")

    yield


class BasicAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith("/admin"):
            return await call_next(request)

        settings = get_settings()
        if not settings.admin_password:
            return await call_next(request)

        auth_header = request.headers.get("authorization")
        if auth_header is None:
            return Response(content="Unauthorized", status_code=401, headers={"WWW-Authenticate": "Basic"})

        try:
            scheme, credentials = auth_header.split()
            if scheme.lower() != "basic":
                return Response(content="Unauthorized", status_code=401, headers={"WWW-Authenticate": "Basic"})
            decoded = base64.b64decode(credentials).decode("utf-8")
            username, _, password = decoded.partition(":")
            user_ok = hmac.compare_digest(username, settings.admin_user)
            pass_ok = hmac.compare_digest(password, settings.admin_password)
            if not user_ok or not pass_ok:
                return Response(content="Forbidden", status_code=403)
        except Exception:
            return Response(content="Unauthorized", status_code=401, headers={"WWW-Authenticate": "Basic"})

        return await call_next(request)


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

app.add_middleware(BasicAuthMiddleware)
app.add_middleware(TemplateMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=500)

app.include_router(admin_sources.router, prefix="/admin/sources", tags=["admin-sources"])
app.include_router(admin_events.router, prefix="/admin/events", tags=["admin-events"])
app.include_router(admin_llm_providers.router, prefix="/admin/llm-providers", tags=["admin-llm-providers"])

templates_dir = BASE_DIR / "infrastructure" / "templates"
static_dir = BASE_DIR / "static"

templates = Jinja2Templates(directory=str(templates_dir))
cast(dict[str, Any], templates.env.globals)["static_url"] = lambda path: f"/static/{str(path).lstrip('/')}"

if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/health", include_in_schema=False)
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@app.get("/")
async def root(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "base.html")
