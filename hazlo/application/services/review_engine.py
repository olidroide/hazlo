from __future__ import annotations

from dataclasses import dataclass

from hazlo.domain.event import Event, EventStatus


@dataclass
class ReviewDecision:
    action: EventStatus
    reason: str
    confidence_threshold: float


class ReviewEngine:
    """Rules: approve/reject/flag based on confidence + required fields."""

    def __init__(self, auto_approve_threshold: float = 0.95) -> None:
        self._auto_approve_threshold = auto_approve_threshold

    def execute(self, event: Event) -> ReviewDecision:
        """Input: scored Event. Output: ReviewDecision.

        Deterministic rules, no LLM calls.
        """
        if not event.title:
            return ReviewDecision(
                action=EventStatus.PENDING,
                reason="Missing required field: title",
                confidence_threshold=self._auto_approve_threshold,
            )

        if event.start_at is None:
            return ReviewDecision(
                action=EventStatus.PENDING,
                reason="Missing required field: start_at",
                confidence_threshold=self._auto_approve_threshold,
            )

        if event.requires_ticket_url() and (event.ticket_info is None or not event.ticket_info.url):
            return ReviewDecision(
                action=EventStatus.PENDING,
                reason="Paid event missing ticket URL",
                confidence_threshold=self._auto_approve_threshold,
            )

        if event.confidence_score is None:
            return ReviewDecision(
                action=EventStatus.PENDING,
                reason="No confidence score available",
                confidence_threshold=self._auto_approve_threshold,
            )

        if event.confidence_score >= self._auto_approve_threshold:
            return ReviewDecision(
                action=EventStatus.APPROVED,
                reason=f"Confidence {event.confidence_score:.2f} >= threshold {self._auto_approve_threshold:.2f}",
                confidence_threshold=self._auto_approve_threshold,
            )

        if event.confidence_score < 0.70:
            return ReviewDecision(
                action=EventStatus.PENDING,
                reason=f"Low confidence {event.confidence_score:.2f} < 0.70",
                confidence_threshold=self._auto_approve_threshold,
            )

        return ReviewDecision(
            action=EventStatus.PENDING,
            reason=f"Confidence {event.confidence_score:.2f} in review range (0.70-{self._auto_approve_threshold:.2f})",
            confidence_threshold=self._auto_approve_threshold,
        )
