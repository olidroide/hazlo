"""LLM-based unified event reparse using pydantic-ai structured output."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

from pydantic_ai import Agent

from hazlo.domain.llm_output import ReparseEventOutput
from hazlo.infrastructure.llm.prompts import REPARSE_EVENT_V1

if TYPE_CHECKING:
    from pydantic_ai.models import Model

logger = logging.getLogger(__name__)


class ReparseEventAgent:
    """LLM-based unified event reparse using pydantic-ai structured output.

    Takes raw payload + raw body and extracts all event fields in one call.
    """

    def __init__(self, model: Model, retries: int = 3) -> None:
        self._agent = Agent(
            model,
            output_type=ReparseEventOutput,
            instructions=REPARSE_EVENT_V1,
            retries=retries,
        )

    async def reparse(
        self, raw_payload: dict[str, object], raw_body: str, existing_event: dict[str, object]
    ) -> ReparseEventOutput:
        user_content = f"RAW payload: {raw_payload}\nRAW body: {raw_body[:8000]}\nExisting event: {existing_event}\n"

        try:
            result = await self._agent.run(user_content)
            output = cast(ReparseEventOutput, result.output)
            logger.info(
                "Reparse result: title='%s', address='%s', neighborhood='%s', confidence=%.2f",
                output.title,
                output.address,
                output.neighborhood,
                output.confidence,
            )
            return output
        except Exception as exc:
            logger.warning("Reparse failed: %s", exc)
            raise
