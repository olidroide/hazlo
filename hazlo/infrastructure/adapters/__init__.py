from __future__ import annotations

from hazlo.domain.source import SourceType
from hazlo.infrastructure.adapters.base import BaseSourceAdapter
from hazlo.infrastructure.adapters.mock_adapter import MockSourceAdapter

adapter_registry: dict[str, BaseSourceAdapter] = {
    SourceType.SCRAPER.value: MockSourceAdapter(),
    SourceType.API.value: MockSourceAdapter(),
    SourceType.CSV.value: MockSourceAdapter(),
}
