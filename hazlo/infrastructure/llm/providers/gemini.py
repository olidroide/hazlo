from __future__ import annotations

import logging
import time

import httpx

from hazlo.infrastructure.llm.providers.base import LLMProvider, LLMResponse, ModelInfo
from hazlo.settings import get_settings

logger = logging.getLogger(__name__)

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GEMINI_LIST_MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiProvider(LLMProvider):
    provider_type = "gemini"

    @classmethod
    async def list_models(cls, api_key: str) -> list[ModelInfo]:
        url = GEMINI_LIST_MODELS_URL
        verify = get_settings().verify_ssl
        async with httpx.AsyncClient(verify=verify) as client:
            response = await client.get(url, headers={"x-goog-api-key": api_key}, timeout=15.0)
            response.raise_for_status()
            data = response.json()

        models: list[ModelInfo] = []
        for m in data.get("models", []):
            methods = m.get("supportedGenerationMethods", [])
            if "generateContent" not in methods:
                continue
            model_id = m["name"].removeprefix("models/")
            display_name = m.get("displayName", model_id)
            is_free = "flash" in model_id.lower()
            description = m.get("description", "")
            models.append(
                ModelInfo(
                    id=model_id,
                    display_name=display_name,
                    is_free=is_free,
                    description=description[:200] if description else None,
                )
            )

        models.sort(key=lambda m: (not m.is_free, m.display_name))
        logger.info("Gemini list_models found=%d models", len(models))
        return models

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash") -> None:
        self._api_key = api_key
        self._model = model
        logger.info("GeminiProvider created model=%s", model)

    async def generate(
        self,
        system_prompt: str,
        user_content: str,
        temperature: float = 0.0,
        max_tokens: int = 500,
        response_mime_type: str | None = "application/json",
    ) -> LLMResponse:
        url = GEMINI_API_URL.format(model=self._model)
        generation_config: dict = {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        }
        if response_mime_type:
            generation_config["responseMimeType"] = response_mime_type

        payload = {
            "contents": [{"role": "user", "parts": [{"text": f"{system_prompt}\n\n{user_content}"}]}],
            "generationConfig": generation_config,
        }

        logger.debug("Gemini request url=%s model=%s", url, self._model)

        start = time.monotonic()
        verify = get_settings().verify_ssl
        async with httpx.AsyncClient(verify=verify) as client:
            response = await client.post(
                url,
                json=payload,
                headers={"x-goog-api-key": self._api_key},
                timeout=30.0,
            )
            if response.is_error:
                logger.error(
                    "Gemini HTTP error status=%d body=%s",
                    response.status_code,
                    response.text[:500],
                )
            response.raise_for_status()
            data = response.json()

        latency_ms = int((time.monotonic() - start) * 1000)

        candidates = data.get("candidates", [])
        if not candidates:
            logger.error("Gemini empty candidates. full_response=%s", data)
            raise RuntimeError("Gemini returned no candidates")

        candidate = candidates[0]
        finish_reason = candidate.get("finishReason", "UNKNOWN")
        content_block = candidate.get("content", {})

        parts = content_block.get("parts", [])
        if not parts:
            logger.error(
                "Gemini empty parts. finishReason=%s candidate=%s",
                finish_reason,
                candidate,
            )
            raise RuntimeError(f"Gemini returned empty response (finishReason={finish_reason})")

        content = parts[0].get("text", "")

        usage = data.get("usageMetadata", {})

        logger.info(
            "Gemini response latency=%dms tokens_in=%s tokens_out=%s",
            latency_ms,
            usage.get("promptTokenCount", 0),
            usage.get("candidatesTokenCount", 0),
        )

        return LLMResponse(
            content=content,
            tokens_in=usage.get("promptTokenCount", 0),
            tokens_out=usage.get("candidatesTokenCount", 0),
            model=self._model,
            latency_ms=latency_ms,
        )

    async def test_connection(self) -> bool:
        logger.info("Gemini test_connection started model=%s", self._model)
        try:
            response = await self.generate(
                system_prompt="Reply with exactly: OK",
                user_content="test",
                max_tokens=50,
                response_mime_type=None,
            )
            ok = "OK" in response.content
            logger.info("Gemini test_connection result=%s content=%r", ok, response.content)
            return ok
        except Exception:
            logger.exception("Gemini test_connection failed for model=%s", self._model)
            return False
