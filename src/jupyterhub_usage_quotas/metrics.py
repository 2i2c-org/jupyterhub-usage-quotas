import os

from jupyterhub_usage_quotas.client import HubApiClient
from jupyterhub_usage_quotas.config import UsageQuotaConfig


class MetricsExporter(UsageQuotaConfig):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        api_url = os.environ.get("JUPYTERHUB_API_URL")
        api_token = os.environ.get("JUPYTERHUB_API_TOKEN")
        self.client = HubApiClient(api_url=api_url, token=api_token)

    async def export_metrics(self):
        """
        Export usage and quota limits as Prometheus metrics.
        """
        response = await self.client.query(path="users")
        self.log.info(response)
