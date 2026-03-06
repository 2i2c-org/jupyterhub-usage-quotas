from pathlib import Path

import aiohttp
from yarl import URL

from jupyterhub_usage_quotas.config import UsageQuotaConfig


class Client(UsageQuotaConfig):
    def __init__(self, token: str | None = None):
        self.session: aiohttp.ClientSession | None = None
        self.token = token

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            headers = {}
            if self.token:
                headers["Authorization"] = f"token {self.token}"
            self.session = aiohttp.ClientSession(headers=headers)
        return self.session

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()


class PrometheusClient(Client):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        prometheus_url = URL(self.config.get("prometheus_url"))
        self.query_url = prometheus_url.joinpath("api/v1/query")

    async def query(self, promql: str) -> dict:
        session = await self._get_session()
        params = {"query": promql}
        try:
            async with session.get(self.query_url, params=params) as response:
                response.raise_for_status()
                data = await response.json()
                return data
        except Exception as e:
            print(f"Error querying prometheus: {e}")
            raise


class HubAPIClient(Client):
    def __init__(self, hub_api_token: str | None = None, **kwargs):
        super().__init__(**kwargs)
        hub_ip = self.config.get("JupyterHub", {}).get("ip", "127.0.0.1")
        hub_port = self.config.get("JupyterHub", {}).get("port", 8000)
        hub_url = f"http://{hub_ip}:{hub_port}"
        self.api_url = URL(hub_url).joinpath("hub/api")
        if hub_api_token is None:
            self.token = self._get_token()

    def _get_token(self):
        # for local dev with token in project root set in jupyterhub_config.py
        here = Path(__file__).parent.parent.parent
        token_file = here.joinpath("api_token")
        with open(token_file, "r") as f:
            print("Found JupyterHub API token in local file.")
            return f.read()

    async def query(self, subpath: str = "") -> dict:
        session = await self._get_session()
        endpoint = self.api_url.joinpath(subpath)
        try:
            async with session.get(endpoint) as response:
                response.raise_for_status()
                data = await response.json()
                return data
        except Exception as e:
            print(f"Error querying JupyterHub API: {e}")
            raise
