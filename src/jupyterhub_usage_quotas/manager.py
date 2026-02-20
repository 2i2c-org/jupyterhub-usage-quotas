import re

from jupyterhub_usage_quotas.client import PrometheusClient
from jupyterhub_usage_quotas.config import UsageQuotaConfig


class UsageQuotaManager(UsageQuotaConfig):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.prometheus_client = PrometheusClient(self.prometheus_url)

    async def enforce(self, user):
        usage_metric = self.prometheus_usage_metrics["memory"]
        pattern = r"(\{.*?)(\})"
        repl = rf"\1, pod='jupyter-{user}'\2"
        promql = re.sub(pattern, repl, usage_metric)
        data = await self.prometheus_client.query(promql)
        print(f"{data=}")

        # TODO: apply quota logic

        return True
