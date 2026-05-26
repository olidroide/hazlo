from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.openrouter import OpenRouterModel
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.providers.openrouter import OpenRouterProvider
from starlette.responses import Response

from hazlo.infrastructure.api.deps import get_llm_provider_repo
from hazlo.infrastructure.crypto import decrypt_value, encrypt_value
from hazlo.infrastructure.db.repositories import LLMProviderRepository
from hazlo.settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter()

SUPPORTED_PROVIDERS = {"gemini", "openrouter", "groq"}


@dataclass
class ModelInfo:
    id: str
    display_name: str
    is_free: bool
    description: str | None = None


async def _list_gemini_models(api_key: str) -> list[ModelInfo]:
    provider = GoogleProvider(api_key=api_key)
    response = provider.client.models.list()
    models = []
    for m in response:
        if not m.name:
            continue
        model_id = m.name.removeprefix("models/")
        display_name = m.display_name or model_id
        is_free = "flash" in model_id.lower()
        description = m.description[:200] if m.description else None
        models.append(ModelInfo(id=model_id, display_name=display_name, is_free=is_free, description=description))
    models.sort(key=lambda m: (not m.is_free, m.display_name))
    return models


async def _list_openrouter_models(api_key: str) -> list[ModelInfo]:
    import httpx

    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()

    models = []
    for m in data.get("data", []):
        model_id = m.get("id", "")
        display_name = m.get("name", model_id)
        pricing = m.get("pricing", {})
        prompt_price = float(pricing.get("prompt", "0") or "0")
        is_free = prompt_price == 0.0
        description = m.get("description", "")[:200] if m.get("description") else None
        models.append(ModelInfo(id=model_id, display_name=display_name, is_free=is_free, description=description))
    models.sort(key=lambda m: (not m.is_free, m.display_name))
    return models


async def _list_groq_models(api_key: str) -> list[ModelInfo]:
    import httpx

    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()

    models = []
    for m in data.get("data", []):
        model_id = m.get("id", "")
        display_name = m.get("id", model_id)
        owned_by = m.get("owned_by", "")
        is_free = owned_by == "groq" or "groq" in model_id.lower()
        models.append(ModelInfo(id=model_id, display_name=display_name, is_free=is_free))
    models.sort(key=lambda m: (not m.is_free, m.display_name))
    return models


async def _list_models(provider_type: str, api_key: str) -> list[ModelInfo]:
    if provider_type == "gemini":
        return await _list_gemini_models(api_key)
    if provider_type == "openrouter":
        return await _list_openrouter_models(api_key)
    if provider_type == "groq":
        return await _list_groq_models(api_key)
    raise ValueError(f"Unknown provider type: {provider_type}")


async def _test_connection(provider_type: str, api_key: str, model_name: str) -> bool:
    if provider_type == "gemini":
        provider = GoogleProvider(api_key=api_key)
        model = GoogleModel(model_name, provider=provider)
    elif provider_type == "openrouter":
        provider = OpenRouterProvider(api_key=api_key)
        model = OpenRouterModel(model_name, provider=provider)
    elif provider_type == "groq":
        from pydantic_ai.models.groq import GroqModel
        from pydantic_ai.providers.groq import GroqProvider

        model = GroqModel(model_name, provider=GroqProvider(api_key=api_key))
    else:
        raise ValueError(f"Unknown provider type: {provider_type}")

    agent = Agent(model)
    result = await agent.run("Reply with exactly: OK")
    return "OK" in str(result.output)


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
    if provider_type not in SUPPORTED_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unknown provider type: {provider_type}")

    try:
        models = await _list_models(provider_type, api_key)
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

    if provider_type not in SUPPORTED_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unknown provider type: {provider_type}")

    from hazlo.infrastructure.db.models import LLMProviderModel

    encrypted_key = encrypt_value(api_key, settings.hazlo_secret_key)
    provider = LLMProviderModel(
        id=uuid.uuid4(),
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

    try:
        success = await _test_connection(model.provider_type, api_key, model.model)
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
