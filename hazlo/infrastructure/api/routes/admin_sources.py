from __future__ import annotations

import asyncio
import html
import logging
import os
import uuid
from collections.abc import AsyncIterable

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.sse import EventSourceResponse, ServerSentEvent

from hazlo.infrastructure.api.deps import get_source_repo
from hazlo.infrastructure.db.repositories import SourceRepository

logger = logging.getLogger(__name__)

router = APIRouter()


def _source_dict(source) -> dict:
    return {
        "id": source.id,
        "name": source.name,
        "source_type": source.source_type.value,
        "url": source.url,
        "config": source.config,
        "is_active": source.is_active,
        "fetch_interval_minutes": source.fetch_interval_minutes,
        "last_run_at": source.last_run_at,
        "last_run_status": source.last_run_status,
    }


@router.get("/")
async def list_sources(
    request: Request,
    source_repo: SourceRepository = Depends(get_source_repo),
):
    sources = await source_repo.list_all()
    source_dicts = [_source_dict(s) for s in sources]
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
    url: str | None = Form(None),
    fetch_interval_minutes: int = Form(60),
    imap_host: str | None = Form(None),
    imap_port: int = Form(993),
    imap_user: str | None = Form(None),
    imap_password: str | None = Form(None),
    imap_mailbox: str = Form("INBOX"),
    imap_ssl: str = Form("true"),
    source_repo: SourceRepository = Depends(get_source_repo),
):
    from hazlo.domain.source import Source, SourceType

    config: dict = {}
    if source_type == SourceType.EMAIL.value and imap_host:
        config["imap_host"] = imap_host
        config["imap_port"] = imap_port
        config["imap_user"] = imap_user
        config["imap_password"] = imap_password
        config["imap_mailbox"] = imap_mailbox
        config["imap_ssl"] = imap_ssl.lower() == "true"

    source = Source(
        name=name,
        source_type=SourceType(source_type),
        url=url,
        config=config,
        fetch_interval_minutes=fetch_interval_minutes,
    )
    created = await source_repo.save(source)
    return request.state.templates.TemplateResponse(
        request,
        "admin/sources/_row.html",
        {"source": _source_dict(created)},
    )


@router.get("/{source_id}")
async def get_source(
    request: Request,
    source_id: uuid.UUID,
    source_repo: SourceRepository = Depends(get_source_repo),
):
    source = await source_repo.get(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")

    history = await source_repo.get_extraction_history(source_id)
    health = _compute_source_health(history)

    return request.state.templates.TemplateResponse(
        request,
        "admin/sources/detail.html",
        {"source": _source_dict(source), "history": history, "health": health},
    )


@router.patch("/{source_id}/toggle")
async def toggle_source(
    request: Request,
    source_id: uuid.UUID,
    source_repo: SourceRepository = Depends(get_source_repo),
):
    source = await source_repo.toggle_active(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")

    return request.state.templates.TemplateResponse(
        request,
        "admin/sources/_row.html",
        {"source": _source_dict(source)},
    )


@router.post("/{source_id}/run-now")
async def run_source_now(
    request: Request,
    source_id: uuid.UUID,
    source_repo: SourceRepository = Depends(get_source_repo),
):
    source = await source_repo.get(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")

    async def _run_and_update() -> None:
        from hazlo.infrastructure.db.repositories import SourceRepository as Repo
        from hazlo.infrastructure.db.session import async_session_factory

        try:
            from hazlo.infrastructure.prefect.flows import ingest_single_source_flow

            await ingest_single_source_flow(str(source_id))
            status = "success"
        except Exception:
            logger.exception("Run-now failed for source %s", source_id)
            status = "error"

        async with async_session_factory() as session:
            repo = Repo(session)
            s = await repo.get(source_id)
            if s is not None:
                s.last_run_status = status
                await repo.save(s)

    _ = asyncio.create_task(_run_and_update())  # noqa: RUF006

    source_dict = _source_dict(source)
    source_dict["last_run_status"] = "running"
    return request.state.templates.TemplateResponse(
        request,
        "admin/sources/_row.html",
        {"source": source_dict},
    )


@router.post("/{source_id}/test-connection")
async def test_source_connection(
    request: Request,
    source_id: uuid.UUID,
    source_repo: SourceRepository = Depends(get_source_repo),
):
    source = await source_repo.get(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")

    success, message = await _test_connection(source)
    logger.info("Test connection result for %s: success=%s, message=%s", source_id, success, message)

    return request.state.templates.TemplateResponse(
        request,
        "admin/sources/_connection_result.html",
        {"success": success, "message": message},
    )


@router.post("/{source_id}/preview")
async def preview_source_parse(
    request: Request,
    source_id: uuid.UUID,
    source_repo: SourceRepository = Depends(get_source_repo),
):
    source = await source_repo.get(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")

    events, error = await _preview_parse(source)

    return request.state.templates.TemplateResponse(
        request,
        "admin/sources/_preview_result.html",
        {"events": events, "error": error},
    )


async def _test_connection(source) -> tuple[bool, str]:
    from hazlo.domain.source import SourceType

    match source.source_type:
        case SourceType.RSS | SourceType.WEB:
            if not source.url:
                return False, "URL not configured"
            import ssl

            import httpx

            logger.info("Testing connection to %s (type=%s)", source.url, source.source_type.value)

            try:
                async with httpx.AsyncClient(
                    timeout=15.0,
                    verify=os.environ.get("SSL_CERT_FILE") or True,
                ) as client:
                    resp = await client.get(source.url)
                    resp.raise_for_status()
                msg = f"Connection OK ({resp.status_code}, {len(resp.text):,} bytes)"
                logger.info("Connection test OK: %s", msg)
                return True, msg
            except httpx.TimeoutException:
                logger.warning("Connection test timeout: %s", source.url)
                return False, "Connection timeout"
            except httpx.HTTPStatusError as e:
                logger.warning("Connection test HTTP error: %s → %d", source.url, e.response.status_code)
                return False, f"HTTP error: {e.response.status_code}"
            except ssl.SSLCertVerificationError as e:
                logger.error("Connection test SSL error: %s → %s", source.url, e)
                return False, f"SSL error: {e}. Verify server certificate."
            except httpx.ConnectError as e:
                logger.error("Connection test connect error: %s → %s", source.url, e)
                return False, f"Connection error: {e}"
            except Exception as e:
                logger.exception("Connection test failed: %s", source.url)
                return False, f"Error: {e}"

        case SourceType.EMAIL:
            config = source.config or {}
            host = config.get("imap_host")
            port = config.get("imap_port", 993)
            user = config.get("imap_user")
            password = config.get("imap_password")
            ssl_flag = config.get("imap_ssl", True)

            if not host or not user or not password:
                return False, "IMAP configuration incomplete"

            logger.info("Testing IMAP connection to %s:%d (ssl=%s)", host, port, ssl_flag)

            def _try_imap() -> tuple[bool, str]:
                import imaplib

                try:
                    conn = (
                        imaplib.IMAP4_SSL(host, port, timeout=15) if ssl_flag else imaplib.IMAP4(host, port, timeout=15)
                    )
                    conn.login(user, password)
                    conn.logout()
                    return True, "IMAP connection OK"
                except imaplib.IMAP4.error as e:
                    return False, f"IMAP auth error: {e}"
                except Exception as e:
                    return False, f"IMAP error: {e}"

            return _try_imap()

        case _:
            return False, f"Unsupported source type: {source.source_type.value}"

    return False, "Unknown source type"


async def _preview_parse(source) -> tuple[list[dict], str | None]:
    from hazlo.infrastructure.adapters import adapter_registry

    adapter = adapter_registry.get(source.source_type.value)
    if adapter is None:
        return [], f"No adapter for source type: {source.source_type.value}"

    try:
        raw_events = await adapter.fetch(source)
    except Exception as e:
        return [], f"Error fetching data: {e}"

    previews = []
    for raw in raw_events[:5]:
        try:
            event = await adapter.normalize(raw)
            previews.append(
                {
                    "title": html.unescape(event.title),
                    "location": html.unescape(event.location.address) if event.location else "",
                    "start_at": event.start_at.strftime("%d/%m/%Y %H:%M") if event.start_at else "",
                    "source_url": event.source_url,
                    "error": False,
                }
            )
        except Exception as e:
            previews.append({"title": "Normalize error", "error": True, "detail": str(e)})

    return previews, None


@router.get("/{source_id}/test/stream", response_class=EventSourceResponse)
async def test_integration_stream(
    request: Request,
    source_id: uuid.UUID,
    source_repo: SourceRepository = Depends(get_source_repo),
) -> AsyncIterable[ServerSentEvent]:
    source = await source_repo.get(source_id)
    if source is None:
        yield ServerSentEvent(
            event="log_entry",
            data='<div class="log-error"><span class="log-icon">\u2717</span> Source not found</div>',
        )
        yield ServerSentEvent(event="complete", data="")
        return

    queue: asyncio.Queue[dict[str, object]] = asyncio.Queue()

    async def _run_pipeline() -> None:
        from hazlo.application.services import DedupService, EnrichmentService
        from hazlo.application.use_cases.ingest_source import IngestSource
        from hazlo.infrastructure.adapters import adapter_registry

        use_case = IngestSource(
            adapter_registry=adapter_registry,
            enrichment_service=EnrichmentService(),
            dedup_service=DedupService(),
            event_queue=queue,
        )
        result = await use_case.execute(source=source, existing_urls=set())
        await queue.put(
            {
                "step": "complete_params",
                "found": result.events_found,
                "new": result.events_new,
                "skipped": result.events_skipped,
                "approved": result.events_auto_approved,
                "flagged": result.events_flagged,
                "errors": len(result.errors),
            }
        )
        await queue.put({"step": "done", "level": "done", "msg": ""})

    _ = asyncio.create_task(_run_pipeline())  # noqa: RUF006

    complete_params: dict[str, object] = {}

    while True:
        item = await queue.get()
        step = str(item.get("step", ""))

        if step == "done":
            params = "&".join(f"{k}={v}" for k, v in complete_params.items())
            result_url = f"/admin/sources/{source_id}/test/result?{params}"
            summary_html = (
                f'<div hx-get="{result_url}" hx-trigger="revealed" hx-target="#test-log" hx-swap="beforeend"></div>'
            )
            yield ServerSentEvent(event="log_entry", data=summary_html)
            yield ServerSentEvent(event="complete", data="")
            break

        if step == "complete_params":
            complete_params = item
            continue

        msg = str(item.get("msg", ""))
        level = str(item.get("level", "info"))
        raw_json = str(item.get("raw_json", ""))

        icon_map = {"success": "✓", "error": "✗", "info": "·", "summary": "✓"}
        icon = icon_map.get(level, "\u00b7")
        html = f'<div class="log-{level}"><span class="log-icon">{icon}</span> {msg}</div>'
        if raw_json:
            safe_json = raw_json.replace("<", "&lt;").replace(">", "&gt;")
            html += f'<details class="log-details"><summary>Raw LLM</summary><pre>{safe_json}</pre></details>'

        yield ServerSentEvent(event="log_entry", data=html)


@router.get("/{source_id}/test/result")
async def test_integration_result(
    request: Request,
    source_id: uuid.UUID,
    found: int = 0,
    new: int = 0,
    skipped: int = 0,
    approved: int = 0,
    flagged: int = 0,
    errors: int = 0,
):
    return request.state.templates.TemplateResponse(
        request,
        "admin/sources/_test_result.html",
        {
            "source_id": source_id,
            "found": found,
            "new": new,
            "skipped": skipped,
            "approved": approved,
            "flagged": flagged,
            "errors": errors,
        },
    )


def _compute_source_health(history: list[dict]) -> dict:
    """Compute health metrics from extraction run history."""
    if not history:
        return {
            "total_runs": 0,
            "success_rate": 0.0,
            "avg_events_found": 0.0,
            "last_success": None,
            "last_failure": None,
        }

    total = len(history)
    errors = sum(1 for r in history if r.get("status") == "error")
    successes = total - errors
    last_success = None
    last_failure = None

    for r in sorted(history, key=lambda x: x.get("started_at") or "", reverse=True):
        if r.get("status") == "error" and last_failure is None:
            last_failure = r.get("finished_at") or r.get("started_at")
        elif r.get("status") != "error" and last_success is None:
            last_success = r.get("finished_at") or r.get("started_at")
        if last_success and last_failure:
            break

    return {
        "total_runs": total,
        "success_rate": successes / total if total > 0 else 0.0,
        "avg_events_found": sum(r.get("events_found", 0) for r in history) / total,
        "last_success": last_success,
        "last_failure": last_failure,
    }
