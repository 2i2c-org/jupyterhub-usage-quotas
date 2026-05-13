"""Storage quota client for querying Prometheus storage metrics."""

import asyncio
import logging
import random
import sys
from datetime import UTC, datetime
from typing import Any

from kubespawner.slugs import escape_slug, safe_slug

from jupyterhub_usage_quotas.client import PrometheusClient

logger = logging.getLogger(__name__)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
logger.handlers = [handler]
logger.setLevel(logging.INFO)


class QuotaClient(PrometheusClient):
    """Client for quota operations using Prometheus and Hub API.

    Args:
        prometheus_usage_quota_metrics: Dictionary of Prometheus metrics
        prometheus_url: URL of the Prometheus server
        prometheus_auth: Dictionary of Prometheus username and password
        namespace: Prometheus namespace for filtering metrics
        escape_scheme: Username escaping scheme for directory names
        dev_mode: Whether to enable development mode with mock data
        **kwargs: Additional arguments passed to PrometheusClient
    """

    def __init__(
        self,
        prometheus_usage_quota_metrics: dict,
        prometheus_url: str,
        prometheus_auth: dict | None = None,
        namespace: str = "",
        escape_scheme: dict = {"directory": "legacy"},
        dev_mode: bool = False,
        **kwargs,
    ):
        super().__init__(prometheus_url, prometheus_auth, **kwargs)
        self.namespace = namespace
        self.escape_scheme = escape_scheme
        self.dev_mode = dev_mode
        self.metrics = prometheus_usage_quota_metrics

    @staticmethod
    def find_matching_result(data: dict[str, Any]) -> list | None:
        """Find the [timestamp, value] pair from the first result in a Prometheus response.

        Args:
            data: Prometheus query response data

        Returns:
            The value pair list [timestamp, value] or None if no result found
        """
        if data.get("status") != "success":
            return None
        results = data.get("data", {}).get("result", [])
        if not results:
            return None
        value_pair = results[0].get("value", [])
        return value_pair if len(value_pair) == 2 else None

    @staticmethod
    def parse_value_result(data: dict[str, Any]) -> int | None:
        """Extract numeric value from Prometheus response.

        Args:
            data: Prometheus query response data

        Returns:
            Integer value or None if parsing fails
        """
        pair = QuotaClient.find_matching_result(data)
        if not pair:
            return None
        try:
            return int(float(pair[1]))
        except (ValueError, TypeError):
            print(f"Non-numeric value in Prometheus response: {pair[1]}")
            return None

    @staticmethod
    def parse_timestamp_result(data: dict[str, Any]) -> datetime | None:
        """Extract timestamp from Prometheus response.

        Args:
            data: Prometheus query response data

        Returns:
            Datetime object or None if parsing fails
        """
        pair = QuotaClient.find_matching_result(data)
        return datetime.fromtimestamp(float(pair[0]), tz=UTC) if pair else None

    @staticmethod
    def with_label_replace(metric: str) -> str:
        """Wrap metric with label_replace for escaped username extraction.

        Args:
            metric: PromQL metric expression

        Returns:
            PromQL expression with label_replace wrapper
        """
        return f'label_replace({metric}, "username", "$1", "directory", "(.*)")'

    @staticmethod
    def escape_username(username: str, escape_scheme: dict):
        """
        Escape username to create a safe string for naming directories.

        Args:
            username: Username to escape
            escape_scheme: Kubespawner slug scheme, e.g. 'safe' or 'legacy'

        Returns:
            String of escaped username
        """
        if escape_scheme["directory"] == "safe":
            return safe_slug(username)
        return escape_slug(username)

    def get_mock_data(self, username: str) -> dict[str, Any]:
        """Return mock data for development when namespace is not set.

        Randomly returns 50% usage, 95% usage, or an error state for testing.

        Args:
            username: Username to generate mock data for

        Returns:
            Dictionary with mock usage data or error message
        """
        scenario = random.choice([0.50, 0.95, "error"])

        if scenario == "error":
            return {
                "username": username,
                "error": "Unable to query usage data. Please try again later.",
            }

        # At this point, scenario must be a float (type narrowing to make mypy happy)
        assert isinstance(scenario, float)
        mock_quota_bytes = 10_737_418_240  # 10 GiB
        mock_usage_bytes = int(mock_quota_bytes * scenario)
        usage_gb = mock_usage_bytes / (1024**3)
        quota_gb = mock_quota_bytes / (1024**3)
        percentage = (mock_usage_bytes / mock_quota_bytes) * 100

        return {
            "username": username,
            "usage_bytes": mock_usage_bytes,
            "quota_bytes": mock_quota_bytes,
            "usage_gb": round(usage_gb, 2),
            "quota_gb": round(quota_gb, 2),
            "percentage": round(percentage, 2),
            "last_updated": datetime.now(tz=UTC).isoformat(),
        }

    async def get_user_storage_usage(self, username: str) -> dict[str, Any]:
        """Query Prometheus for user storage usage and quota.

        Args:
            username: Username to query storage for

        Returns:
            Dictionary with usage information or error dict if unavailable
        """
        # Check if we should use mock data (all three conditions must be met)
        use_mock_data = (
            self.dev_mode
            and str(self.prometheus_url) == "http://127.0.0.1:9090"
            and not self.namespace
        )

        if use_mock_data:
            logger.warning(
                "Development mode is enabled with unconfigured Prometheus settings — returning mock data. "
                f"(dev_mode={self.dev_mode}, prometheus_url={str(self.prometheus_url)}, "
                f"namespace={self.namespace or '(empty)'})"
            )
            return self.get_mock_data(username)

        logger.debug(f"Fetching usage data for user: {username}")

        directory = self.escape_username(username, escape_scheme=self.escape_scheme)

        base_quota_metric = f'{self.metrics["home_storage"]["quota"]}{{namespace="{self.namespace}", directory="{directory}"}}'
        base_usage_metric = f'{self.metrics["home_storage"]["usage"]}{{namespace="{self.namespace}", directory="{directory}"}}'

        quota_value_query = self.with_label_replace(base_quota_metric)
        usage_value_query = self.with_label_replace(base_usage_metric)
        usage_timestamp_query = self.with_label_replace(
            f"timestamp({base_usage_metric})"
        )

        try:
            quota_value_data, usage_value_data, usage_timestamp_data = (
                await asyncio.gather(
                    self.query(quota_value_query),
                    self.query(usage_value_query),
                    self.query(usage_timestamp_query),
                )
            )
        except Exception as e:
            logger.error(f"Error fetching usage data for {username}: {e}")
            return {
                "username": username,
                "error": "Unable to query home storage usage. Please try again later.",
            }

        quota_bytes = self.parse_value_result(quota_value_data)
        usage_bytes = self.parse_value_result(usage_value_data)
        last_updated_dt = self.parse_timestamp_result(usage_timestamp_data)

        if quota_bytes is None or usage_bytes is None or last_updated_dt is None:
            return {
                "username": username,
                "error": "No storage data found for your account.",
            }

        usage_gb = usage_bytes / (1024**3)
        quota_gb = quota_bytes / (1024**3)
        percentage = (usage_bytes / quota_bytes) * 100 if quota_bytes > 0 else 0

        return {
            "username": username,
            "usage_bytes": usage_bytes,
            "quota_bytes": quota_bytes,
            "usage_gb": round(usage_gb, 2),
            "quota_gb": round(quota_gb, 2),
            "percentage": round(percentage, 2),
            "last_updated": last_updated_dt.isoformat(),
        }

    async def get_user_compute_usage(self, username: str) -> list[dict[str, Any]]:
        """
        Query Prometheus for user compute usage and quota.

        Args:
            username: Username to query for

        Returns:
            Dictionary with usage information or error dict if unavailable
        """
        results: list = []
        compute_metrics = self.metrics["compute"]
        for key in ["usage", "quota"]:
            metric = compute_metrics[key]
            promql = f"{metric}{{namespace='{self.namespace}', username='{username}'}}"
            try:
                response = await self.query(promql)
                if not response["data"]["result"]:
                    # handle case when no data is returned
                    logger.warning(f"No usage metrics detected for {username}")
                    return [
                        {
                            "username": username,
                            "error": "No usage detected for your account.",
                        }
                    ]
            except Exception as e:
                logger.error(f"Error fetching usage data for {username}: {e}")
                return [
                    {
                        "username": username,
                        "error": "Unable to query compute usage. Please try again later.",
                    }
                ]
            for r in response["data"]["result"]:
                result: dict[str, Any] = {"username": username}
                value = float(r["value"][1])
                result.update({key: round(value, 2)})
                window = int(r["metric"]["window"])
                result.update({"window": window})
                last_updated_dt = datetime.fromtimestamp(r["value"][0], tz=UTC)
                result.update({"last_updated": last_updated_dt.isoformat()})
                results.append(result)
        combined = {}
        for result in results:
            window = result["window"]
            if window not in combined:
                combined[window] = {
                    "window": window,
                    "username": result["username"],
                    "last_updated": result["last_updated"],
                }
            combined[window].update(result)
        output = []
        for item in combined.values():
            usage = item.get("usage", 0)
            quota = item.get("quota", 0)
            item["percentage"] = (usage / quota) * 100 if quota else None
            output.append(item)
        logger.debug(f"{output=}")
        ordered = sorted(output, key=lambda d: (-d["percentage"], d["window"]))

        return ordered
