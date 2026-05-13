"""Tests for Prometheus integration and client"""

import random
from unittest.mock import AsyncMock

import aiohttp
import pytest
from aioresponses import aioresponses

from jupyterhub_usage_quotas.client import PrometheusClient
from jupyterhub_usage_quotas.services.usage_viewer.quota_client import QuotaClient
from tests.services.fixtures.prometheus_responses import (
    PROMETHEUS_COMPUTE_QUOTA_MULTIPLE,
    PROMETHEUS_COMPUTE_USAGE_MULTIPLE,
    PROMETHEUS_EMPTY_RESULT,
    PROMETHEUS_ERROR_RESPONSE,
    PROMETHEUS_MALFORMED_NO_DATA,
    PROMETHEUS_MALFORMED_NO_RESULT,
    PROMETHEUS_STORAGE_MALFORMED_INVALID_VALUE,
    PROMETHEUS_STORAGE_MALFORMED_NON_NUMERIC,
    PROMETHEUS_STORAGE_QUOTA_50_PERCENT,
    PROMETHEUS_STORAGE_TIMESTAMP_50_PERCENT,
    PROMETHEUS_STORAGE_USAGE_50_PERCENT,
)


class TestParseValueResult:
    """Test the parse_value_result helper"""

    def test_parses_value_from_single_result(self):
        value_bytes = QuotaClient.parse_value_result(
            PROMETHEUS_STORAGE_QUOTA_50_PERCENT
        )
        assert value_bytes == 10737418240

    def test_returns_none_for_failed_status(self):
        assert (
            QuotaClient.parse_value_result({"status": "error", "error": "bad query"})
            is None
        )

    def test_returns_none_for_empty_results(self):
        assert (
            QuotaClient.parse_value_result(
                {"status": "success", "data": {"resultType": "vector", "result": []}}
            )
            is None
        )


class TestGetUserStorageUsageWithPrometheus:
    """Test get_user_storage_usage with mocked Prometheus responses"""

    @pytest.mark.asyncio
    async def test_returns_usage_data(self):
        client = QuotaClient("http://prometheus:9090", namespace="prod")
        client.query = AsyncMock(
            side_effect=[
                PROMETHEUS_STORAGE_QUOTA_50_PERCENT,
                PROMETHEUS_STORAGE_USAGE_50_PERCENT,
                PROMETHEUS_STORAGE_TIMESTAMP_50_PERCENT,
            ]
        )

        usage_data = await client.get_user_storage_usage(username="testuser")

        assert usage_data["username"] == "testuser"
        assert usage_data["quota_bytes"] == 10737418240
        assert usage_data["usage_bytes"] == 5368709120
        assert usage_data["percentage"] > 0
        assert "last_updated" in usage_data
        assert "error" not in usage_data

    @pytest.mark.asyncio
    async def test_returns_error_when_prometheus_unreachable(self):
        client = QuotaClient("http://prometheus:9090", namespace="prod")
        client.query = AsyncMock(side_effect=Exception("Connection refused"))

        usage_data = await client.get_user_storage_usage(username="testuser")

        assert "error" in usage_data
        assert usage_data["username"] == "testuser"

    @pytest.mark.asyncio
    async def test_returns_error_when_no_results_for_user(self):
        empty_response = {
            "status": "success",
            "data": {"resultType": "vector", "result": []},
        }
        client = QuotaClient("http://prometheus:9090", namespace="prod")
        client.query = AsyncMock(return_value=empty_response)

        usage_data = await client.get_user_storage_usage(username="unknownuser")

        assert "error" in usage_data
        assert usage_data["username"] == "unknownuser"


class TestGetUserComputeUsageWithPrometheus:
    """Test get_user_compute_usage with mocked Prometheus responses"""

    @pytest.mark.asyncio
    async def test_returns_usage_data(self):
        client = QuotaClient("http://prometheus:9090", namespace="prod")
        client.query = AsyncMock(
            side_effect=[
                PROMETHEUS_COMPUTE_USAGE_MULTIPLE,
                PROMETHEUS_COMPUTE_QUOTA_MULTIPLE,
            ]
        )
        usage_data = await client.get_user_compute_usage(username="testuser")
        assert len(usage_data) == 2
        # check ordering by -percentage and then window
        assert usage_data[0]["percentage"] > usage_data[1]["percentage"]
        assert usage_data[0]["window"] < usage_data[1]["window"]

    @pytest.mark.asyncio
    async def test_returns_error_when_prometheus_unreachable(self):
        client = QuotaClient("http://prometheus:9090", namespace="prod")
        client.query = AsyncMock(side_effect=Exception("Connection refused"))

        usage_data = await client.get_user_compute_usage(username="testuser")

        assert any("error" in u.keys() for u in usage_data)
        assert all(u["username"] == "testuser" for u in usage_data)

    @pytest.mark.asyncio
    async def test_returns_error_when_no_results_for_user(self):
        empty_response = {
            "status": "success",
            "data": {"resultType": "vector", "result": []},
        }
        client = QuotaClient("http://prometheus:9090", namespace="prod")
        client.query = AsyncMock(return_value=empty_response)

        usage_data = await client.get_user_compute_usage(username="unknownuser")

        assert any("error" in u.keys() for u in usage_data)
        assert all(u["username"] == "unknownuser" for u in usage_data)


class TestPrometheusTimeouts:
    """Test timeout handling"""

    @pytest.mark.asyncio
    async def test_handles_connection_timeout(self, mocker):
        """Should return error on connection timeout"""
        client = QuotaClient("http://prometheus:9090", namespace="prod")
        client.query = AsyncMock(side_effect=TimeoutError("Connection timeout"))

        usage_data = await client.get_user_storage_usage(username="testuser")

        assert "error" in usage_data
        assert usage_data["username"] == "testuser"
        assert "Unable to query" in usage_data["error"]

    @pytest.mark.asyncio
    async def test_handles_aiohttp_timeout(self, mocker):
        """Should handle aiohttp.ServerTimeoutError"""
        client = QuotaClient("http://prometheus:9090", namespace="prod")
        client.query = AsyncMock(side_effect=aiohttp.ServerTimeoutError("Read timeout"))

        usage_data = await client.get_user_storage_usage(username="testuser")

        assert "error" in usage_data
        assert usage_data["username"] == "testuser"


class TestPrometheusMalformedResponses:
    """Test handling of malformed Prometheus responses"""

    def test_handles_missing_data_field(self):
        """Should handle response missing 'data' field"""
        result = QuotaClient.find_matching_result(PROMETHEUS_MALFORMED_NO_DATA)
        assert result is None

    def test_handles_missing_result_field(self):
        """Should handle response missing 'result' field"""
        result = QuotaClient.find_matching_result(PROMETHEUS_MALFORMED_NO_RESULT)
        assert result is None

    def test_handles_invalid_value_structure(self):
        """Should handle metrics with wrong value structure"""
        result = QuotaClient.parse_value_result(
            PROMETHEUS_STORAGE_MALFORMED_INVALID_VALUE
        )
        assert result is None

    def test_handles_non_numeric_values(self):
        """Should handle non-numeric metric values"""
        result = QuotaClient.parse_value_result(
            PROMETHEUS_STORAGE_MALFORMED_NON_NUMERIC
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_handles_empty_string_namespace(self):
        """Should fall back to mock data when namespace is empty AND dev_mode is True"""
        client = QuotaClient(
            "http://127.0.0.1:9090",  # default URL
            namespace="",
            dev_mode=True,  # Enable mock data
        )

        usage_data = await client.get_user_storage_usage(username="testuser")

        assert usage_data["username"] == "testuser"
        assert "quota_bytes" in usage_data or "error" in usage_data

    @pytest.mark.asyncio
    async def test_handles_invalid_json_response(self, mocker):
        """Should handle non-JSON responses"""
        client = QuotaClient("http://prometheus:9090", namespace="prod")
        client.query = AsyncMock(side_effect=Exception("Invalid JSON"))

        usage_data = await client.get_user_storage_usage(username="testuser")

        assert "error" in usage_data
        assert usage_data["username"] == "testuser"


class TestPrometheusUnavailability:
    """Test Prometheus unavailability scenarios"""

    @pytest.mark.asyncio
    async def test_handles_prometheus_server_down(self, mocker):
        """Should return error when Prometheus is unreachable"""
        client = QuotaClient("http://prometheus:9090", namespace="prod")
        client.query = AsyncMock(side_effect=aiohttp.ClientError("Connection refused"))

        usage_data = await client.get_user_storage_usage(username="testuser")

        assert "error" in usage_data
        assert usage_data["username"] == "testuser"
        assert "Unable to query" in usage_data["error"]

    @pytest.mark.asyncio
    async def test_handles_prometheus_500_error(self):
        """Should handle Prometheus server errors"""
        client = QuotaClient("http://prometheus:9090", namespace="prod")
        client.query = AsyncMock(return_value=PROMETHEUS_ERROR_RESPONSE)

        usage_data = await client.get_user_storage_usage(username="testuser")

        assert "error" in usage_data
        assert usage_data["username"] == "testuser"

    @pytest.mark.asyncio
    async def test_handles_prometheus_network_error(self, mocker):
        """Should handle network errors"""
        client = QuotaClient("http://prometheus:9090", namespace="prod")
        client.query = AsyncMock(side_effect=Exception("Network error"))

        usage_data = await client.get_user_storage_usage(username="testuser")

        assert "error" in usage_data
        assert usage_data["username"] == "testuser"

    @pytest.mark.asyncio
    async def test_handles_partial_query_failure(self):
        """Should handle when one query succeeds but others fail"""
        client = QuotaClient("http://prometheus:9090", namespace="prod")
        client.query = AsyncMock(
            side_effect=[
                PROMETHEUS_STORAGE_QUOTA_50_PERCENT,
                Exception("Query failed"),
                PROMETHEUS_STORAGE_TIMESTAMP_50_PERCENT,
            ]
        )

        usage_data = await client.get_user_storage_usage(username="testuser")

        assert "error" in usage_data
        assert usage_data["username"] == "testuser"


class TestPrometheusUserWithNoStorageData:
    """Test users without storage quota data"""

    @pytest.mark.asyncio
    async def test_returns_error_for_user_with_no_quota(self):
        """Should return 'No storage data found' error"""
        client = QuotaClient("http://prometheus:9090", namespace="prod")
        client.query = AsyncMock(return_value=PROMETHEUS_EMPTY_RESULT)

        usage_data = await client.get_user_storage_usage(username="unknownuser")

        assert "error" in usage_data
        assert usage_data["username"] == "unknownuser"
        assert "No storage data found" in usage_data["error"]

    @pytest.mark.asyncio
    async def test_returns_error_when_quota_exists_but_usage_missing(self):
        """Should handle quota data without usage data"""
        client = QuotaClient("http://prometheus:9090", namespace="prod")
        client.query = AsyncMock(
            side_effect=[
                PROMETHEUS_STORAGE_QUOTA_50_PERCENT,
                PROMETHEUS_EMPTY_RESULT,
                PROMETHEUS_EMPTY_RESULT,
            ]
        )

        usage_data = await client.get_user_storage_usage(username="testuser")

        assert "error" in usage_data
        assert "No storage data found" in usage_data["error"]

    @pytest.mark.asyncio
    async def test_returns_error_when_usage_exists_but_quota_missing(self):
        """Should handle usage data without quota data"""
        client = QuotaClient("http://prometheus:9090", namespace="prod")
        client.query = AsyncMock(
            side_effect=[
                PROMETHEUS_EMPTY_RESULT,
                PROMETHEUS_STORAGE_USAGE_50_PERCENT,
                PROMETHEUS_STORAGE_TIMESTAMP_50_PERCENT,
            ]
        )

        usage_data = await client.get_user_storage_usage(username="testuser")

        assert "error" in usage_data
        assert "No storage data found" in usage_data["error"]

    @pytest.mark.asyncio
    async def test_returns_error_when_timestamp_missing(self):
        """Should handle missing timestamp data"""
        client = QuotaClient("http://prometheus:9090", namespace="prod")
        client.query = AsyncMock(
            side_effect=[
                PROMETHEUS_STORAGE_QUOTA_50_PERCENT,
                PROMETHEUS_STORAGE_USAGE_50_PERCENT,
                PROMETHEUS_EMPTY_RESULT,
            ]
        )

        usage_data = await client.get_user_storage_usage(username="testuser")

        assert "error" in usage_data
        assert "No storage data found" in usage_data["error"]


class TestPrometheusClientQuery:
    """Test the query method of PrometheusClient from client.py"""

    @pytest.mark.asyncio
    async def test_query_raises_request_error(self):
        """Should propagate aiohttp.ClientError"""
        client = PrometheusClient(prometheus_url="http://prometheus:9090")

        with aioresponses() as mock:
            mock.get(
                "http://prometheus:9090/api/v1/query?query=up",
                exception=aiohttp.ClientError("Connection refused"),
            )
            with pytest.raises(aiohttp.ClientError):
                await client.query("up")

        await client.close()

    @pytest.mark.asyncio
    async def test_query_raises_on_http_error_status(self):
        """Should propagate ClientResponseError on non-2xx responses"""
        client = PrometheusClient(prometheus_url="http://prometheus:9090")

        with aioresponses() as mock:
            mock.get(
                "http://prometheus:9090/api/v1/query?query=up",
                status=500,
                body="Internal Server Error",
            )
            with pytest.raises(aiohttp.ClientResponseError):
                await client.query("up")

        await client.close()


class TestPrometheusClientContextManager:
    """Test async context manager protocol"""

    @pytest.mark.asyncio
    async def test_async_context_manager_closes_on_exit(self):
        """__aexit__ should close the underlying aiohttp session"""
        async with PrometheusClient(prometheus_url="http://prometheus:9090") as client:
            # Trigger lazy initialization by making a request
            with aioresponses() as mock:
                mock.get(
                    "http://prometheus:9090/api/v1/query?query=up",
                    payload={"status": "success", "data": {"result": []}},
                )
                await client.query("up")
            underlying = client.session

        assert underlying.closed


class TestGetMockDataErrorScenario:
    """Test both branches of get_mock_data"""

    def test_returns_error_dict_when_scenario_is_error(self, monkeypatch):
        """Should return an error dict when random.choice yields 'error'"""
        monkeypatch.setattr(random, "choice", lambda _: "error")
        result = QuotaClient("http://test", namespace="").get_mock_data("testuser")

        assert result["username"] == "testuser"
        assert "error" in result
        assert "Unable to query" in result["error"]

    def test_returns_usage_dict_when_scenario_is_numeric(self, monkeypatch):
        """Should return usage data when random.choice yields a numeric scenario"""
        monkeypatch.setattr(random, "choice", lambda _: 0.50)
        result = QuotaClient("http://test", namespace="").get_mock_data("testuser")

        assert result["username"] == "testuser"
        assert "error" not in result
        assert result["percentage"] == 50.0
        assert "usage_bytes" in result
        assert "quota_bytes" in result
        assert "last_updated" in result


class TestConfigurableMetricNames:
    """Test that custom quota_metric / usage_metric are used in PromQL queries."""

    def test_uses_default_metric_names_when_not_configured(self):
        client = QuotaClient("http://prometheus:9090", namespace="prod")
        assert client.metrics["home_storage"]["quota"] == "dirsize_hard_limit_bytes"
        assert client.metrics["home_storage"]["usage"] == "dirsize_total_size_bytes"

    @pytest.mark.asyncio
    async def test_custom_metric_names_appear_in_queries(self):
        client = QuotaClient(
            "http://prometheus:9090",
            namespace="staging",
            prometheus_usage_quota_metrics={
                "home_storage": {
                    "usage": "custom_total_size_bytes",
                    "quota": "custom_hard_limit_bytes",
                }
            },
        )
        captured_queries = []
        original_side_effect = [
            PROMETHEUS_STORAGE_QUOTA_50_PERCENT,
            PROMETHEUS_STORAGE_USAGE_50_PERCENT,
            PROMETHEUS_STORAGE_TIMESTAMP_50_PERCENT,
        ]
        idx = 0

        async def capturing_mock(query):
            nonlocal idx
            captured_queries.append(query)
            result = original_side_effect[idx]
            idx += 1
            return result

        client.query = capturing_mock

        await client.get_user_storage_usage(username="testuser")

        assert any("custom_hard_limit_bytes" in q for q in captured_queries)
        assert any("custom_total_size_bytes" in q for q in captured_queries)
        assert not any("dirsize_hard_limit_bytes" in q for q in captured_queries)
        assert not any("dirsize_total_size_bytes" in q for q in captured_queries)


class TestPrometheusEdgeCaseValues:
    """Test edge case values in Prometheus data"""

    def test_handles_very_large_values(self):
        """Should handle very large byte values (petabytes)"""
        large_value_response = {
            "status": "success",
            "data": {
                "resultType": "vector",
                "result": [
                    {
                        "metric": {"namespace": "prod"},
                        "value": [1771314029.985, "1125899906842624"],  # 1 PB
                    }
                ],
            },
        }

        result = QuotaClient.parse_value_result(large_value_response)
        assert result == 1125899906842624

    @pytest.mark.asyncio
    async def test_prevents_division_by_zero(self):
        """Should handle division by zero when quota is 0"""
        client = QuotaClient("http://prometheus:9090", namespace="prod")
        client.query = AsyncMock(
            side_effect=[
                {
                    "status": "success",
                    "data": {
                        "resultType": "vector",
                        "result": [
                            {
                                "metric": {"namespace": "prod"},
                                "value": [1771314029.985, "0"],
                            }
                        ],
                    },
                },
                PROMETHEUS_STORAGE_USAGE_50_PERCENT,
                PROMETHEUS_STORAGE_TIMESTAMP_50_PERCENT,
            ]
        )

        usage_data = await client.get_user_storage_usage(username="testuser")

        assert usage_data["percentage"] == 0
