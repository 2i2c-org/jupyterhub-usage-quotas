import os

from jupyterhub_usage_quotas.client import HubApiClient
from jupyterhub_usage_quotas.config import UsageViewerConfig


class MetricsExporter(UsageViewerConfig):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        api_url = os.environ.get("JUPYTERHUB_API_URL")
        api_token = os.environ.get("JUPYTERHUB_API_TOKEN")
        self.client = HubApiClient(api_url=api_url, token=api_token)

    async def get_users_and_groups(self) -> list:
        response = await self.client.query(path="users")
        filtered = [
            {"user_name": r.get("name"), "user_group": r.get("groups")}
            for r in response
        ]
        return filtered

    async def export_metrics(self):
        """
        Export usage and quota limits as Prometheus metrics.
        """
        users_and_groups = await self.get_users_and_groups()
        print(users_and_groups)
