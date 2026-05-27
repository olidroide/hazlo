from __future__ import annotations

import logging
import os
from datetime import timedelta

from prefect.client.orchestration import get_client
from prefect.client.schemas.actions import (
    DeploymentScheduleCreate,
    DeploymentScheduleUpdate,
    DeploymentUpdate,
)
from prefect.client.schemas.schedules import IntervalSchedule

from hazlo.domain.source import Source
from hazlo.settings import get_settings

logger = logging.getLogger(__name__)

_INGEST_SINGLE_FLOW_NAME = "ingest-single-source"
_INGEST_SINGLE_ENTRYPOINT = "hazlo.infrastructure.prefect.flows.ingest_single_source_flow"
_INGEST_SINGLE_PATH = "/usr/local/lib/python3.13/site-packages/hazlo/infrastructure/prefect"


def source_deployment_name(source_id: str) -> str:
    return f"source-{source_id}"


class SourceDeploymentManager:
    def __init__(self) -> None:
        settings = get_settings()
        os.environ.setdefault("PREFECT_API_URL", settings.prefect_api_url)
        self._work_pool_name = settings.prefect_work_pool_name

    async def _read_source_deployment(self, source_id: str):
        deployment_name = source_deployment_name(source_id)
        async with get_client() as client:
            deployments = await client.read_deployments(limit=200)
            for deployment in deployments:
                if deployment.name == deployment_name:
                    return deployment
        return None

    async def sync_source(self, source: Source) -> None:
        source_id = str(source.id)
        deployment_name = source_deployment_name(source_id)
        schedule = DeploymentScheduleCreate(
            schedule=IntervalSchedule(interval=timedelta(minutes=source.fetch_interval_minutes)),
            active=True,
        )
        schedule_update = DeploymentScheduleUpdate(
            schedule=IntervalSchedule(interval=timedelta(minutes=source.fetch_interval_minutes)),
            active=True,
        )

        async with get_client() as client:
            deployments = await client.read_deployments(limit=200)
            existing = next((d for d in deployments if d.name == deployment_name), None)

            if source.is_active:
                flow_id = await client.create_flow_from_name(_INGEST_SINGLE_FLOW_NAME)
                if existing is None:
                    await client.create_deployment(
                        flow_id=flow_id,
                        name=deployment_name,
                        entrypoint=_INGEST_SINGLE_ENTRYPOINT,
                        path=_INGEST_SINGLE_PATH,
                        work_pool_name=self._work_pool_name,
                        pull_steps=[],
                        paused=False,
                        parameters={"source_id": source_id},
                        schedules=[schedule],
                        tags=[f"source:{source_id}"],
                    )
                    logger.info("Created deployment %s (%d min)", deployment_name, source.fetch_interval_minutes)
                    return

                await client.update_deployment(
                    deployment_id=existing.id,
                    deployment=DeploymentUpdate(
                        schedules=[schedule_update],
                        paused=False,
                        parameters={"source_id": source_id},
                        work_pool_name=self._work_pool_name,
                        entrypoint=_INGEST_SINGLE_ENTRYPOINT,
                        path=_INGEST_SINGLE_PATH,
                        tags=[f"source:{source_id}"],
                    ),
                )
                logger.info("Updated deployment %s (%d min)", deployment_name, source.fetch_interval_minutes)
                return

            if existing is not None:
                await client.set_deployment_paused_state(existing.id, True)
                logger.info("Paused deployment %s", deployment_name)

    async def delete_source_deployment(self, source_id: str) -> None:
        deployment_name = source_deployment_name(source_id)

        async with get_client() as client:
            deployments = await client.read_deployments(limit=200)
            existing = next((d for d in deployments if d.name == deployment_name), None)
            if existing is None:
                return
            await client.delete_deployment(existing.id)
            logger.info("Deleted deployment %s", deployment_name)

    async def trigger_run(self, source: Source) -> str:
        source_id = str(source.id)

        await self.sync_source(source)
        deployment = await self._read_source_deployment(source_id)
        if deployment is None:
            msg = f"Deployment not found for source {source_id}"
            raise RuntimeError(msg)

        async with get_client() as client:
            flow_run = await client.create_flow_run_from_deployment(
                deployment_id=deployment.id,
                parameters={"source_id": source_id},
                tags=["run-now", f"source:{source_id}"],
            )
        logger.info("Triggered run-now flow_run=%s for source=%s", flow_run.id, source_id)
        return str(flow_run.id)

    async def cleanup_legacy_deployments(self) -> None:
        legacy_names = {"every-30-minutes", "manual-trigger"}
        async with get_client() as client:
            deployments = await client.read_deployments(limit=200)
            for deployment in deployments:
                if deployment.name in legacy_names:
                    await client.delete_deployment(deployment.id)
                    logger.info("Deleted legacy deployment: %s", deployment.name)
