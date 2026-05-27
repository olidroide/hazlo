from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from hazlo.domain.source import Source, SourceType
from hazlo.infrastructure.prefect.source_deployment_manager import SourceDeploymentManager, source_deployment_name


class _ClientContext:
    def __init__(self, client) -> None:
        self._client = client

    async def __aenter__(self):
        return self._client

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


def _make_source(*, is_active: bool = True, fetch_interval_minutes: int = 90) -> Source:
    return Source(
        id=uuid.uuid4(),
        name="Madrid Feed",
        source_type=SourceType.RSS,
        url="https://example.com/rss.xml",
        is_active=is_active,
        fetch_interval_minutes=fetch_interval_minutes,
    )


@pytest.mark.asyncio
async def test_sync_source_creates_deployment_for_active_source() -> None:
    source = _make_source(is_active=True, fetch_interval_minutes=90)
    client = SimpleNamespace(
        read_deployments=AsyncMock(return_value=[]),
        create_flow_from_name=AsyncMock(return_value=uuid.uuid4()),
        create_deployment=AsyncMock(return_value=uuid.uuid4()),
    )

    manager = SourceDeploymentManager()

    with patch(
        "hazlo.infrastructure.prefect.source_deployment_manager.get_client",
        return_value=_ClientContext(client),
    ):
        await manager.sync_source(source)

    client.create_deployment.assert_awaited_once()
    _, kwargs = client.create_deployment.await_args
    assert kwargs["name"] == source_deployment_name(str(source.id))
    assert kwargs["parameters"] == {"source_id": str(source.id)}


@pytest.mark.asyncio
async def test_sync_source_pauses_deployment_for_inactive_source() -> None:
    source = _make_source(is_active=False)
    deployment = SimpleNamespace(id=uuid.uuid4(), name=source_deployment_name(str(source.id)))
    client = SimpleNamespace(
        read_deployments=AsyncMock(return_value=[deployment]),
        set_deployment_paused_state=AsyncMock(return_value=None),
    )

    manager = SourceDeploymentManager()

    with patch(
        "hazlo.infrastructure.prefect.source_deployment_manager.get_client",
        return_value=_ClientContext(client),
    ):
        await manager.sync_source(source)

    client.set_deployment_paused_state.assert_awaited_once_with(deployment.id, True)


@pytest.mark.asyncio
async def test_trigger_run_creates_flow_run_from_source_deployment() -> None:
    source = _make_source(is_active=True)
    deployment = SimpleNamespace(id=uuid.uuid4(), name=source_deployment_name(str(source.id)))
    flow_run = SimpleNamespace(id=uuid.uuid4())
    client = SimpleNamespace(
        create_flow_run_from_deployment=AsyncMock(return_value=flow_run),
    )

    manager = SourceDeploymentManager()

    with (
        patch.object(manager, "sync_source", AsyncMock(return_value=None)),
        patch.object(manager, "_read_source_deployment", AsyncMock(return_value=deployment)),
        patch(
            "hazlo.infrastructure.prefect.source_deployment_manager.get_client",
            return_value=_ClientContext(client),
        ),
    ):
        run_id = await manager.trigger_run(source)

    assert run_id == str(flow_run.id)
    client.create_flow_run_from_deployment.assert_awaited_once()
