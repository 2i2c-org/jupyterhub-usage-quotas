"""Async Prometheus client for querying user storage usage and quota."""

import asyncio
import logging
import os
import random
from datetime import UTC, datetime
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


class PrometheusClient:
    """Client for querying Prometheus storage metrics."""

    def __init__(self):
        self.prometheus_url = os.environ.get("PROMETHEUS_URL", "http://prometheus:9090")
        self.namespace = os.environ.get("PROMETHEUS_NAMESPACE", "")
        self.client = None

    async def query(self, query: str) -> dict[str, Any]:
        """Execute a PromQL query."""
        if self.client is None:
            self.client = aiohttp.ClientSession()

        url = f"{self.prometheus_url}/api/v1/query"
        params = {"query": query}

        try:
            async with self.client.get(url, params=params) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as e:
            logger.error(f"Error querying Prometheus: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

    def _find_matching_result(self, data: dict[str, Any]) -> list | None:
        """Find the [timestamp, value] pair for the matching namespace in a Prometheus response.

        Returns:
            The value pair list or None if no matching result found.
        """
        if data.get("status") != "success":
            return None
        for result in data.get("data", {}).get("result", []):
            if result.get("metric", {}).get("namespace") == self.namespace:
                value_pair = result.get("value", [])
                return value_pair if len(value_pair) == 2 else None
        return None

    def _parse_value_result(self, data: dict[str, Any]) -> int | None:
        pair = self._find_matching_result(data)
        if not pair:
            return None
        try:
            return int(float(pair[1]))
        except (ValueError, TypeError):
            logger.warning(f"Non-numeric value in Prometheus response: {pair[1]}")
            return None

    def _with_label_replace(self, metric: str) -> str:
        return f'label_replace({metric}, "username", "$1", "directory", "(.*)")'

    def _parse_timestamp_result(self, data: dict[str, Any]) -> datetime | None:
        pair = self._find_matching_result(data)
        return datetime.fromtimestamp(float(pair[1]), tz=UTC) if pair else None

    def _get_mock_data(self, username: str) -> dict[str, Any]:
        """Return mock data for development when PROMETHEUS_NAMESPACE is not set.

        Randomly returns 50% usage, 95% usage, or an error state.
        """
        scenario = random.choice([0.50, 0.95, "error"])

        if scenario == "error":
            return {
                "username": username,
                "error": "Unable to reach Prometheus. Please try again later.",
            }

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

    async def get_user_usage(self, username: str) -> dict[str, Any]:
        """Get storage usage and quota for a specific user.

        Returns:
            Dictionary with usage information, or an error dict if data is unavailable.
        """
        if not self.namespace:
            logger.warning(
                "PROMETHEUS_NAMESPACE is not set — returning mock data for development"
            )
            return self._get_mock_data(username)

        logger.info(f"Fetching usage data for user: {username}")

        base_quota_metric = (
            f'dirsize_hard_limit_bytes{{namespace!="", directory="{username}"}}'
        )
        base_usage_metric = (
            f'dirsize_total_size_bytes{{namespace!="", directory="{username}"}}'
        )

        quota_value_query = self._with_label_replace(base_quota_metric)
        usage_value_query = self._with_label_replace(base_usage_metric)
        usage_timestamp_query = self._with_label_replace(
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
            logger.error(f"Error fetching usage data concurrently for {username}: {e}")
            return {
                "username": username,
                "error": "Unable to reach Prometheus. Please try again later.",
            }

        quota_bytes = self._parse_value_result(quota_value_data)
        usage_bytes = self._parse_value_result(usage_value_data)
        last_updated_dt = self._parse_timestamp_result(usage_timestamp_data)

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

    async def close(self):
        if self.client is not None:
            await self.client.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, _exc_type, _exc_val, _exc_tb):
        await self.close()
