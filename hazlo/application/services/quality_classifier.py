from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from hazlo.domain.event import Event
from hazlo.infrastructure.llm import LLMClient
from hazlo.infrastructure.llm.prompts import QUALITY_CLASSIFIER_V1

logger = logging.getLogger(__name__)


@dataclass
class ClassificationResult:
    is_children_activity: bool
    is_toddler_friendly: bool
    confidence: float
    raw_response: str


class QualityClassifier:
    """LLM: classify event properties + confidence score."""

    def __init__(self, llm_client: LLMClient) -> None:
        self._client = llm_client

    async def execute(self, event: Event) -> ClassificationResult:
        """Input: Event domain object. Output: ClassificationResult.

        Single LLM call. Structured output via Pydantic.
        """
        user_content = self._build_prompt(event)

        response = await self._client.generate(
            system_prompt=QUALITY_CLASSIFIER_V1,
            user_content=user_content,
            action="classify",
            temperature=0.0,
            max_tokens=200,
        )

        return self._parse_response(response.content)

    def _build_prompt(self, event: Event) -> str:
        parts = [
            f"Title: {event.title}",
        ]
        if event.location:
            parts.append(f"Location: {event.location.address}")
            if event.location.neighborhood:
                parts.append(f"Neighborhood: {event.location.neighborhood}")
        if event.start_at:
            parts.append(f"Start: {event.start_at.isoformat()}")
        if event.end_at:
            parts.append(f"End: {event.end_at.isoformat()}")
        if event.price:
            if event.price.is_free:
                parts.append("Price: Free")
            elif event.price.amount_cents is not None:
                parts.append(f"Price: {event.price.amount_euros:.2f}€")
        if event.ticket_info and event.ticket_info.notes:
            parts.append(f"Ticket notes: {event.ticket_info.notes}")

        return "\n".join(parts)

    def _parse_response(self, content: str) -> ClassificationResult:
        """Parse JSON response from LLM."""
        try:
            data = json.loads(content.strip())
            return ClassificationResult(
                is_children_activity=bool(data.get("is_children_activity", False)),
                is_toddler_friendly=bool(data.get("is_toddler_friendly", False)),
                confidence=float(data.get("confidence", 0.5)),
                raw_response=content,
            )
        except (json.JSONDecodeError, ValueError, KeyError) as exc:
            logger.warning("Failed to parse LLM response: %s", exc)
            return ClassificationResult(
                is_children_activity=False,
                is_toddler_friendly=False,
                confidence=0.0,
                raw_response=content,
            )
