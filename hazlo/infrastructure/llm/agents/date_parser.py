from __future__ import annotations

import logging
from dataclasses import replace
from datetime import datetime
from typing import TYPE_CHECKING, cast

from pydantic_ai import Agent

from hazlo.domain.event import Event
from hazlo.domain.llm_output import DateParsingOutput
from hazlo.infrastructure.llm.prompts import DATE_PARSING_V1

if TYPE_CHECKING:
    from pydantic_ai.models import Model

logger = logging.getLogger(__name__)


class DateParserAgent:
    """LLM-based date parsing using pydantic-ai structured output.

    Extracts correct start_at and end_at from natural language text
    (title, description, schedule) when XML feed dates are unreliable.
    """

    def __init__(self, model: Model, retries: int = 3) -> None:
        self._agent = Agent(
            model,
            output_type=DateParsingOutput,
            instructions=DATE_PARSING_V1,
            retries=retries,
        )

    async def parse_dates(self, event: Event) -> Event:
        user_content = (
            f"Title: {event.title}\n"
            f"Description: {event.description or 'N/A'}\n"
            f"Schedule: {event.raw_description or 'N/A'}\n"
            f"Raw XML start: {event.start_at.isoformat() if event.start_at else 'null'}\n"
            f"Raw XML end: {event.end_at.isoformat() if event.end_at else 'null'}\n"
        )

        try:
            result = await self._agent.run(user_content)
            output = cast(DateParsingOutput, result.output)
            logger.info(
                "Date parser for %s: start=%s, end=%s, confidence=%.2f",
                event.title,
                output.start_at,
                output.end_at,
                output.confidence,
            )

            if output.confidence < 0.3:
                logger.info("Date parser low confidence for %s, keeping original", event.title)
                return event

            new_start = datetime.fromisoformat(output.start_at) if output.start_at else event.start_at
            new_end = datetime.fromisoformat(output.end_at) if output.end_at else event.end_at

            if new_start == event.start_at and new_end == event.end_at:
                logger.info("Date parser no delta for %s, skipping", event.title)
                return event

            logger.info(
                "Date parser updated %s: start %s→%s, end %s→%s",
                event.title,
                event.start_at,
                new_start,
                event.end_at,
                new_end,
            )
            return replace(event, start_at=new_start, end_at=new_end)
        except Exception as exc:
            logger.warning("Date parsing failed for %s: %s", event.title, exc)
            return event
