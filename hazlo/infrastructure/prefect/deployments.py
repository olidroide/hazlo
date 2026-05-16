from __future__ import annotations

from datetime import timedelta

from prefect.schedules import Interval

from hazlo.infrastructure.prefect.flows import (
    ingest_all_sources_flow,
    ingest_single_source_flow,
)


def main() -> None:
    schedule = Interval(timedelta(minutes=30))

    ingest_all_sources_flow.to_deployment(
        name="every-30-minutes",
        schedule=schedule,
    )

    ingest_single_source_flow.to_deployment(
        name="manual-trigger",
    )


if __name__ == "__main__":
    main()
