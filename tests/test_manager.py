import logging
from unittest.mock import MagicMock

logger = logging.getLogger(__name__)

from traitlets.config import Config

from jupyterhub_usage_quotas.manager import UsageQuotaManager


async def test_resolve_policy_single(mock_hub_client):
    """
    Test policy resolver applies a single policy scope for group-0 to user-0.
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
    quota_manager.hub_api_client = mock_hub_client
    merged = await quota_manager.resolve_policy("user-0")
    assert merged == quota_manager.policy


async def test_resolve_policy_empty(mock_hub_client):
    """
    Test policy resolver yields 'empty' backup strategy for user-2 who is a member of no groups.
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
    quota_manager.hub_api_client = mock_hub_client
    quota_manager.resolve_empty = MagicMock(
        return_value=c.UsageQuotaManager.scope_backup_strategy["empty"]
    )
    merged = await quota_manager.resolve_policy("user-2")
    assert merged == quota_manager.scope_backup_strategy["empty"]
