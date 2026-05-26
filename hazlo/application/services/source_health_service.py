from __future__ import annotations

import uuid
from datetime import UTC, datetime

from hazlo.domain.source_health import SourceHealth


class SourceHealthService:
    """Compute source health metrics from extraction run history."""

    def compute(self, extraction_runs: list[dict]) -> SourceHealth:
        health = SourceHealth()
        if not extraction_runs:
            return health

        health.total_runs = len(extraction_runs)
        confidence_scores: list[float] = []

        for run in extraction_runs:
            if run.get("status") == "error":
                health.total_errors += 1
                health.last_failure_at = run.get("finished_at") or run.get("started_at")
            else:
                health.last_success_at = run.get("finished_at") or run.get("started_at")
                events_found = run.get("events_found", 0)
                if events_found > 0:
                    avg_confidence = run.get("avg_confidence") or 0.0
                    confidence_scores.append(avg_confidence)

        health.failure_rate = health.total_errors / health.total_runs if health.total_runs > 0 else 0.0
        health.events_per_run_avg = sum(r.get("events_found", 0) for r in extraction_runs) / health.total_runs
        health.avg_confidence_score = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
        health.updated_at = datetime.now(UTC)

        return health

    def compute_for_source(
        self,
        source_id: uuid.UUID,
        extraction_runs: list[dict],
    ) -> SourceHealth:
        health = self.compute(extraction_runs)
        health.source_id = source_id
        return health
