from __future__ import annotations

import asyncio

from hazlo.infrastructure.db.repositories import SourceRepository
from hazlo.infrastructure.db.session import async_session_factory
from hazlo.infrastructure.prefect.source_deployment_manager import SourceDeploymentManager


async def _reconcile() -> None:
    manager = SourceDeploymentManager()
    await manager.cleanup_legacy_deployments()

    async with async_session_factory() as session:
        source_repo = SourceRepository(session)
        sources = await source_repo.list_all()

    for source in sources:
        await manager.sync_source(source)


def main() -> None:
    asyncio.run(_reconcile())


if __name__ == "__main__":
    main()
