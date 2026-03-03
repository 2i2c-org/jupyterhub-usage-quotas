import re
from collections import defaultdict
from copy import deepcopy
from typing import Any, Optional

from tornado import web

from jupyterhub_usage_quotas.client import HubAPIClient, PrometheusClient
from jupyterhub_usage_quotas.config import UsageQuotaConfig


class UsageQuotaManager(UsageQuotaConfig):

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        hub_ip = self.config.get("JupyterHub", {}).get("ip", "127.0.0.1")
        hub_port = self.config.get("JupyterHub", {}).get("port", 8000)
        self.hub_api_client = HubAPIClient(hub_url=f"http://{hub_ip}:{hub_port}")
        self.prometheus_client = PrometheusClient(self.prometheus_url)

    def resolve_empty(self) -> dict:
        """
        Resolve quota policy for users with no group memberships.
        """
        policy_empty: dict
        if isinstance(self.scope_backup_strategy["empty"], dict):
            policy_empty = self.scope_backup_strategy["empty"]
        return policy_empty

    def resolve_intersection(self, policies: list[dict], operator: str) -> dict:
        """
        Resolve quota policy for users with multiple group memberships.

        Apply min/max/sum operators to merge policies sharing the same resource over the same rolling window for the same groups, otherwise return applicable quota policies.

        Example 1: Policy A limits 30 memory hours over the last 30 days to group 1, policy B limits 60 memory hours over the last 30 days to group 1. The policy backup strategy specifies the 'max' operator, therefore the policy of max(30, 60) = 60 memory hours over the last 30 days applies to group 1.

        Example 2:  Policy A limits 30 memory hours over the last 30 days to group 1, policy B limits 7 memory hours over the last 7 days to group 1. Both quota policies are returned (and eventually applied).

        TODO: Add support for aggregating resource units, e.g. GiB and MiB-hours.
        """

        grouped = defaultdict(list)

        for p in policies:
            key = (
                p["resource"],
                p["limit"]["unit"],
                p["window"],
            )
            grouped[key].append(p)

        merged = []

        for (resource, unit, window), group in grouped.items():

            if len(group) == 1:
                merged.append(deepcopy(group[0]))
                continue

            values = [p["limit"]["value"] for p in group]

            if operator == "min":
                combined_value = min(values)
            elif operator == "max":
                combined_value = max(values)
            elif operator == "sum":
                combined_value = sum(values)
            else:
                raise ValueError(
                    f"Operator must be one of: min, max, sum, got {operator}"
                )

            merged_groups = set()
            for p in group:
                merged_groups.update(p["scope"].get("group", []))

            merged.append(
                {
                    "resource": resource,
                    "limit": {
                        "value": combined_value,
                        "unit": unit,
                    },
                    "window": window,
                    "scope": {"group": sorted(merged_groups)},
                }
            )

        return merged

    async def resolve_policy(self, user):
        """
        Resolve which group quota policy applies to the user.
        """
        data_user = await self.hub_api_client.query("users")
        entry_user = next(filter(lambda x: x["name"] == user, data_user), None)
        groups_user = entry_user["groups"]
        self.log.info(f"User {user} is a member of groups: {groups_user}")
        policies = [
            p for p in self.policy if set(groups_user) <= set(p["scope"]["group"])
        ]
        self.log.info(f"{policies=}")
        if len(policies) == 0:
            policy = self.resolve_empty()
        elif len(policies) >= 1:
            policy = self.resolve_intersection(
                policies, self.scope_backup_strategy["intersection"]
            )
        else:
            policy = policies[0]
        return policy

    async def enforce(self, user):
        usage_metric = self.prometheus_usage_metrics["memory"]
        pattern = r"(\{.*?)(\})"
        repl = rf"\1, pod='jupyter-{user}'\2"
        promql = re.sub(pattern, repl, usage_metric)
        data_prometheus = await self.prometheus_client.query(promql)
        self.log.info(f"{data_prometheus=}")

        # TODO: apply quota logic
        policy = await self.resolve_policy(user)
        self.log.info(f"{policy=}")

        return True


class SpawnException(web.HTTPError):
    """Custom exception that sets jupyterhub_message attribute"""

    def __init__(
        self,
        status_code: int = 500,
        log_message: Optional[str] = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(status_code, log_message, *args, **kwargs)
        self.jupyterhub_message = log_message
