from __future__ import annotations

from datetime import UTC, datetime

import pytest

from hazlo.application.services.source_health_service import SourceHealthService


def _make_run(status: str, events_found: int = 0, started_at: datetime | None = None) -> dict:
    return {
        "status": status,
        "events_found": events_found,
        "started_at": started_at or datetime.now(UTC),
        "finished_at": datetime.now(UTC),
    }


def test_compute_empty_history() -> None:
    service = SourceHealthService()
    health = service.compute([])
    assert health.total_runs == 0
    assert health.failure_rate == 0.0


def test_compute_all_success() -> None:
    service = SourceHealthService()
    runs = [
        _make_run("success", events_found=5),
        _make_run("success", events_found=10),
        _make_run("success", events_found=3),
    ]
    health = service.compute(runs)
    assert health.total_runs == 3
    assert health.total_errors == 0
    assert health.failure_rate == 0.0
    assert health.events_per_run_avg == 6.0


def test_compute_with_errors() -> None:
    service = SourceHealthService()
    runs = [
        _make_run("success", events_found=5),
        _make_run("error", events_found=0),
        _make_run("success", events_found=3),
    ]
    health = service.compute(runs)
    assert health.total_runs == 3
    assert health.total_errors == 1
    assert health.failure_rate == pytest.approx(1 / 3, abs=0.01)


def test_compute_for_source() -> None:
    import uuid

    service = SourceHealthService()
    source_id = uuid.uuid4()
    runs = [_make_run("success", events_found=5)]
    health = service.compute_for_source(source_id, runs)
    assert health.source_id == source_id
    assert health.total_runs == 1
