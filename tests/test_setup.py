from unittest.mock import AsyncMock, Mock

import kubespawner
import pytest
from traitlets.config import Config

from jupyterhub_usage_quotas import setup_usage_quotas
from jupyterhub_usage_quotas.manager import UsageQuotaManager
from tests.conftest import MockUser


@pytest.fixture
def mock_setup_dependencies(mocker):
    """Mock side-effects of setup_usage_quotas for hook-chaining tests."""
    mocker.patch("jupyterhub_usage_quotas.Counter")
    mocker.patch("jupyterhub_usage_quotas.MetricsExporter")
    mocker.patch.object(
        UsageQuotaManager,
        "enforce",
        new_callable=AsyncMock,
        return_value={"allow_server_launch": True},
    )


async def test_pre_spawn_hook_with_unset_existing_hook(mock_setup_dependencies):
    """
    setup_usage_quotas must not crash when c.Spawner.pre_spawn_hook has never
    been set. traitlets returns a LazyConfigValue (not None) in that case.
    """
    c = Config()
    setup_usage_quotas(c)

    spawner = kubespawner.KubeSpawner(_mock=True, user=MockUser())
    await c.KubeSpawner.pre_spawn_hook(spawner)


async def test_pre_spawn_hook_calls_existing_sync_hook(mock_setup_dependencies):
    """
    When an existing sync callable pre_spawn_hook is configured, setup_usage_quotas
    must call it when the hook fires.
    """
    c = Config()
    existing_hook = Mock()
    c.Spawner.pre_spawn_hook = existing_hook

    setup_usage_quotas(c)

    spawner = kubespawner.KubeSpawner(_mock=True, user=MockUser())
    await c.KubeSpawner.pre_spawn_hook(spawner)

    existing_hook.assert_called_once_with(spawner)


async def test_pre_spawn_hook_calls_existing_async_hook(mock_setup_dependencies):
    """
    When an existing async callable pre_spawn_hook is configured, setup_usage_quotas
    must await it when the hook fires.
    """
    c = Config()
    existing_hook = AsyncMock()
    c.Spawner.pre_spawn_hook = existing_hook

    setup_usage_quotas(c)

    spawner = kubespawner.KubeSpawner(_mock=True, user=MockUser())
    await c.KubeSpawner.pre_spawn_hook(spawner)

    existing_hook.assert_awaited_once_with(spawner)
