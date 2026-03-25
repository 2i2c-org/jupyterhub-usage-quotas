import datetime
import itertools
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
        self.convert_resource = {"GiB-hours": 2**30}
        self.convert_seconds = {"GiB-hours": 60**2}
        self.prometheus_client = PrometheusClient(self.prometheus_url)

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
            p for p in self.policy if set(user_groups) & set(p["scope"]["group"])
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
        promql = f"{promql}[{str(policy['window']) + 'd'}]"
        self.log.debug(f"{promql=}")
        response = await self.prometheus_client.query(promql)
        self.log.debug(f"{response=}")
        if not response["data"]["result"]:
            # handle case when no data is returned
            unix_timestamp = (
                datetime.datetime.utcnow() - datetime.datetime(1970, 1, 1)
            ).total_seconds()
            data = [[unix_timestamp, "0"]]
        else:
            # flatten results into a list
            n_result = len(response["data"]["result"])
            data = [response["data"]["result"][i]["values"] for i in range(n_result)]
            data = [d for ds in data for d in ds]
        # Unit conversion
        unit = policy["limit"]["unit"]
        data = [
            [
                d[0],
                float(d[1])
                * self.prometheus_scrape_interval
                / self.convert_seconds[unit]
                / self.convert_resource[unit],
            ]
            for d in data
        ]
        # Sort by time
        data.sort(key=lambda d: d[0])
        return data

    def get_retry_time(self, policy: dict, data: list) -> str:
        """
        Calculate when a user can retry launching their server after exceeding their quota limit.
        """
        x, y = zip(*data)
        cumulative_sum = list(itertools.accumulate(y))
        # Calculate difference between policy limit and current usage
        delta_resource = cumulative_sum[-1] - policy["limit"]["value"]
        self.log.debug(f"{delta_resource=}")
        # Find timestamp when usage falls below delta_resource
        index_retry = min(
            i for i, v in enumerate(cumulative_sum) if v >= delta_resource
        )
        # Calculate retry_time = timestamp + rolling window
        retry_time = datetime.datetime.fromtimestamp(
            x[index_retry], tz=datetime.UTC
        ) + datetime.timedelta(days=policy["window"])
        return retry_time.strftime("%Y-%m-%dT%H:%M:%SZ")

    def get_output(self, policy: dict, data: list) -> dict:
        """
        Formats the output returned by the quota system.
        """
        output: dict = {}
        self.log.debug(f"{data=}")
        value = [sum(x) for x in zip(*data)][1]
        limit = policy["limit"]["value"]
        if value < limit:
            output["allow_server_launch"] = True
        else:
            output["allow_server_launch"] = False
            output["error"] = {
                "code": "quota-exceeded",
                "message": f"Current {policy['resource']} usage = {value:.2f} {policy['limit']['unit']} is over the quota limit of {limit} {policy['limit']['unit']} over the last {policy['window']} days.",
                "retry_time": self.get_retry_time(policy, data),
            }
        policy.update({"used": value})
        output["quota"] = policy
        output["timestamp"] = datetime.datetime.now(datetime.UTC).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        return output

    async def enforce(self, spawner: KubeSpawner) -> dict:
        """
        Enforce quota system by resolving the policy applied to the user and comparing their usage to the quota limit.
        """
        policy = self.resolve_policy(spawner)
        self.log.info(f"Quota policy applied: {policy}")

        for p in policy:
            usage = await self.get_usage(spawner, p)
            output = self.get_output(p, usage)
            self.log.info(f"{output=}")
            if output["allow_server_launch"] is False:
                self.log.warning(f"{output['error']['code']}: {spawner.user.name}")
                break
        return output


class SpawnException(web.HTTPError):
    """Custom exception that sets attributes for error page template."""

    def __init__(
        self,
        status_code: int,
        log_message: Optional[str] = None,
        html_message: Optional[str] = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(status_code, log_message, *args, **kwargs)
        self.jupyterhub_html_message = html_message
