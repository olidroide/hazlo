"""Prefect init: create work pool and deploy flows. Idempotent — safe to re-run."""
from __future__ import annotations

import asyncio
import logging
import os
import sys

from prefect.client.orchestration import get_client
from prefect.client.schemas.actions import WorkPoolCreate

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

API_URL = os.environ.get("PREFECT_API_URL")
if not API_URL:
    logger.error("PREFECT_API_URL not set")
    sys.exit(1)

logger.info("PREFECT_API_URL=%s", API_URL)


async def _create_work_pool() -> None:
    """Create 'local-pool' work pool if it doesn't exist."""
    async with get_client() as client:
        pools = await client.read_work_pools()
        if any(p.name == "local-pool" for p in pools):
            logger.info("Work pool 'local-pool' already exists")
        else:
            await client.create_work_pool(WorkPoolCreate(name="local-pool", type="process"))
            logger.info("Work pool 'local-pool' created")


async def _cleanup_deployments() -> None:
    """Delete old deployments to ensure clean re-deploy with correct entrypoints."""
    async with get_client() as client:
        deployments = await client.read_deployments()
        for dep in deployments:
            if dep.name in ("every-30-minutes", "manual-trigger"):
                await client.delete_deployment(dep.id)
                logger.info("Deleted old deployment: %s", dep.name)


async def _deploy_flows() -> None:
    """Register deployments via Prefect API with module-path entrypoints."""
    from datetime import timedelta

    from prefect.client.schemas.actions import DeploymentScheduleCreate
    from prefect.client.schemas.schedules import IntervalSchedule

    async with get_client() as client:
        flow_all = await client.create_flow_from_name("ingest-all-sources")
        flow_single = await client.create_flow_from_name("ingest-single-source")

        schedule_create = DeploymentScheduleCreate(
            schedule=IntervalSchedule(interval=timedelta(minutes=30)),
            active=True,
        )

        await client.create_deployment(
            flow_id=flow_all,
            name="every-30-minutes",
            entrypoint="hazlo.infrastructure.prefect.flows.ingest_all_sources_flow",
            path="/usr/local/lib/python3.13/site-packages/hazlo/infrastructure/prefect",
            work_pool_name="local-pool",
            pull_steps=[],
            paused=False,
            schedules=[schedule_create],
        )
        logger.info("Deployed: every-30-minutes (every 30 min)")

        await client.create_deployment(
            flow_id=flow_single,
            name="manual-trigger",
            entrypoint="hazlo.infrastructure.prefect.flows.ingest_single_source_flow",
            path="/usr/local/lib/python3.13/site-packages/hazlo/infrastructure/prefect",
            work_pool_name="local-pool",
            pull_steps=[],
            paused=False,
        )
        logger.info("Deployed: manual-trigger")


def main() -> None:
    asyncio.run(_create_work_pool())
    asyncio.run(_cleanup_deployments())
    asyncio.run(_deploy_flows())


if __name__ == "__main__":
    main()
