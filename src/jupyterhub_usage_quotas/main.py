import re

import aiohttp
from yarl import URL

from jupyterhub_usage_quotas.config import UsageQuotaConfig


class PrometheusClient:
    def __init__(self, prometheus_url: str):
        self.prometheus_url = URL(prometheus_url)
        self.session = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    async def query(self, promql: str) -> dict:
        session = await self._get_session()
        api_url = self.prometheus_url.with_path("api/v1/query")
        params = {"query": promql}
        try:
            async with session.get(api_url, params=params) as response:
                print(f"{api_url=}")
                print(f"{params}")
                response.raise_for_status()
                data = await response.json()
                return data
        except aiohttp.ClientError as e:
            print(f"Error querying prometheus: {e}")


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

        return data
