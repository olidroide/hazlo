from __future__ import annotations

import logging
import time

import httpx

from hazlo.infrastructure.llm.providers.base import LLMProvider, LLMResponse, ModelInfo
from hazlo.settings import get_settings

logger = logging.getLogger(__name__)

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"


class OpenRouterProvider(LLMProvider):
    provider_type = "openrouter"

    @classmethod
    async def list_models(cls, api_key: str) -> list[ModelInfo]:
        verify = get_settings().verify_ssl
        async with httpx.AsyncClient(verify=verify) as client:
            response = await client.get(OPENROUTER_MODELS_URL, timeout=15.0)
            response.raise_for_status()
            data = response.json()

        models: list[ModelInfo] = []
        for m in data.get("data", []):
            pricing = m.get("pricing", {})
            try:
                prompt_price = float(pricing.get("prompt", -1))
            except (ValueError, TypeError):
                prompt_price = -1
            try:
                completion_price = float(pricing.get("completion", -1))
            except (ValueError, TypeError):
                completion_price = -1
            is_free = prompt_price == 0 and completion_price == 0
            models.append(
                ModelInfo(
                    id=m["id"],
                    display_name=m.get("name", m["id"]),
                    is_free=is_free,
                    description=m.get("description", "")[:200] or None,
                )
            )

        models.sort(key=lambda m: (not m.is_free, m.display_name))
        logger.info("OpenRouter list_models found=%d models", len(models))
        return models

    def __init__(self, api_key: str, model: str = "google/gemini-2.0-flash") -> None:
        self._api_key = api_key
        self._model = model
        logger.info("OpenRouterProvider created model=%s", model)

    async def generate(
        self,
        system_prompt: str,
        user_content: str,
        temperature: float = 0.0,
        max_tokens: int = 500,
    ) -> LLMResponse:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        logger.debug("OpenRouter request model=%s", self._model)

        start = time.monotonic()
        verify = get_settings().verify_ssl
        async with httpx.AsyncClient(verify=verify) as client:
            response = await client.post(
                OPENROUTER_API_URL,
                json=payload,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )
            if response.is_error:
                logger.error(
                    "OpenRouter HTTP error status=%d body=%s",
                    response.status_code,
                    response.text[:500],
                )
            response.raise_for_status()
            data = response.json()

        latency_ms = int((time.monotonic() - start) * 1000)

        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})

        logger.info(
            "OpenRouter response latency=%dms tokens_in=%s tokens_out=%s",
            latency_ms,
            usage.get("prompt_tokens", 0),
            usage.get("completion_tokens", 0),
        )

        return LLMResponse(
            content=content,
            tokens_in=usage.get("prompt_tokens", 0),
            tokens_out=usage.get("completion_tokens", 0),
            model=self._model,
            latency_ms=latency_ms,
        )

    async def test_connection(self) -> bool:
        logger.info("OpenRouter test_connection started model=%s", self._model)
        try:
            response = await self.generate(
                system_prompt="Reply with exactly: OK",
                user_content="test",
                max_tokens=50,
            )
            ok = "OK" in response.content
            logger.info("OpenRouter test_connection result=%s content=%r", ok, response.content)
            return ok
        except Exception:
            logger.exception("OpenRouter test_connection failed for model=%s", self._model)
            return False
