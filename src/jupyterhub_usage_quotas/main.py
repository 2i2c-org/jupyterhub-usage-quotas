import re
from typing import Any

import requests
from yarl import URL

from jupyterhub_usage_quotas.config import UsageQuotaConfig


class PrometheusClient:
    def __init__(self, prometheus_url: str):
        self.prometheus_url = URL(prometheus_url)

    def query(self, promql: str) -> Any:
        api_url = self.prometheus_url.with_path("api/v1/query")
        params = {"query": promql}
        with requests.get(api_url, params=params) as response:
            data = response.json()
            return data


class UsageQuotaManager(UsageQuotaConfig):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.prometheus_client = PrometheusClient(self.prometheus_url)

    def enforce(self, user):
        usage_metric = self.prometheus_usage_metrics["memory"]
        pattern = r"(\{.*?)(\})"
        repl = rf"\1, user='jupyter-{user}'\2"
        promql = re.sub(pattern, repl, usage_metric)
        data = self.prometheus_client.query(promql)
        print(f"{data=}")

        return data
