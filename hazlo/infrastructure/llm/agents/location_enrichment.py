from __future__ import annotations

import logging
from dataclasses import replace
from typing import TYPE_CHECKING, cast

from pydantic_ai import Agent

from hazlo.domain.event import Event, Location
from hazlo.domain.llm_output import LocationEnrichmentOutput
from hazlo.infrastructure.llm.prompts import LOCATION_ENRICHMENT_V1

if TYPE_CHECKING:
    from pydantic_ai.models import Model

logger = logging.getLogger(__name__)


class LocationEnrichmentAgent:
    """LLM-based location enrichment using pydantic-ai structured output."""

    def __init__(self, model: Model, retries: int = 3) -> None:
        self._agent = Agent(
            model,
            output_type=LocationEnrichmentOutput,
            instructions=LOCATION_ENRICHMENT_V1,
            retries=retries,
        )

    async def enrich_location(self, event: Event) -> Event:
        if event.location is None:
            return event

        user_content = f"Event title: {event.title}\nRaw address: {event.location.address}"

        try:
            result = await self._agent.run(user_content)
            output = cast(LocationEnrichmentOutput, result.output)
            enriched = Location(
                address=output.normalized_address or event.location.address,
                neighborhood=output.neighborhood or event.location.neighborhood,
                metro=output.metro if output.metro else event.location.metro,
            )
            return replace(event, location=enriched)
        except Exception as exc:
            logger.warning("Location enrichment failed for %s: %s", event.title, exc)
            return event
