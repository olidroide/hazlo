from __future__ import annotations

from abc import ABC, abstractmethod

from hazlo.domain.event import Event


class BaseSourceAdapter(ABC):
    @abstractmethod
    async def fetch(self, source_url: str) -> list[dict]:
        """Returns raw event dicts from the source."""
        ...

    @abstractmethod
    async def normalize(self, raw: dict) -> Event:
        """Normalizes raw dict to domain Event entity."""
        ...
