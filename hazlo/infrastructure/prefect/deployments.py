from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from prefect.schedules import Interval

from hazlo.infrastructure.prefect.flows import (
    ingest_all_sources_flow,
    ingest_single_source_flow,
)

_FLOWS_DIR = str(Path(__file__).resolve().parent)

_MODULE_INGEST_ALL = "hazlo.infrastructure.prefect.flows.ingest_all_sources_flow"
_MODULE_INGEST_SINGLE = "hazlo.infrastructure.prefect.flows.ingest_single_source_flow"


def main() -> None:
    schedule = Interval(timedelta(minutes=30))

    ingest_all_sources_flow.from_source(
        source=_FLOWS_DIR,
        entrypoint=_MODULE_INGEST_ALL,
    ).deploy(  # ty: ignore
        name="every-30-minutes",
        schedule=schedule,
        work_pool_name="local-pool",
    )

    ingest_single_source_flow.from_source(
        source=_FLOWS_DIR,
        entrypoint=_MODULE_INGEST_SINGLE,
    ).deploy(  # ty: ignore
        name="manual-trigger",
        work_pool_name="local-pool",
    )


if __name__ == "__main__":
    main()
