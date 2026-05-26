"""Tests for content hash computation in Event domain model."""

from __future__ import annotations

import pytest

from hazlo.domain.event import Event


@pytest.fixture
def sample_raw_event() -> dict[str, object]:
    """Sample raw event dict."""
    return {
        "title": "Concierto de Jazz",
        "description": "Noche de jazz en vivo",
        "location": "Calle Mayor 1, Madrid",
        "start_at": "2026-06-01T20:00:00",
        "end_at": "2026-06-01T22:00:00",
        "price": "15€",
        "ticket_info": "https://tickets.example.com",
        "source_url": "https://source.example.com/event/123",
    }


class TestComputeContentHash:
    """Test suite for Event.compute_content_hash()."""

    def test_compute_content_hash_deterministic(self, sample_raw_event: dict[str, object]) -> None:
        """Test that same input produces same hash."""
        hash1 = Event.compute_content_hash(sample_raw_event)
        hash2 = Event.compute_content_hash(sample_raw_event)
        assert hash1 == hash2

    def test_compute_content_hash_different_title(self, sample_raw_event: dict[str, object]) -> None:
        """Test that different title produces different hash."""
        hash1 = Event.compute_content_hash(sample_raw_event)
        modified = {**sample_raw_event, "title": "Concierto de Rock"}
        hash2 = Event.compute_content_hash(modified)
        assert hash1 != hash2

    def test_compute_content_hash_different_description(self, sample_raw_event: dict[str, object]) -> None:
        """Test that different description produces different hash."""
        hash1 = Event.compute_content_hash(sample_raw_event)
        modified = {**sample_raw_event, "description": "Noche de rock en vivo"}
        hash2 = Event.compute_content_hash(modified)
        assert hash1 != hash2

    def test_compute_content_hash_different_location(self, sample_raw_event: dict[str, object]) -> None:
        """Test that different location produces different hash."""
        hash1 = Event.compute_content_hash(sample_raw_event)
        modified = {**sample_raw_event, "location": "Calle Menor 2, Madrid"}
        hash2 = Event.compute_content_hash(modified)
        assert hash1 != hash2

    def test_compute_content_hash_different_start_at(self, sample_raw_event: dict[str, object]) -> None:
        """Test that different start_at produces different hash."""
        hash1 = Event.compute_content_hash(sample_raw_event)
        modified = {**sample_raw_event, "start_at": "2026-06-02T20:00:00"}
        hash2 = Event.compute_content_hash(modified)
        assert hash1 != hash2

    def test_compute_content_hash_different_price(self, sample_raw_event: dict[str, object]) -> None:
        """Test that different price produces different hash."""
        hash1 = Event.compute_content_hash(sample_raw_event)
        modified = {**sample_raw_event, "price": "20€"}
        hash2 = Event.compute_content_hash(modified)
        assert hash1 != hash2

    def test_compute_content_hash_ignores_extracted_at(self, sample_raw_event: dict[str, object]) -> None:
        """Test that extracted_at is ignored (not part of content)."""
        hash1 = Event.compute_content_hash(sample_raw_event)
        modified = {**sample_raw_event, "extracted_at": "2026-05-26T10:00:00"}
        hash2 = Event.compute_content_hash(modified)
        assert hash1 == hash2

    def test_compute_content_hash_ignores_source_url(self, sample_raw_event: dict[str, object]) -> None:
        """Test that source_url is ignored (not part of content)."""
        hash1 = Event.compute_content_hash(sample_raw_event)
        modified = {**sample_raw_event, "source_url": "https://other.example.com/event/456"}
        hash2 = Event.compute_content_hash(modified)
        assert hash1 == hash2

    def test_compute_content_hash_handles_none_values(self) -> None:
        """Test that None values are handled gracefully."""
        raw = {
            "title": "Evento",
            "description": None,
            "location": "Madrid",
            "start_at": "2026-06-01T20:00:00",
            "price": None,
        }
        hash_value = Event.compute_content_hash(raw)
        assert isinstance(hash_value, str)
        assert len(hash_value) == 64

    def test_compute_content_hash_handles_missing_keys(self) -> None:
        """Test that missing keys are handled gracefully."""
        raw = {
            "title": "Evento",
            "start_at": "2026-06-01T20:00:00",
        }
        hash_value = Event.compute_content_hash(raw)
        assert isinstance(hash_value, str)
        assert len(hash_value) == 64

    def test_compute_content_hash_order_independent(self, sample_raw_event: dict[str, object]) -> None:
        """Test that key order doesn't affect hash."""
        hash1 = Event.compute_content_hash(sample_raw_event)
        reordered = {
            "source_url": sample_raw_event["source_url"],
            "title": sample_raw_event["title"],
            "description": sample_raw_event["description"],
            "location": sample_raw_event["location"],
            "start_at": sample_raw_event["start_at"],
            "end_at": sample_raw_event["end_at"],
            "price": sample_raw_event["price"],
            "ticket_info": sample_raw_event["ticket_info"],
        }
        hash2 = Event.compute_content_hash(reordered)
        assert hash1 == hash2

    def test_compute_content_hash_is_sha256(self, sample_raw_event: dict[str, object]) -> None:
        """Hash should be a valid SHA-256 hex digest (64 characters)."""
        hash_value = Event.compute_content_hash(sample_raw_event)
        assert len(hash_value) == 64
        assert all(c in "0123456789abcdef" for c in hash_value)


class TestContentHashNormalization:
    """Test suite for Event.normalize_for_hash() and normalization behavior."""

    def test_normalize_whitespace_in_title(self) -> None:
        """Extra whitespace in title should be normalized."""
        event1 = {"title": "Concierto de Jazz", "start_at": "2026-06-01T20:00:00"}
        event2 = {"title": "Concierto  de   Jazz", "start_at": "2026-06-01T20:00:00"}
        event3 = {"title": "  Concierto de Jazz  ", "start_at": "2026-06-01T20:00:00"}

        hash1 = Event.compute_content_hash(event1)
        hash2 = Event.compute_content_hash(event2)
        hash3 = Event.compute_content_hash(event3)

        assert hash1 == hash2 == hash3

    def test_normalize_case_in_title(self) -> None:
        """Case differences in title should be normalized."""
        event1 = {"title": "Concierto de Jazz", "start_at": "2026-06-01T20:00:00"}
        event2 = {"title": "concierto de jazz", "start_at": "2026-06-01T20:00:00"}
        event3 = {"title": "CONCIERTO DE JAZZ", "start_at": "2026-06-01T20:00:00"}

        hash1 = Event.compute_content_hash(event1)
        hash2 = Event.compute_content_hash(event2)
        hash3 = Event.compute_content_hash(event3)

        assert hash1 == hash2 == hash3

    def test_normalize_whitespace_in_description(self) -> None:
        """Extra whitespace in description should be normalized."""
        event1 = {"title": "Jazz", "description": "Noche de jazz en vivo", "start_at": "2026-06-01T20:00:00"}
        event2 = {"title": "Jazz", "description": "Noche  de   jazz  en   vivo", "start_at": "2026-06-01T20:00:00"}

        hash1 = Event.compute_content_hash(event1)
        hash2 = Event.compute_content_hash(event2)

        assert hash1 == hash2

    def test_normalize_whitespace_in_location(self) -> None:
        """Extra whitespace in location should be normalized."""
        event1 = {"title": "Jazz", "location": "Calle Mayor 1, Madrid", "start_at": "2026-06-01T20:00:00"}
        event2 = {"title": "Jazz", "location": "Calle  Mayor   1,  Madrid", "start_at": "2026-06-01T20:00:00"}

        hash1 = Event.compute_content_hash(event1)
        hash2 = Event.compute_content_hash(event2)

        assert hash1 == hash2

    def test_normalize_datetime_formats(self) -> None:
        """Different datetime formats for same time should normalize."""
        event1 = {"title": "Jazz", "start_at": "2026-06-01T20:00:00"}
        event2 = {"title": "Jazz", "start_at": "2026-06-01T20:00:00Z"}
        event3 = {"title": "Jazz", "start_at": "2026-06-01T20:00:00+00:00"}

        hash1 = Event.compute_content_hash(event1)
        hash2 = Event.compute_content_hash(event2)
        hash3 = Event.compute_content_hash(event3)

        assert hash1 == hash2 == hash3

    def test_normalize_combined_variations(self) -> None:
        """Multiple normalization variations should produce same hash."""
        event1 = {
            "title": "Concierto de Jazz",
            "description": "Noche de jazz en vivo",
            "location": "Calle Mayor 1, Madrid",
            "start_at": "2026-06-01T20:00:00",
            "price": "15€",
        }
        event2 = {
            "title": "  CONCIERTO  DE  JAZZ  ",
            "description": "noche  de   jazz   en   vivo",
            "location": "calle  mayor  1,  madrid",
            "start_at": "2026-06-01T20:00:00Z",
            "price": "15€",
        }

        hash1 = Event.compute_content_hash(event1)
        hash2 = Event.compute_content_hash(event2)

        assert hash1 == hash2

    def test_different_content_still_different_hash(self) -> None:
        """Different content should still produce different hashes."""
        event1 = {"title": "Concierto de Jazz", "start_at": "2026-06-01T20:00:00"}
        event2 = {"title": "Concierto de Rock", "start_at": "2026-06-01T20:00:00"}

        hash1 = Event.compute_content_hash(event1)
        hash2 = Event.compute_content_hash(event2)

        assert hash1 != hash2

    def test_normalize_for_hash_preserves_none(self) -> None:
        """None values should be preserved in normalization."""
        raw = {"title": None, "description": None, "start_at": None}
        normalized = Event.normalize_for_hash(raw)

        assert normalized["title"] is None
        assert normalized["description"] is None
        assert normalized["start_at"] is None

    def test_normalize_for_hash_preserves_ticket_info(self) -> None:
        """ticket_info (URL) should not be normalized."""
        raw = {"ticket_info": "https://Tickets.Example.com/Event/123"}
        normalized = Event.normalize_for_hash(raw)

        assert normalized["ticket_info"] == "https://Tickets.Example.com/Event/123"
