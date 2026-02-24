import re
from typing import Any, Optional

from tornado import web

from jupyterhub_usage_quotas.client import HubAPIClient, PrometheusClient
from jupyterhub_usage_quotas.config import UsageQuotaConfig, policy_schema_backup


class UsageQuotaManager(UsageQuotaConfig):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        hub_ip = self.config.get("JupyterHub", {}).get("ip", "127.0.0.1")
        hub_port = self.config.get("JupyterHub", {}).get("port", 8000)
        self.hub_api_client = HubAPIClient(hub_url=f"http://{hub_ip}:{hub_port}")
        self.prometheus_client = PrometheusClient(self.prometheus_url)

    def resolve_intersection(self, policies: list(dict), operator: str) -> dict:
        #  TODO: add logic to match other required keys, e.g. units
        resource_keys = policy_schema_backup["properties"]["resource"]["enum"]
        policy_intersection = {}
        for resource in resource_keys:
            limit_values = []
            for p in policies:
                if p["resource"] == resource:
                    limit_values.append(p["limit"]["value"])
            if limit_values:
                if operator == "min":
                    limit = min(limit_values)
                elif operator == "max":
                    limit = max(limit_values)
                elif operator == "sum":
                    limit = sum(limit_values)
                else:
                    print("Operator not recognized.")
                p["limit"]["value"] = limit
                policy_intersection.update(p)
        return policy_intersection

    async def resolve_policy(self, user):
        """
        Resolve which quota policy applies to the user.
        """
        data_user = await self.hub_api_client.query("users")
        entry_user = next(filter(lambda x: x["name"] == user, data_user), None)
        groups_user = entry_user["groups"]
        policies = [
            p for p in self.policy if set(groups_user) <= set(p["scope"]["group"])
        ]
        test = self.resolve_intersection(
            policies, self.scope_backup_strategy["intersection"]
        )
        print(f"{test=}")
        return groups_user

    async def enforce(self, user):
        usage_metric = self.prometheus_usage_metrics["memory"]
        pattern = r"(\{.*?)(\})"
        repl = rf"\1, pod='jupyter-{user}'\2"
        promql = re.sub(pattern, repl, usage_metric)
        data_prometheus = await self.prometheus_client.query(promql)
        print(f"{data_prometheus=}")

        # TODO: apply quota logic
        data_user = await self.resolve_policy(user)
        print(f"{data_user}")

        return True


class SpawnException(web.HTTPError):
    """Custom exception that sets jupyterhub_message attribute"""

    def __init__(
        self,
        status_code: int = 500,
        log_message: Optional[str] = None,
        *args: Any,
        **kwargs: Any,
    ):
        super().__init__(status_code, log_message, *args, **kwargs)
        self.jupyterhub_message = log_message
