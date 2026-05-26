from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class SourceHealth:
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    source_id: uuid.UUID = field(default_factory=uuid.uuid4)
    failure_rate: float = 0.0
    last_success_at: datetime | None = None
    last_failure_at: datetime | None = None
    events_per_run_avg: float = 0.0
    avg_confidence_score: float = 0.0
    total_runs: int = 0
    total_errors: int = 0
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def record_success(self, events_found: int, confidence_score: float | None = None) -> None:
        self.total_runs += 1
        self.last_success_at = datetime.now(UTC)
        self.events_per_run_avg = (self.events_per_run_avg * (self.total_runs - 1) + events_found) / self.total_runs
        if confidence_score is not None:
            self.avg_confidence_score = (
                self.avg_confidence_score * (self.total_runs - 1) + confidence_score
            ) / self.total_runs
        self.failure_rate = self.total_errors / self.total_runs if self.total_runs > 0 else 0.0
        self.updated_at = datetime.now(UTC)

    def record_failure(self) -> None:
        self.total_runs += 1
        self.total_errors += 1
        self.last_failure_at = datetime.now(UTC)
        self.failure_rate = self.total_errors / self.total_runs
        self.updated_at = datetime.now(UTC)
