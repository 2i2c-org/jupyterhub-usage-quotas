"""Storage quota client for querying Prometheus storage metrics."""

import asyncio
import logging
import random
from datetime import UTC, datetime
from typing import Any

from kubespawner.slugs import escape_slug, safe_slug

from jupyterhub_usage_quotas.client import PrometheusClient

logger = logging.getLogger(__name__)


class StorageQuotaClient(PrometheusClient):
    """Client for storage quota operations using Prometheus.

    Extends PrometheusClient with storage-specific query methods.

    Args:
        prometheus_url: URL of the Prometheus server
        prometheus_auth: Dictionary of Prometheus username and password
        namespace: Prometheus namespace for filtering metrics
        safe_scheme: Username escaping scheme for directory names
        dev_mode: Whether to enable development mode with mock data
        quota_metric: Prometheus metric name for storage quota/hard limit
        usage_metric: Prometheus metric name for current storage usage
        **kwargs: Additional arguments passed to PrometheusClient
    """

    def __init__(
        self,
        prometheus_url: str,
        prometheus_auth: dict | None = None,
        namespace: str = "",
        safe_scheme: bool = True,
        dev_mode: bool = False,
        quota_metric: str = "dirsize_hard_limit_bytes",
        usage_metric: str = "dirsize_total_size_bytes",
        **kwargs,
    ):
        super().__init__(prometheus_url, prometheus_auth, **kwargs)
        self.namespace = namespace
        self.safe_scheme = safe_scheme
        self.dev_mode = dev_mode
        self.quota_metric = quota_metric
        self.usage_metric = usage_metric

    @staticmethod
    def find_matching_result(data: dict[str, Any], namespace: str) -> list | None:
        """Find the [timestamp, value] pair for the matching namespace.

        Args:
            data: Prometheus query response data
            namespace: Namespace to filter results by

        Returns:
            The value pair list [timestamp, value] or None if no matching result found
        """
        if data.get("status") != "success":
            return None
        for result in data.get("data", {}).get("result", []):
            if result.get("metric", {}).get("namespace") == namespace:
                value_pair = result.get("value", [])
                return value_pair if len(value_pair) == 2 else None
        return None

    @staticmethod
    def parse_value_result(data: dict[str, Any], namespace: str) -> int | None:
        """Extract numeric value from Prometheus response.

        Args:
            data: Prometheus query response data
            namespace: Namespace to filter results by

        Returns:
            Integer value or None if parsing fails
        """
        pair = StorageQuotaClient.find_matching_result(data, namespace)
        if not pair:
            return None
        try:
            return int(float(pair[1]))
        except (ValueError, TypeError):
            logger.warning(f"Non-numeric value in Prometheus response: {pair[1]}")
            return None

    @staticmethod
    def parse_timestamp_result(data: dict[str, Any], namespace: str) -> datetime | None:
        """Extract timestamp from Prometheus response.

        Args:
            data: Prometheus query response data
            namespace: Namespace to filter results by

        Returns:
            Datetime object or None if parsing fails
        """
        pair = StorageQuotaClient.find_matching_result(data, namespace)
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
    def escape_username(username: str, safe_scheme: bool = True):
        """
        Escape username to create a safe string for naming directories.

        Args:
            username: Username to escape
            safe_scheme: Kubespawner slug scheme, set to True for modern safe slugs, or False for legacy escaped slugs

        Returns:
            String of escaped username
        """
        if safe_scheme:
            return safe_slug(username)
        else:
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
                "error": "Unable to reach Prometheus. Please try again later.",
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

        directory = self.escape_username(username, safe_scheme=self.safe_scheme)

        base_quota_metric = f'{self.quota_metric}{{namespace="{self.namespace}", directory="{directory}"}}'
        base_usage_metric = f'{self.usage_metric}{{namespace="{self.namespace}", directory="{directory}"}}'

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
                "error": "Unable to reach Prometheus. Please try again later.",
            }

        quota_bytes = self.parse_value_result(quota_value_data, self.namespace)
        usage_bytes = self.parse_value_result(usage_value_data, self.namespace)
        last_updated_dt = self.parse_timestamp_result(
            usage_timestamp_data, self.namespace
        )

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
