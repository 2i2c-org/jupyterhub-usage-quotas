import re
from typing import Any, Optional

from tornado import web

from jupyterhub_usage_quotas.client import HubAPIClient, PrometheusClient
from jupyterhub_usage_quotas.config import UsageQuotaConfig


class UsageQuotaManager(UsageQuotaConfig):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        hub_ip = self.config["JupyterHub"]["ip"]
        hub_port = self.config["JupyterHub"]["port"]
        self.hub_api_client = HubAPIClient(hub_url=f"http://{hub_ip}:{hub_port}")
        self.prometheus_client = PrometheusClient(self.prometheus_url)

    async def resolve_policy(self, user):
        """
        Resolve which quota policy applies to the user.
        """
        data_user = await self.hub_api_client.query("users")
        return data_user

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
