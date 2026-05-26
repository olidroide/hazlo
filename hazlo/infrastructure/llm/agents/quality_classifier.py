from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

from pydantic_ai import Agent

from hazlo.domain.event import Event
from hazlo.domain.llm_output import ClassificationOutput, ClassificationResult
from hazlo.infrastructure.llm.prompts import QUALITY_CLASSIFIER_V1

if TYPE_CHECKING:
    from pydantic_ai.models import Model

logger = logging.getLogger(__name__)


class QualityClassifierAgent:
    """LLM-based event classifier using pydantic-ai structured output."""

    def __init__(self, model: Model, retries: int = 3) -> None:
        self._agent = Agent(
            model,
            output_type=ClassificationOutput,
            instructions=QUALITY_CLASSIFIER_V1,
            retries=retries,
        )

    async def execute(self, event: Event) -> ClassificationResult:
        user_content = self._build_prompt(event)

        try:
            result = await self._agent.run(user_content)
            output = cast(ClassificationOutput, result.output)
            return ClassificationResult(
                is_children_activity=output.is_children_activity,
                is_toddler_friendly=output.is_toddler_friendly,
                confidence=output.confidence,
                raw_response=output.model_dump_json(),
            )
        except Exception as exc:
            logger.warning("Quality classification failed for %s: %s", event.title, exc)
            return ClassificationResult(
                is_children_activity=False,
                is_toddler_friendly=False,
                confidence=0.0,
                raw_response="",
            )

    def _build_prompt(self, event: Event) -> str:
        parts = [f"Title: {event.title}"]
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
