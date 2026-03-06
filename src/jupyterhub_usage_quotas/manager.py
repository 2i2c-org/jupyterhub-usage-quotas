import re
from collections import defaultdict
from typing import Any, Optional

from kubespawner.slugs import safe_slug
from tornado import web

from jupyterhub_usage_quotas.client import PrometheusClient
from jupyterhub_usage_quotas.config import UsageQuotaConfig


class UsageQuotaManager(UsageQuotaConfig):

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

    def resolve_empty(self) -> list:
        """
        Resolve quota policy for users with no group memberships.
        """
        policy_empty: list = []
        if isinstance(self.scope_backup_strategy["empty"], dict):
            policy_empty.append(self.scope_backup_strategy["empty"])
        return policy_empty

    def resolve_intersection(self, values: list[dict], operator: str) -> list:
        """
        Resolve quota policy for users with multiple group memberships.

        Apply min/max/sum operators to merge policies sharing the same resource over the same rolling window for the same groups.
        """

        limits = [v["limit"]["value"] for v in values]

        if operator == "min":
            combined_value = min(limits)
        elif operator == "max":
            combined_value = max(limits)
        elif operator == "sum":
            combined_value = sum(limits)
        else:
            raise ValueError(f"Operator must be one of: min, max, sum, got {operator}")

        return combined_value

    def resolve_policy(self, spawner) -> list:
        """
        Resolve and merge group quota policies that apply to the user.

        Example 1 - empty: Backup policy applies to users who are out of scope of policy definitions.

        Example 2 - intersection: Policy A limits 30 memory hours over the last 30 days to group 1, policy B limits 60 memory hours over the last 30 days to group 1. The policy backup strategy specifies the 'max' operator, therefore the policy of max(30, 60) = 60 memory hours over the last 30 days applies to group 1.

        Example 3 - multiple:  Policy A limits 30 memory hours over the last 30 days to group 1, policy B limits 7 memory hours over the last 7 days to group 1. Both quota policies are returned (and eventually applied with no limit stacking).
        """
        user_name = spawner.user.name
        user_groups = [g.name for g in spawner.user.groups]
        self.log.info(
            f"User {user_name} is a member of quota policy scope groups: {user_groups}"
        )
        policies = [
            p for p in self.policy if set(p["scope"]["group"]) <= set(user_groups)
        ]
        self.log.debug(f"{policies=}")

        # Group policies with common keys together, e.g. the same resources and rolling windows.
        grouped = defaultdict(list)
        for p in policies:
            key = (
                p["resource"],
                p["limit"][
                    "unit"
                ],  # TODO: Add support for aggregating different resource units, e.g. GiB and MiB-hours.
                p["window"],
            )
            grouped[key].append(p)

        merged = []
        if len(policies) == 1:
            self.log.debug("Resolve single policy")
            merged.append(next(iter(grouped.values()))[0])
        elif len(policies) == 0:
            self.log.debug("Resolve no policy")
            merged = self.resolve_empty()
        elif len(policies) >= 1:
            self.log.debug("Resolve multiple policies")
            for (resource, unit, window), values in grouped.items():
                combined_value = self.resolve_intersection(
                    values, self.scope_backup_strategy["intersection"]
                )
                merged_groups = set()
                for v in values:
                    merged_groups.update(v["scope"].get("group", []))
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

    async def enforce(self, spawner):
        policy = self.resolve_policy(spawner)
        self.log.info(f"Quota policy applied: {policy}")

        # TODO: apply quota logic
        usage_metric = self.prometheus_usage_metrics["memory"]
        pattern = r"(\{.*?)(\})"
        repl = rf"\1, pod='jupyter-{safe_slug(spawner.user.name)}'\2"
        promql = re.sub(pattern, repl, usage_metric)
        prometheus_client = PrometheusClient(prometheus_url=self.prometheus_url)
        data_prometheus = await prometheus_client.query(promql)
        self.log.info(f"{data_prometheus=}")
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
