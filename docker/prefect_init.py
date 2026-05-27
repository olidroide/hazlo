"""Prefect init: create work pool and deploy flows. Idempotent — safe to re-run."""

from __future__ import annotations

import asyncio
import logging
import os
import sys

from prefect.client.orchestration import get_client
from prefect.client.schemas.actions import WorkPoolCreate

from hazlo.infrastructure.db.repositories import SourceRepository
from hazlo.infrastructure.db.session import async_session_factory
from hazlo.infrastructure.prefect.source_deployment_manager import SourceDeploymentManager
from hazlo.settings import get_settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

settings = get_settings()
API_URL = os.environ.get("PREFECT_API_URL") or settings.prefect_api_url
if not API_URL:
    logger.error("PREFECT_API_URL not set")
    sys.exit(1)

os.environ["PREFECT_API_URL"] = API_URL

logger.info("PREFECT_API_URL=%s", API_URL)


async def _create_work_pool() -> None:
    """Create configured work pool if it doesn't exist."""
    work_pool_name = settings.prefect_work_pool_name
    async with get_client() as client:
        pools = await client.read_work_pools()
        if any(p.name == work_pool_name for p in pools):
            logger.info("Work pool '%s' already exists", work_pool_name)
        else:
            await client.create_work_pool(WorkPoolCreate(name=work_pool_name, type="process"))
            logger.info("Work pool '%s' created", work_pool_name)


async def _reconcile_source_deployments() -> None:
    """Create/update/pause one deployment per source and remove legacy globals."""
    manager = SourceDeploymentManager()
    await manager.cleanup_legacy_deployments()

    async with async_session_factory() as session:
        source_repo = SourceRepository(session)
        sources = await source_repo.list_all()

    for source in sources:
        await manager.sync_source(source)

    logger.info("Reconciled source deployments: %d", len(sources))


def main() -> None:
    asyncio.run(_create_work_pool())
    asyncio.run(_reconcile_source_deployments())


if __name__ == "__main__":
    main()
