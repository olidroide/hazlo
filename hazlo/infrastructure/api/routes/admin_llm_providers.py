from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from starlette.responses import Response

from hazlo.infrastructure.api.deps import get_llm_provider_repo
from hazlo.infrastructure.crypto import decrypt_value, encrypt_value
from hazlo.infrastructure.db.repositories import LLMProviderRepository
from hazlo.infrastructure.llm.providers import _PROVIDER_CLASSES
from hazlo.settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter()


def _provider_dict(model) -> dict:
    return {
        "id": model.id,
        "name": model.name,
        "provider_type": model.provider_type,
        "model": model.model,
        "is_active": model.is_active,
        "priority": model.priority,
        "max_calls_per_run": model.max_calls_per_run,
        "cost_per_1k_tokens_micros": model.cost_per_1k_tokens_micros,
        "created_at": model.created_at,
        "updated_at": model.updated_at,
    }


@router.get("/")
async def list_llm_providers(
    request: Request,
    repo: LLMProviderRepository = Depends(get_llm_provider_repo),
):
    providers = await repo.list_all()
    return request.state.templates.TemplateResponse(
        request,
        "admin/llm_providers/list.html",
        {"providers": [_provider_dict(p) for p in providers]},
    )


@router.get("/_new")
async def new_provider_form(request: Request):
    return request.state.templates.TemplateResponse(
        request,
        "admin/llm_providers/_create_form.html",
        {},
    )


@router.post("/models")
async def list_provider_models(
    request: Request,
    provider_type: str = Form(...),
    api_key: str = Form(...),
):
    provider_cls = _PROVIDER_CLASSES.get(provider_type)
    if provider_cls is None:
        raise HTTPException(status_code=400, detail=f"Unknown provider type: {provider_type}")

    try:
        models = await provider_cls.list_models(api_key)
    except Exception:
        logger.exception("Failed to list models for provider=%s", provider_type)
        return request.state.templates.TemplateResponse(
            request,
            "admin/llm_providers/_models_list.html",
            {
                "provider_type": provider_type,
                "models": [],
                "error": "Failed to fetch models. Check the API key and try again.",
            },
        )

    return request.state.templates.TemplateResponse(
        request,
        "admin/llm_providers/_models_list.html",
        {
            "provider_type": provider_type,
            "models": models,
            "error": None,
        },
    )


@router.post("/")
async def create_provider(
    request: Request,
    name: str = Form(...),
    provider_type: str = Form(...),
    model: str = Form(...),
    api_key: str = Form(...),
    priority: int = Form(0),
    repo: LLMProviderRepository = Depends(get_llm_provider_repo),
):
    settings = get_settings()
    if not settings.hazlo_secret_key:
        raise HTTPException(status_code=500, detail="HAZLO_SECRET_KEY not configured")

    if provider_type not in _PROVIDER_CLASSES:
        raise HTTPException(status_code=400, detail=f"Unknown provider type: {provider_type}")

    from hazlo.infrastructure.db.models import LLMProviderModel

    encrypted_key = encrypt_value(api_key, settings.hazlo_secret_key)
    provider = LLMProviderModel(
        name=name,
        provider_type=provider_type,
        model=model,
        api_key_encrypted=encrypted_key,
        priority=priority,
    )
    await repo.save(provider)
    return request.state.templates.TemplateResponse(
        request,
        "admin/llm_providers/_create_result.html",
        {"provider": _provider_dict(provider)},
    )


@router.post("/{provider_id}/test")
async def test_provider_connection(
    provider_id: uuid.UUID,
    request: Request,
    repo: LLMProviderRepository = Depends(get_llm_provider_repo),
):
    settings = get_settings()
    if not settings.hazlo_secret_key:
        raise HTTPException(status_code=500, detail="HAZLO_SECRET_KEY not configured")

    model = await repo.get(provider_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Provider not found")

    logger.info("Testing connection for provider=%s type=%s model=%s", model.name, model.provider_type, model.model)

    api_key = decrypt_value(model.api_key_encrypted, settings.hazlo_secret_key)

    provider_cls = _PROVIDER_CLASSES.get(model.provider_type)
    if provider_cls is None:
        raise HTTPException(status_code=400, detail=f"Unknown provider type: {model.provider_type}")

    provider = provider_cls(api_key=api_key, model=model.model)

    try:
        success = await provider.test_connection()
        logger.info("Test connection result for %s: success=%s", model.name, success)
    except Exception as exc:
        logger.exception("Provider test connection failed for %s", model.name)
        return request.state.templates.TemplateResponse(
            request,
            "admin/llm_providers/_test_result.html",
            {"success": False, "error": str(exc)},
            headers={"HX-Retarget": "#provider-test-result", "HX-Reswap": "innerHTML"},
        )

    return request.state.templates.TemplateResponse(
        request,
        "admin/llm_providers/_test_result.html",
        {"success": success},
        headers={"HX-Retarget": "#provider-test-result", "HX-Reswap": "innerHTML"},
    )


@router.post("/{provider_id}/activate")
async def activate_provider(
    provider_id: uuid.UUID,
    request: Request,
    repo: LLMProviderRepository = Depends(get_llm_provider_repo),
):
    model = await repo.set_active(provider_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    return request.state.templates.TemplateResponse(
        request,
        "admin/llm_providers/_list_row.html",
        {"provider": _provider_dict(model)},
        headers={"HX-Retarget": f"#provider-row-{model.id}", "HX-Reswap": "outerHTML"},
    )


@router.delete("/{provider_id}")
async def delete_provider(
    provider_id: uuid.UUID,
    request: Request,
    repo: LLMProviderRepository = Depends(get_llm_provider_repo),
):
    success = await repo.delete(provider_id)
    if not success:
        raise HTTPException(status_code=404, detail="Provider not found")
    return Response(content="", status_code=200)
