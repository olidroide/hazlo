from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from hazlo.domain.event import Event, IdempotencyKey, Location, Price, TicketInfo


def _make_event(**kwargs: Any) -> Event:
    defaults: dict[str, Any] = {
        "title": "Test Event",
        "location": Location(address="Calle Mayor 1", neighborhood="Sol"),
        "start_at": datetime(2026, 6, 1, 20, 0, tzinfo=UTC),
        "end_at": datetime(2026, 6, 1, 22, 0, tzinfo=UTC),
        "price": Price(amount_cents=1000, is_free=False),
        "ticket_info": TicketInfo(url="https://tickets.example.com"),
        "source_url": "https://example.com/1",
    }
    defaults.update(kwargs)
    return Event(**defaults)


class TestIdempotencyKey:
    def test_deterministic_same_inputs_same_key(self) -> None:
        key1 = IdempotencyKey.from_event("https://example.com/1", "Test Event", datetime(2026, 6, 1, 20, 0, tzinfo=UTC))
        key2 = IdempotencyKey.from_event("https://example.com/1", "Test Event", datetime(2026, 6, 1, 20, 0, tzinfo=UTC))
        assert key1.value == key2.value

    def test_different_url_different_key(self) -> None:
        key1 = IdempotencyKey.from_event("https://example.com/1", "Test Event", datetime(2026, 6, 1, 20, 0, tzinfo=UTC))
        key2 = IdempotencyKey.from_event("https://example.com/2", "Test Event", datetime(2026, 6, 1, 20, 0, tzinfo=UTC))
        assert key1.value != key2.value

    def test_different_title_different_key(self) -> None:
        key1 = IdempotencyKey.from_event("https://example.com/1", "Test Event", datetime(2026, 6, 1, 20, 0, tzinfo=UTC))
        key2 = IdempotencyKey.from_event(
            "https://example.com/1", "Other Event", datetime(2026, 6, 1, 20, 0, tzinfo=UTC)
        )
        assert key1.value != key2.value

    def test_different_date_different_key(self) -> None:
        key1 = IdempotencyKey.from_event("https://example.com/1", "Test Event", datetime(2026, 6, 1, 20, 0, tzinfo=UTC))
        key2 = IdempotencyKey.from_event("https://example.com/1", "Test Event", datetime(2026, 6, 2, 20, 0, tzinfo=UTC))
        assert key1.value != key2.value

    def test_title_normalization_case_insensitive(self) -> None:
        key1 = IdempotencyKey.from_event("https://example.com/1", "Test Event", datetime(2026, 6, 1, 20, 0, tzinfo=UTC))
        key2 = IdempotencyKey.from_event("https://example.com/1", "test event", datetime(2026, 6, 1, 20, 0, tzinfo=UTC))
        assert key1.value == key2.value

    def test_title_normalization_whitespace(self) -> None:
        key1 = IdempotencyKey.from_event("https://example.com/1", "Test Event", datetime(2026, 6, 1, 20, 0, tzinfo=UTC))
        key2 = IdempotencyKey.from_event(
            "https://example.com/1", "  Test  Event  ", datetime(2026, 6, 1, 20, 0, tzinfo=UTC)
        )
        assert key1.value == key2.value

    def test_none_start_at_produces_key(self) -> None:
        key = IdempotencyKey.from_event("https://example.com/1", "Test Event", None)
        assert key.value is not None
        assert len(key.value) == 64

    def test_key_is_sha256_hex(self) -> None:
        key = IdempotencyKey.from_event("https://example.com/1", "Test Event", datetime(2026, 6, 1, 20, 0, tzinfo=UTC))
        assert len(key.value) == 64
        int(key.value, 16)

    def test_event_compute_idempotency_key(self) -> None:
        event = _make_event()
        key = event.compute_idempotency_key()
        assert key.value is not None
        assert len(key.value) == 64

    def test_event_with_same_attributes_same_key(self) -> None:
        event1 = _make_event()
        event2 = _make_event()
        assert event1.compute_idempotency_key().value == event2.compute_idempotency_key().value

    def test_event_with_different_source_url_different_key(self) -> None:
        event1 = _make_event(source_url="https://example.com/1")
        event2 = _make_event(source_url="https://example.com/2")
        assert event1.compute_idempotency_key().value != event2.compute_idempotency_key().value
