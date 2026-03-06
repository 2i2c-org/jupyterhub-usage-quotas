import logging
from unittest.mock import MagicMock, Mock

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
    groups = [MockGroup()]
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
    c.UsageQuotaManager.policy = (
        {
            "resource": "memory",
            "limit": {
                "value": 5000,
                "unit": "GiB-hours",
            },
            "window": 30,
            "scope": {"group": ["group-0"]},
        },
    )

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
    c.UsageQuotaManager.policy = (
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
    )

    quota_manager = UsageQuotaManager(config=c)
    merged = quota_manager.resolve_policy(spawner)
    assert merged == quota_manager.policy


async def test_resolve_policy_empty():
    """
    Test policy resolver yields 'empty' backup strategy for user-2 who is a member of no groups.
    """
    spawner = kubespawner.KubeSpawner(_mock=True, user=MockUser(name="user-2"))
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
    quota_manager.resolve_empty = MagicMock(
        return_value=c.UsageQuotaManager.scope_backup_strategy["empty"]
    )
    merged = quota_manager.resolve_policy(spawner)
    assert merged == quota_manager.scope_backup_strategy["empty"]


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
    c.UsageQuotaManager.policy = (
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
    )
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
