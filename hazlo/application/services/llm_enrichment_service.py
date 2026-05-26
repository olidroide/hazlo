"""LLM-based location enrichment service."""

from __future__ import annotations

import json
import logging
from dataclasses import replace

from hazlo.domain.event import Event, Location
from hazlo.infrastructure.llm.client import LLMClient
from hazlo.infrastructure.llm.prompts import LOCATION_ENRICHMENT_V1

logger = logging.getLogger(__name__)


class LLMEnrichmentService:
    """Enriches event locations using LLM for address normalization, neighborhood and metro detection."""

    def __init__(self, llm_client: LLMClient) -> None:
        self._llm = llm_client

    async def enrich_location(self, event: Event) -> Event:
        """Enrich event location with normalized address, neighborhood, and metro.

        Args:
            event: Event to enrich

        Returns:
            Event with enriched location, or original event if enrichment fails
        """
        if event.location is None:
            return event

        try:
            system_prompt, user_content = self._build_prompt(event)
            response = await self._llm.generate(system_prompt, user_content, action="enrich_location")

            enriched_location = self._parse_response(response.content, event.location)
            if enriched_location is None:
                return event

            return replace(event, location=enriched_location)

        except Exception as exc:
            logger.warning("LLM location enrichment failed for event %s: %s", event.title, exc)
            return event

    def _build_prompt(self, event: Event) -> tuple[str, str]:
        """Build LLM prompt for location enrichment.

        Returns:
            Tuple of (system_prompt, user_content)
        """
        assert event.location is not None
        user_content = f"Event title: {event.title}\nRaw address: {event.location.address}"
        return LOCATION_ENRICHMENT_V1, user_content

    def _parse_response(self, response: str, original: Location) -> Location | None:
        """Parse LLM response into Location object.

        Returns None if response is invalid or incomplete.
        """
        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            logger.warning("Invalid JSON response from LLM: %s", response[:100])
            return None

        if not isinstance(data, dict):
            logger.warning("LLM response is not a dict: %s", type(data))
            return None

        normalized_address = data.get("normalized_address")
        neighborhood = data.get("neighborhood")
        metro = data.get("metro")

        if not all(isinstance(field, str) for field in [normalized_address, neighborhood, metro]):
            logger.warning("LLM response missing required fields")
            return None

        return Location(
            address=normalized_address or original.address,
            neighborhood=neighborhood or original.neighborhood,
            metro=metro if metro else original.metro,
        )
