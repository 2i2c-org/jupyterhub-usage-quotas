from pathlib import Path

import aiohttp
from yarl import URL


class Client:
    def __init__(self, token: str | None = None):
        self.session = None
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
    def __init__(self, prometheus_url: str, **kwargs):
        super().__init__(**kwargs)
        self.prometheus_url = URL(prometheus_url)
        self.query_url = self.prometheus_url.joinpath("api/v1/query")

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
    def __init__(self, hub_url: str, hub_api_token: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self.api_url = URL(hub_url).joinpath("hub/api")
        if hub_api_token is None:
            self.token = self._get_token()
        else:
            self.token = hub_api_token

    def _get_token(self):
        # for local dev with token in project root set in jupyterhub_config.py
        try:
            here = Path(__file__).parent.parent.parent
            token_file = here.joinpath("api_token")
            with open(token_file, "r") as f:
                return f.read()
        except:
            raise ValueError("JupyterHub API token file does not exist.")

    async def query(self, endpoint: str = "") -> dict:
        session = await self._get_session()
        endpoint = self.api_url.joinpath(endpoint)
        try:
            async with session.get(endpoint) as response:
                response.raise_for_status()
                data = await response.json()
                return data
        except Exception as e:
            print(f"Error querying JupyterHub API: {e}")
            raise
