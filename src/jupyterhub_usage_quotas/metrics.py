from prometheus_client import REGISTRY, Counter
from tornado.ioloop import PeriodicCallback

from jupyterhub_usage_quotas.config import UsageViewerConfig

c = Counter(
    "my_counter_total", "Example counter", namespace="jupyterhub", registry=REGISTRY
)


class MetricsExporter(UsageViewerConfig):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # api_url = os.environ.get("JUPYTERHUB_API_URL")
        # api_token = os.environ.get("JUPYTERHUB_API_TOKEN")
        # self.client = HubApiClient(api_url=api_url, token=api_token)

    async def get_users_and_groups(self) -> list:
        response = await self.client.query(path="users")
        filtered = [
            {"user_name": r.get("name"), "user_group": r.get("groups")}
            for r in response
        ]
        return filtered

    def update_metrics(self):
        """
        Update usage and quota limits Prometheus metrics.
        """
        # users_and_groups = await self.get_users_and_groups()
        # print(users_and_groups)
        print("incrementing counter")
        c.inc()

    def start(self):
        pc = PeriodicCallback(self.update_metrics, 5e3)
        pc.start()
