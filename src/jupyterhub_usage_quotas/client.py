import aiohttp
from yarl import URL


class Client:
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
    def __init__(self, prometheus_url: str, **kwargs):
        super().__init__(**kwargs)
        self.prometheus_url = URL(prometheus_url)
        self.query_url = self.prometheus_url.joinpath("api/v1/query")

    async def query(self, promql: str) -> dict:
        session = await self._get_session()
        params = {
            "query": promql,
        }
        try:
            async with session.get(self.query_url, params=params) as response:
                response.raise_for_status()
                data = await response.json()
                return data
        except Exception as e:
            print(f"Error querying prometheus: {e}")
            raise
