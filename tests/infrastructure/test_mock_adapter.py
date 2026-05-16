from __future__ import annotations

import pytest

from hazlo.infrastructure.adapters.mock_adapter import MockSourceAdapter


@pytest.mark.asyncio
async def test_mock_adapter_returns_valid_events() -> None:
    adapter = MockSourceAdapter()
    raw_events = await adapter.fetch("https://example.com")

    assert len(raw_events) == 3

    for raw in raw_events:
        event = await adapter.normalize(raw)
        assert event.title
        assert event.location
        assert event.start_at
        assert event.price
        assert event.source_url
        assert event.extracted_at
