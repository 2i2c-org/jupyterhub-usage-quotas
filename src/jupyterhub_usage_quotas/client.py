import aiohttp
from aiohttp import web
from yarl import URL


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
                response.raise_for_status()
                data = await response.json()
                return data
        except aiohttp.ClientError as e:
            raise web.Response(status=500, text=f"Error querying prometheus: {e}")
