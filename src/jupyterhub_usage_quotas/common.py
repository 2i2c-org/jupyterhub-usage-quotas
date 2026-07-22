import logging
import re

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


class Resource(object):
    """
    Allow easily specifying resources and convert units with suffixes.

    Suffixes allowed are:
      - K -> Kilo
      - M -> Mega
      - G -> Giga
      - T -> Tera
    """

    MEMORY_SUFFIXES = {
        "K": 1024,
        "M": 1024**2,
        "G": 1024**3,
        "T": 1024**4,
    }
    CPU_SUFFIXES = {
        "K": 1e3,
        "M": 1e4,
        "G": 1e5,
        "T": 1e6,
    }

    def __init__(self, name, value):
        self.name = name
        self.value = value
        self.get_pure_value()

    def get_pure_value(self) -> int | None:
        """
        Validate that the passed in value is a valid resource specification

        It could either be a pure int or string. If there is a string suffix, the convert to pure value.
        """
        if isinstance(self.value, int | float):
            self.pure_value = int(self.value)
            self.unit = ""
            return None
        elif isinstance(self.value, str):
            pattern = re.compile(r"^\d+[KMGT]$")
            if not pattern.match(self.value):
                raise ValueError(
                    f"{self.value} is not a valid resource specification. Must be an int or a string with suffix K, M, G, T"
                )

        try:
            num = float(self.value[:-1])
        except ValueError:
            raise ValueError(
                f"{self.value} is not a valid memory specification. Must be an int or a string with suffix K, M, G, T"
            )
        self.unit = self.value[-1]
        if self.unit not in self.MEMORY_SUFFIXES or self.unit not in self.CPU_SUFFIXES:
            raise ValueError(
                f"{self.value} is not a valid memory specification. Must be an int or a string with suffix K, M, G, T"
            )
        if self.name == "memory":
            self.pure_value = int(float(num) * self.MEMORY_SUFFIXES[self.unit])
        elif self.name == "cpu":
            self.pure_value = int(float(num) * self.CPU_SUFFIXES[self.unit])
        return None

    @classmethod
    def get_value(cls, name: str, value: float, unit: str) -> float:
        """
        Helper function to convert pure values to other units.
        """
        if unit:
            if name == "memory":
                return value / cls.MEMORY_SUFFIXES[unit]
            elif name == "cpu":
                return value / cls.CPU_SUFFIXES[unit]
            else:
                raise ValueError(f"Resource {name} not recognised.")
        else:
            return value

    @staticmethod
    def get_readable_unit(name: str, unit: str) -> str:
        """
        Get full human-readable unit string.
        """
        if name == "memory":
            return unit + "iB-hours" if unit else "byte-hours"
        elif name == "cpu":
            return "CPU-hours"
        else:
            raise ValueError(f"Resource {name} not recognised.")

    @staticmethod
    def get_limit_without_unit(value: str | int) -> int:
        """
        Get the numeric value of a limit, e.g. 20G -> 20.
        """
        if type(value) is str:
            pattern = r"-?\d+"
            match = re.findall(pattern, value)
            return int(match[0])
        else:
            return int(value)
