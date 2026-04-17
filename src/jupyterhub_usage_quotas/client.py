import logging

import aiohttp
from yarl import URL

logger = logging.getLogger(__name__)


class Client:
    def __init__(self, token: str | None = None):
        self.session: aiohttp.ClientSession | None = None
        self.token = token

    async def _get_session(
        self, auth: aiohttp.BasicAuth | None = None
    ) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            headers = {}
            if self.token:
                headers["Authorization"] = f"token {self.token}"
            self.session = aiohttp.ClientSession(headers=headers, auth=auth)
        return self.session

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


class PrometheusClient(Client):
    def __init__(
        self, prometheus_url: str, prometheus_auth: dict | None = None, **kwargs
    ):
        super().__init__(**kwargs)
        if prometheus_auth:
            self.auth = aiohttp.BasicAuth(
                prometheus_auth["username"], prometheus_auth["password"]
            )
        self.prometheus_url = URL(prometheus_url)
        self.query_url = self.prometheus_url.joinpath("api/v1/query")

    async def query(self, promql: str) -> dict:
        session = await self._get_session(auth=self.auth)
        params = {
            "query": promql,
        }
        try:
            async with session.get(self.query_url, params=params) as response:
                response.raise_for_status()
                data = await response.json()
                return data
        except aiohttp.ClientError as e:
            logger.error(f"Error querying Prometheus: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise
