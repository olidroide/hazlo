from __future__ import annotations

import logging
from dataclasses import replace
from typing import TYPE_CHECKING, cast

from pydantic_ai import Agent

from hazlo.domain.event import Event, Location
from hazlo.domain.llm_output import LocationEnrichmentOutput
from hazlo.infrastructure.llm.prompts import LOCATION_ENRICHMENT_V2

if TYPE_CHECKING:
    from pydantic_ai.models import Model

logger = logging.getLogger(__name__)


class LocationEnrichmentAgent:
    """LLM-based location enrichment using pydantic-ai structured output."""

    def __init__(self, model: Model, retries: int = 3) -> None:
        self._agent = Agent(
            model,
            output_type=LocationEnrichmentOutput,
            instructions=LOCATION_ENRICHMENT_V2,
            retries=retries,
        )

    async def enrich_location(self, event: Event) -> Event:
        if event.location is None:
            logger.info("No location for event %s, skipping enrichment", event.id)
            return event

        user_content = (
            f"Event title: {event.title}\n"
            f"Event description: {event.description or 'N/A'}\n"
            f"Raw address: {event.location.address}\n"
        )
        logger.info(
            "Sending to LLM: title='%s', address='%s', description='%s'",
            event.title,
            event.location.address,
            event.description or "N/A",
        )

        try:
            result = await self._agent.run(user_content)
            output = cast(LocationEnrichmentOutput, result.output)
            logger.info(
                "LLM returned: address='%s', neighborhood='%s', metro='%s'",
                output.normalized_address,
                output.neighborhood,
                output.metro,
            )
            enriched = Location(
                address=output.normalized_address or event.location.address,
                neighborhood=output.neighborhood or event.location.neighborhood,
                metro=output.metro if output.metro else event.location.metro,
            )

            has_delta = (
                enriched.address != event.location.address
                or enriched.neighborhood != event.location.neighborhood
                or enriched.metro != event.location.metro
            )
            if not has_delta:
                logger.info("Enrichment no delta for %s, skipping save", event.id)
                return event

            return replace(event, location=enriched)
        except Exception as exc:
            logger.warning(
                "Location enrichment failed for %s (title='%s', address='%s'): %s",
                event.id,
                event.title,
                event.location.address,
                exc,
            )
            return event
