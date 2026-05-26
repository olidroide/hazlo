from __future__ import annotations

from hazlo.domain.event import Event


class DedupService:
    """Deterministic: detect duplicate events using title similarity + date match."""

    SIMILARITY_THRESHOLD: float = 0.85

    def execute(
        self,
        event: Event,
        existing_urls: set[str],
        existing_titles: list[tuple[str, str]] | None = None,
    ) -> bool:
        """Check if event is a duplicate.

        Input: Event, set of existing URLs, optional list of (title, date) tuples.
        Output: True if duplicate, False if unique.

        No side effects. No DB access.
        """
        if event.source_url and event.source_url in existing_urls:
            return True

        if existing_titles and event.title and event.start_at:
            event_date_str = event.start_at.strftime("%Y-%m-%d")
            for existing_title, existing_date in existing_titles:
                if event_date_str == existing_date:
                    similarity = self._title_similarity(event.title, existing_title)
                    if similarity >= self.SIMILARITY_THRESHOLD:
                        return True

        return False

    def _title_similarity(self, title1: str, title2: str) -> float:
        """Calculate Jaccard token similarity between two titles."""
        if not title1 or not title2:
            return 0.0

        t1 = title1.lower().strip()
        t2 = title2.lower().strip()

        if t1 == t2:
            return 1.0

        tokens1 = set(t1.split())
        tokens2 = set(t2.split())

        if not tokens1 or not tokens2:
            return 0.0

        intersection = tokens1 & tokens2
        union = tokens1 | tokens2

        return len(intersection) / len(union)
