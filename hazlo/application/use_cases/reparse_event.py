"""Use case: reparse an event from stored RAW using unified LLM agent."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Protocol

from hazlo.domain.event import Event, Location, Price, TicketInfo
from hazlo.domain.llm_output import ReparseEventOutput
from hazlo.domain.review import Review, ReviewAction


@dataclass
class RawDocForReparse:
    payload: dict[str, object]
    body: bytes


class ReparseEventAgentProtocol(Protocol):
    async def reparse(
        self,
        raw_payload: dict[str, object],
        raw_body: str,
        existing_event: dict[str, object],
    ) -> ReparseEventOutput: ...


class RawDocumentStoreProtocol(Protocol):
    def read(self, event_id: uuid.UUID) -> RawDocForReparse: ...


@dataclass
class ReparseResult:
    event: Event
    review: Review
    fields_changed: list[str] = field(default_factory=list)
    reasoning: str = ""


class ReparseEvent:
    def __init__(
        self,
        agent: ReparseEventAgentProtocol,
        raw_store: RawDocumentStoreProtocol,
    ) -> None:
        self._agent = agent
        self._raw_store = raw_store

    async def execute(self, event: Event) -> ReparseResult:
        raw_doc = self._raw_store.read(event.id)
        if not isinstance(raw_doc, RawDocForReparse):
            msg = "Raw store returned unexpected type"
            raise TypeError(msg)
        raw_payload = raw_doc.payload
        raw_body = raw_doc.body.decode("utf-8")

        output = await self._agent.reparse(
            raw_payload=raw_payload,
            raw_body=raw_body,
            existing_event=event.to_dict(),
        )

        updated = self._apply_reparse(event, output)
        fields_changed = self._compute_delta(event, updated)

        review = Review(
            id=uuid.uuid4(),
            event_id=event.id,
            reviewer_id=uuid.uuid4(),
            action=ReviewAction.EDIT,
            changes={f: {"before": getattr(event, f), "after": getattr(updated, f)} for f in fields_changed},
            reviewed_at=datetime.now(UTC),
        )

        return ReparseResult(
            event=updated,
            review=review,
            fields_changed=fields_changed,
            reasoning=output.reasoning,
        )

    @staticmethod
    def _apply_reparse(event: Event, output: ReparseEventOutput) -> Event:
        location = Location(
            address=output.address or event.location.address if event.location else output.address,
            neighborhood=output.neighborhood or (event.location.neighborhood if event.location else ""),
            metro=output.metro or (event.location.metro if event.location else None),
        )
        price = Price(
            amount_cents=output.price_amount_cents,
            is_free=output.is_free,
            notes=output.price_notes,
        )
        ticket_info = TicketInfo(
            url=output.ticket_url,
            notes=output.ticket_notes,
        )

        from datetime import datetime as dt

        start_at = dt.fromisoformat(output.start_at) if output.start_at else event.start_at
        end_at = dt.fromisoformat(output.end_at) if output.end_at else event.end_at

        return replace(
            event,
            title=output.title or event.title,
            description=output.description or event.description,
            location=location,
            start_at=start_at,
            end_at=end_at,
            price=price,
            ticket_info=ticket_info,
            is_children_activity=output.is_children_activity,
            is_toddler_friendly=output.is_toddler_friendly,
            confidence_score=output.confidence,
            agent_review={
                **(event.agent_review or {}),
                "reparse_output": output.model_dump(),
                "reparse_reasoning": output.reasoning,
            },
            updated_at=datetime.now(UTC),
        )

    @staticmethod
    def _compute_delta(old: Event, new: Event) -> list[str]:
        changed = []
        for field_name in (
            "title",
            "description",
            "location",
            "start_at",
            "end_at",
            "price",
            "ticket_info",
            "is_children_activity",
            "is_toddler_friendly",
            "confidence_score",
        ):
            if getattr(old, field_name) != getattr(new, field_name):
                changed.append(field_name)
        return changed
