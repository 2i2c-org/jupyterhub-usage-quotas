import logging

import aiohttp
from yarl import URL

logger = logging.getLogger(__name__)

from prometheus_client import REGISTRY, Counter

PROMETHEUS_ERROR_TOTAL = Counter(
    "jupyterhub_usage_quotas_prometheus_error_total",
    "Number of Prometheus errors from the usage quota system",
    registry=REGISTRY,
)

HUB_API_ERROR_TOTAL = Counter(
    "jupyterhub_usage_quotas_hub_api_error_total",
    "Number of Hub REST API errors from the usage quota system",
    registry=REGISTRY,
)


class Client:
    def __init__(self, headers: dict | None = None, token: str | None = None):
        self.session: aiohttp.ClientSession | None = None
        self.headers = headers
        self.token = token

    def _get_session(
        self, auth: aiohttp.BasicAuth | None = None
    ) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            headers = {}
            if self.token:
                headers["Authorization"] = f"token {self.token}"
            if self.headers:
                headers.update(self.headers.items())
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
        self.auth = (
            aiohttp.BasicAuth(prometheus_auth["username"], prometheus_auth["password"])
            if prometheus_auth
            else None
        )
        self.prometheus_url = URL(prometheus_url)
        self.query_url = self.prometheus_url.joinpath("api/v1/query")

    async def query(self, promql: str) -> dict:
        session = self._get_session(auth=self.auth)
        params = {
            "query": promql,
        }
        try:
            async with session.get(self.query_url, params=params) as response:
                response.raise_for_status()
                data = await response.json()
                return data
        except aiohttp.ClientError as e:
            PROMETHEUS_ERROR_TOTAL.inc()
            logger.error(f"Error querying Prometheus: {e}")
            raise
        except Exception as e:
            PROMETHEUS_ERROR_TOTAL.inc()
            logger.error(f"Unexpected error querying Prometheus: {e}")
            raise


class HubApiClient(Client):
    def __init__(
        self,
        hub_url: str,
        headers: dict | None = None,
        api_token: str | None = None,
        **kwargs,
    ):
        super().__init__(headers=headers, token=api_token, **kwargs)
        self.hub_url = URL(hub_url)

    async def query(self, path: str, query: str | None = None):
        query_url = self.hub_url.with_path(path).with_query(query)
        session = self._get_session()
        try:
            async with session.get(query_url) as response:
                response.raise_for_status()
                data = await response.json()
                return data
        except aiohttp.ClientError as e:
            HUB_API_ERROR_TOTAL.inc()
            logger.error(f"Error querying Hub REST API: {e}")
            raise
        except Exception as e:
            HUB_API_ERROR_TOTAL.inc()
            logger.error(f"Unexpected error querying Hub REST API: {e}")
            raise
