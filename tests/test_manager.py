import logging
from unittest.mock import Mock

import kubespawner
import pytest
from jupyterhub.objects import Server
from traitlets.config import Config

from jupyterhub_usage_quotas.manager import UsageQuotaManager

logger = logging.getLogger(__name__)


class MockGroup(Mock):
    name = "test-group"

    def __init__(self, **kwargs):
        super().__init__()
        for key, value in kwargs.items():
            setattr(self, key, value)


class MockUser(Mock):
    name = "test-user"
    groups = []
    server = Server()

    def __init__(self, **kwargs):
        super().__init__()
        for key, value in kwargs.items():
            setattr(self, key, value)

    @property
    def escaped_name(self):
        return self.name

    @property
    def url(self):
        return self.server.url


async def test_resolve_policy_single():
    """
    Test policy resolver applies a single policy scope for group-0 to user-0.
    """
    spawner = kubespawner.KubeSpawner(
        _mock=True, user=MockUser(name="user-0", groups=[MockGroup(name="group-0")])
    )
    c = Config()
    c.UsageQuotaManager.scope_backup_strategy = {
        "empty": {
            "resource": "memory",
            "limit": {"value": 500, "unit": "GiB-hours"},
            "window": 7,
        },
        "intersection": "min",
    }
    c.UsageQuotaManager.policy = [
        {
            "resource": "memory",
            "limit": {
                "value": 5000,
                "unit": "GiB-hours",
            },
            "window": 30,
            "scope": {"group": ["group-0"]},
        },
    ]

    quota_manager = UsageQuotaManager(config=c)
    merged = quota_manager.resolve_policy(spawner)
    assert merged == quota_manager.policy


async def test_resolve_policy_multiple():
    """
    Test policy resolver applies multiple policy scopes for group-1 to user-1.
    """
    spawner = kubespawner.KubeSpawner(
        _mock=True, user=MockUser(name="user-1", groups=[MockGroup(name="group-1")])
    )
    c = Config()
    c.UsageQuotaManager.policy = [
        {
            "resource": "memory",
            "limit": {
                "value": 5000,
                "unit": "GiB-hours",
            },
            "window": 30,
            "scope": {"group": ["group-1"]},
        },
        {
            "resource": "memory",
            "limit": {
                "value": 700,
                "unit": "GiB-hours",
            },
            "window": 7,
            "scope": {"group": ["group-1"]},
        },
    ]

    quota_manager = UsageQuotaManager(config=c)
    merged = quota_manager.resolve_policy(spawner)
    assert merged == quota_manager.policy


async def test_resolve_policy_empty():
    """
    Test policy resolver yields 'empty' backup strategy.
    """
    c = Config()
    c.UsageQuotaManager.scope_backup_strategy = {
        "empty": {
            "resource": "memory",
            "limit": {"value": 500, "unit": "GiB-hours"},
            "window": 7,
        },
        "intersection": "min",
    }
    quota_manager = UsageQuotaManager(config=c)
    policy_empty = quota_manager.resolve_empty()
    assert policy_empty == [quota_manager.scope_backup_strategy["empty"]]


@pytest.mark.parametrize("operator", ["min", "max", "sum"])
async def test_resolve_policy_intersection(operator):
    """
    Test policy resolver applies min/max/sum operator to policy scopes for user-3 who is a member of multiple groups, (group-0 and group-1).
    """
    spawner = kubespawner.KubeSpawner(
        _mock=True,
        user=MockUser(
            name="user-1", groups=[MockGroup(name="group-0"), MockGroup(name="group-1")]
        ),
    )
    c = Config()
    c.UsageQuotaManager.scope_backup_strategy = {
        "empty": {
            "resource": "memory",
            "limit": {"value": 500, "unit": "GiB-hours"},
            "window": 7,
        },
        "intersection": operator,
    }
    c.UsageQuotaManager.policy = [
        {
            "resource": "memory",
            "limit": {
                "value": 5000,
                "unit": "GiB-hours",
            },
            "window": 30,
            "scope": {"group": ["group-0"]},
        },
        {
            "resource": "memory",
            "limit": {
                "value": 700,
                "unit": "GiB-hours",
            },
            "window": 30,
            "scope": {"group": ["group-1"]},
        },
    ]
    quota_manager = UsageQuotaManager(config=c)
    merged = quota_manager.resolve_policy(spawner)
    logger.debug(f"{merged=}")
    logger.debug(f"{operator=}")
    if operator == "min":
        assert merged[0]["limit"]["value"] == min(
            [p["limit"]["value"] for p in quota_manager.policy]
        )
    elif operator == "max":
        assert merged[0]["limit"]["value"] == max(
            [p["limit"]["value"] for p in quota_manager.policy]
        )
    elif operator == "sum":
        assert merged[0]["limit"]["value"] == sum(
            [p["limit"]["value"] for p in quota_manager.policy]
        )


async def test_enforce_single(mocker):
    """
    Test enforcing a single policy scope for group-0 to user-0.
    """
    spawner = kubespawner.KubeSpawner(
        _mock=True, user=MockUser(name="user-0", groups=[MockGroup(name="group-0")])
    )
    c = Config()
    c.UsageQuotaManager.scope_backup_strategy = {
        "empty": {
            "resource": "memory",
            "limit": {"value": 500, "unit": "GiB-hours"},
            "window": 7,
        },
        "intersection": "min",
    }
    c.UsageQuotaManager.policy = [
        {
            "resource": "memory",
            "limit": {
                "value": 5000,
                "unit": "GiB-hours",
            },
            "window": 30,
            "scope": {"group": ["group-0"]},
        },
    ]
    c.UsageQuotaManager.prometheus_usage_metrics = {
        "memory": "kube_pod_container_resource_requests{resource='memory'}",
    }
    # Under quota limit
    mock_usage = mocker.AsyncMock(return_value=[1773089003.938, "4999"])
    mocker.patch("jupyterhub_usage_quotas.manager.UsageQuotaManager.get_usage")
    quota_manager = UsageQuotaManager(config=c)
    output = await quota_manager.enforce(spawner)
    assert output["allow_server_launch"] == True
    # Over quota limit
    mock_usage = mocker.AsyncMock(return_value=[1773089003.938, "5001"])
    mocker.patch(
        "jupyterhub_usage_quotas.manager.UsageQuotaManager.get_usage", mock_usage
    )
    quota_manager = UsageQuotaManager(config=c)
    output = await quota_manager.enforce(spawner)
    assert output["allow_server_launch"] == False


async def test_enforce_multiple(mocker):
    """
    Test enforcing multiple policy scopes for group-1 to user-1.
    """
    spawner = kubespawner.KubeSpawner(
        _mock=True, user=MockUser(name="user-1", groups=[MockGroup(name="group-1")])
    )
    c = Config()
    c.UsageQuotaManager.policy = [
        {
            "resource": "memory",
            "limit": {
                "value": 5000,
                "unit": "GiB-hours",
            },
            "window": 30,
            "scope": {"group": ["group-1"]},
        },
        {
            "resource": "memory",
            "limit": {
                "value": 700,
                "unit": "GiB-hours",
            },
            "window": 7,
            "scope": {"group": ["group-1"]},
        },
    ]
    c.UsageQuotaManager.prometheus_usage_metrics = {
        "memory": "kube_pod_container_resource_requests{resource='memory'}",
    }
    # Under quota limit
    mock_usage = [[1773089003.938, "4999"], [1773089003.938, "699"]]
    mocker.patch(
        "jupyterhub_usage_quotas.manager.UsageQuotaManager.get_usage",
        side_effect=mock_usage,
    )
    quota_manager = UsageQuotaManager(config=c)
    output = await quota_manager.enforce(spawner)
    assert output["allow_server_launch"] == True
    # Over quota limit – 7 day window
    mock_usage = [[1773089003.938, "4999"], [1773089003.938, "701"]]
    mocker.patch(
        "jupyterhub_usage_quotas.manager.UsageQuotaManager.get_usage",
        side_effect=mock_usage,
    )
    quota_manager = UsageQuotaManager(config=c)
    output = await quota_manager.enforce(spawner)
    assert output["allow_server_launch"] == False
    # Over quota limit – 30 day window
    mock_usage = [[1773089003.938, "5001"], [1773089003.938, "699"]]
    mocker.patch(
        "jupyterhub_usage_quotas.manager.UsageQuotaManager.get_usage",
        side_effect=mock_usage,
    )
    quota_manager = UsageQuotaManager(config=c)
    output = await quota_manager.enforce(spawner)
    assert output["allow_server_launch"] == False
    # Over quota limit – both 7 and 30 day window
    mock_usage = [[1773089003.938, "5001"], [1773089003.938, "701"]]
    mocker.patch(
        "jupyterhub_usage_quotas.manager.UsageQuotaManager.get_usage",
        side_effect=mock_usage,
    )
    quota_manager = UsageQuotaManager(config=c)
    output = await quota_manager.enforce(spawner)
    assert output["allow_server_launch"] == False


async def test_enforce_empty(mocker):
    """
    Test enforcing empty policy scope for user-2 who is a member of no groups.
    """
    spawner = kubespawner.KubeSpawner(
        _mock=True, user=MockUser(name="user-2", groups=[])
    )
    c = Config()
    c.UsageQuotaManager.scope_backup_strategy = {
        "empty": {
            "resource": "memory",
            "limit": {"value": 500, "unit": "GiB-hours"},
            "window": 7,
        },
        "intersection": "min",
    }
    c.UsageQuotaManager.prometheus_usage_metrics = {
        "memory": "kube_pod_container_resource_requests{resource='memory'}",
    }
    # Under quota limit
    mock_usage = mocker.AsyncMock(return_value=[1773089003.938, "499"])
    mocker.patch(
        "jupyterhub_usage_quotas.manager.UsageQuotaManager.get_usage", mock_usage
    )
    quota_manager = UsageQuotaManager(config=c)
    output = await quota_manager.enforce(spawner)
    assert output["allow_server_launch"] == True
    # Over quota limit
    mock_usage = mocker.AsyncMock(return_value=[1773089003.938, "501"])
    mocker.patch(
        "jupyterhub_usage_quotas.manager.UsageQuotaManager.get_usage", mock_usage
    )
    quota_manager = UsageQuotaManager(config=c)
    output = await quota_manager.enforce(spawner)
    assert output["allow_server_launch"] == False


@pytest.mark.parametrize(
    "operator, under, over",
    [
        pytest.param("min", "699", "701"),
        pytest.param("max", "4999", "5001"),
        pytest.param("sum", "5699", "5701"),
    ],
)
async def test_enforce_intersection(mocker, operator, under, over):
    """
    Test enforcing min/max/sum operator to policy scopes for user-3 who is a member of multiple groups, (group-0 and group-1).
    """
    spawner = kubespawner.KubeSpawner(
        _mock=True,
        user=MockUser(
            name="user-1", groups=[MockGroup(name="group-0"), MockGroup(name="group-1")]
        ),
    )
    c = Config()
    c.UsageQuotaManager.scope_backup_strategy = {
        "empty": {
            "resource": "memory",
            "limit": {"value": 500, "unit": "GiB-hours"},
            "window": 7,
        },
        "intersection": operator,
    }
    c.UsageQuotaManager.policy = [
        {
            "resource": "memory",
            "limit": {
                "value": 5000,
                "unit": "GiB-hours",
            },
            "window": 30,
            "scope": {"group": ["group-0"]},
        },
        {
            "resource": "memory",
            "limit": {
                "value": 700,
                "unit": "GiB-hours",
            },
            "window": 30,
            "scope": {"group": ["group-1"]},
        },
    ]
    c.UsageQuotaManager.prometheus_usage_metrics = {
        "memory": "kube_pod_container_resource_requests{resource='memory'}",
    }
    # Under quota limit
    mock_usage = mocker.AsyncMock(return_value=[1773089003.938, under])
    mocker.patch(
        "jupyterhub_usage_quotas.manager.UsageQuotaManager.get_usage", mock_usage
    )
    quota_manager = UsageQuotaManager(config=c)
    output = await quota_manager.enforce(spawner)
    assert output["allow_server_launch"] == True
    # Over quota limit
    mock_usage = mocker.AsyncMock(return_value=[1773089003.938, over])
    mocker.patch(
        "jupyterhub_usage_quotas.manager.UsageQuotaManager.get_usage", mock_usage
    )
    quota_manager = UsageQuotaManager(config=c)
    output = await quota_manager.enforce(spawner)
    assert output["allow_server_launch"] == False
