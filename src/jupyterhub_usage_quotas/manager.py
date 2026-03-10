import datetime
import re
from collections import defaultdict
from typing import Any, Optional

from kubespawner import KubeSpawner
from kubespawner.slugs import safe_slug
from tornado import web

from jupyterhub_usage_quotas.client import PrometheusClient
from jupyterhub_usage_quotas.config import UsageQuotaConfig


class UsageQuotaManager(UsageQuotaConfig):

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.convert = {"GiB-hours": 2**30}  # bytes to XiB
        self.sample_rate = 60 * 60 / self.prometheus_scrape_interval  # samples per hour

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

    def resolve_policy(self, spawner: KubeSpawner) -> list:
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

    async def get_usage(self, spawner: KubeSpawner, policy: dict) -> list:
        """
        Get resource usage by user over a rolling time window.
        """
        usage_metric = self.prometheus_usage_metrics[policy["resource"]]
        pattern = r"(\{.*?)(\})"
        repl = rf"\1, namespace='{spawner.namespace}', node!='', pod='jupyter-{safe_slug(spawner.user.name)}'\2"
        promql = re.sub(pattern, repl, usage_metric)
        promql = f"sum(sum_over_time({promql}[{str(policy['window']) + 'd'}]) / {self.sample_rate} / {self.convert[policy['limit']['unit']]}) by (namespace, pod)"
        self.log.debug(f"{promql=}")
        prometheus_client = PrometheusClient(prometheus_url=self.prometheus_url)
        response = await prometheus_client.query(promql)
        self.log.debug(f"{response=}")
        usage = response["data"]["result"][0]["value"]
        return usage

    def get_output(self, policy: dict, usage: list) -> dict:
        output: dict = {}
        value = float(usage[1])
        limit = policy["limit"]["value"]
        if value < limit:
            output["allow_server_launch"] = True
        else:
            output["allow_server_launch"] = False
            output["error"] = {
                "code": "quota-exceeded",
                "message": f"Current {policy['resource']} usage = {value} {policy['limit']['unit']} is over the quota limit of {limit} {policy['limit']['unit']} over the last {policy['window']} days.",
                "retry_time": "TBC",  # TODO: calculate retry_time
            }
        policy.update({"used": value})
        output["quota"] = policy
        output["timestamp"] = datetime.datetime.fromtimestamp(
            usage[0], datetime.timezone.utc
        ).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )  # convert from unix timestamp to string formatted with datetime
        return output

    async def enforce(self, spawner: KubeSpawner) -> dict:
        policy = self.resolve_policy(spawner)
        self.log.info(f"Quota policy applied: {policy}")

        for p in policy:
            usage = await self.get_usage(spawner, p)
            self.log.info(f"{usage=}")
            output = self.get_output(p, usage)
            self.log.info(f"{output=}")
            if output["allow_server_launch"] is False:
                self.log.warning(f"{output['error']['code']}: {spawner.user.name}")
                break
        return output


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
