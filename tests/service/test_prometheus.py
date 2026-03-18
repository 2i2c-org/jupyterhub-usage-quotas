"""Tests for Prometheus integration and client"""

import random
from unittest.mock import AsyncMock

import httpx
import pytest
import respx

from jupyterhub_usage_quotas.service.prometheus_client import PrometheusClient
from tests.service.fixtures.prometheus_responses import (
    PROMETHEUS_EMPTY_RESULT,
    PROMETHEUS_ERROR_RESPONSE,
    PROMETHEUS_MALFORMED_INVALID_VALUE,
    PROMETHEUS_MALFORMED_NO_DATA,
    PROMETHEUS_MALFORMED_NO_RESULT,
    PROMETHEUS_MALFORMED_NON_NUMERIC,
    PROMETHEUS_MULTI_NS_QUOTA,
    PROMETHEUS_MULTI_NS_TIMESTAMP,
    PROMETHEUS_MULTI_NS_USAGE,
    PROMETHEUS_MULTIPLE_NAMESPACES_QUOTA,
    PROMETHEUS_QUOTA_50_PERCENT,
    PROMETHEUS_TIMESTAMP_50_PERCENT,
    PROMETHEUS_USAGE_50_PERCENT,
)


class TestParseValueResult:
    """Test the _parse_value_result helper"""

    def test_parses_correct_namespace(self):
        client = PrometheusClient()
        client.namespace = "staging"
        value_bytes = client._parse_value_result(PROMETHEUS_MULTI_NS_QUOTA)
        assert value_bytes == 10737418240

    def test_parses_prod_namespace(self):
        client = PrometheusClient()
        client.namespace = "prod"
        value_bytes = client._parse_value_result(PROMETHEUS_MULTI_NS_QUOTA)
        assert value_bytes == 214748364800

    def test_returns_none_for_unknown_namespace(self):
        client = PrometheusClient()
        client.namespace = "nonexistent"
        assert client._parse_value_result(PROMETHEUS_MULTI_NS_QUOTA) is None

    def test_returns_none_for_failed_status(self):
        client = PrometheusClient()
        client.namespace = "prod"
        assert client._parse_value_result({"status": "error", "error": "bad query"}) is None

    def test_returns_none_for_empty_results(self):
        client = PrometheusClient()
        client.namespace = "prod"
        assert (
            client._parse_value_result(
                {"status": "success", "data": {"resultType": "vector", "result": []}}
            )
            is None
        )


class TestGetUserUsageWithPrometheus:
    """Test get_user_usage with mocked Prometheus responses"""

    @pytest.mark.asyncio
    async def test_returns_usage_data(self):
        client = PrometheusClient()
        client.namespace = "staging"
        client.query = AsyncMock(
            side_effect=[
                PROMETHEUS_MULTI_NS_QUOTA,
                PROMETHEUS_MULTI_NS_USAGE,
                PROMETHEUS_MULTI_NS_TIMESTAMP,
            ]
        )

        usage_data = await client.get_user_usage("testuser")

        assert usage_data["username"] == "testuser"
        assert usage_data["quota_bytes"] == 10737418240
        assert usage_data["usage_bytes"] == 243240960
        assert usage_data["percentage"] > 0
        assert "last_updated" in usage_data
        assert "error" not in usage_data

        await client.close()

    @pytest.mark.asyncio
    async def test_returns_error_when_prometheus_unreachable(self):
        client = PrometheusClient()
        client.namespace = "prod"
        client.query = AsyncMock(side_effect=Exception("Connection refused"))

        usage_data = await client.get_user_usage("testuser")

        assert "error" in usage_data
        assert usage_data["username"] == "testuser"

        await client.close()

    @pytest.mark.asyncio
    async def test_returns_error_when_no_results_for_user(self):
        empty_response = {
            "status": "success",
            "data": {"resultType": "vector", "result": []},
        }
        client = PrometheusClient()
        client.namespace = "prod"
        client.query = AsyncMock(return_value=empty_response)

        usage_data = await client.get_user_usage("unknownuser")

        assert "error" in usage_data
        assert usage_data["username"] == "unknownuser"

        await client.close()


class TestPrometheusTimeouts:
    """Test timeout handling"""

    @pytest.mark.asyncio
    async def test_handles_connection_timeout(self, mocker):
        """Should return error on connection timeout"""
        client = PrometheusClient()
        client.namespace = "prod"
        client.query = AsyncMock(side_effect=TimeoutError("Connection timeout"))

        usage_data = await client.get_user_usage("testuser")

        assert "error" in usage_data
        assert usage_data["username"] == "testuser"
        assert "Prometheus" in usage_data["error"]

        await client.close()

    @pytest.mark.asyncio
    async def test_handles_aiohttp_timeout(self, mocker):
        """Should handle httpx.TimeoutException"""
        client = PrometheusClient()
        client.namespace = "prod"
        client.query = AsyncMock(side_effect=httpx.TimeoutException("Read timeout"))

        usage_data = await client.get_user_usage("testuser")

        assert "error" in usage_data
        assert usage_data["username"] == "testuser"

        await client.close()


class TestPrometheusMalformedResponses:
    """Test handling of malformed Prometheus responses"""

    def test_handles_missing_data_field(self):
        """Should handle response missing 'data' field"""
        client = PrometheusClient()
        client.namespace = "prod"
        result = client._find_matching_result(PROMETHEUS_MALFORMED_NO_DATA)
        assert result is None

    def test_handles_missing_result_field(self):
        """Should handle response missing 'result' field"""
        client = PrometheusClient()
        client.namespace = "prod"
        result = client._find_matching_result(PROMETHEUS_MALFORMED_NO_RESULT)
        assert result is None

    def test_handles_invalid_value_structure(self):
        """Should handle metrics with wrong value structure"""
        client = PrometheusClient()
        client.namespace = "prod"
        result = client._parse_value_result(PROMETHEUS_MALFORMED_INVALID_VALUE)
        assert result is None

    def test_handles_non_numeric_values(self):
        """Should handle non-numeric metric values"""
        client = PrometheusClient()
        client.namespace = "prod"
        result = client._parse_value_result(PROMETHEUS_MALFORMED_NON_NUMERIC)
        assert result is None

    @pytest.mark.asyncio
    async def test_handles_empty_string_namespace(self):
        """Should fall back to mock data when namespace is empty"""
        client = PrometheusClient()
        client.namespace = ""

        usage_data = await client.get_user_usage("testuser")

        assert usage_data["username"] == "testuser"
        assert "quota_bytes" in usage_data or "error" in usage_data

        await client.close()

    @pytest.mark.asyncio
    async def test_handles_invalid_json_response(self, mocker):
        """Should handle non-JSON responses"""
        client = PrometheusClient()
        client.namespace = "prod"
        client.query = AsyncMock(side_effect=Exception("Invalid JSON"))

        usage_data = await client.get_user_usage("testuser")

        assert "error" in usage_data
        assert usage_data["username"] == "testuser"

        await client.close()


class TestPrometheusMultipleNamespaces:
    """Test namespace filtering"""

    @pytest.mark.asyncio
    async def test_filters_correct_namespace_with_multiple_results(self):
        """Should select metric matching configured namespace"""
        client = PrometheusClient()
        client.namespace = "prod"
        value_bytes = client._parse_value_result(PROMETHEUS_MULTIPLE_NAMESPACES_QUOTA)
        assert value_bytes == 10737418240  # prod namespace value (10 GB)

    @pytest.mark.asyncio
    async def test_filters_staging_namespace(self):
        """Should correctly filter staging namespace"""
        client = PrometheusClient()
        client.namespace = "staging"
        value_bytes = client._parse_value_result(PROMETHEUS_MULTIPLE_NAMESPACES_QUOTA)
        assert value_bytes == 5368709120  # staging namespace value (5 GB)

    @pytest.mark.asyncio
    async def test_returns_none_when_namespace_not_found(self):
        """Should return None if namespace doesn't exist in results"""
        client = PrometheusClient()
        client.namespace = "nonexistent"
        assert client._parse_value_result(PROMETHEUS_MULTIPLE_NAMESPACES_QUOTA) is None


class TestPrometheusUnavailability:
    """Test Prometheus unavailability scenarios"""

    @pytest.mark.asyncio
    async def test_handles_prometheus_server_down(self, mocker):
        """Should return error when Prometheus is unreachable"""
        client = PrometheusClient()
        client.namespace = "prod"
        client.query = AsyncMock(side_effect=httpx.RequestError("Connection refused"))

        usage_data = await client.get_user_usage("testuser")

        assert "error" in usage_data
        assert usage_data["username"] == "testuser"
        assert "Prometheus" in usage_data["error"]

        await client.close()

    @pytest.mark.asyncio
    async def test_handles_prometheus_500_error(self):
        """Should handle Prometheus server errors"""
        client = PrometheusClient()
        client.namespace = "prod"
        client.query = AsyncMock(return_value=PROMETHEUS_ERROR_RESPONSE)

        usage_data = await client.get_user_usage("testuser")

        assert "error" in usage_data
        assert usage_data["username"] == "testuser"

        await client.close()

    @pytest.mark.asyncio
    async def test_handles_prometheus_network_error(self, mocker):
        """Should handle network errors"""
        client = PrometheusClient()
        client.namespace = "prod"
        client.query = AsyncMock(side_effect=Exception("Network error"))

        usage_data = await client.get_user_usage("testuser")

        assert "error" in usage_data
        assert usage_data["username"] == "testuser"

        await client.close()

    @pytest.mark.asyncio
    async def test_handles_partial_query_failure(self):
        """Should handle when one query succeeds but others fail"""
        client = PrometheusClient()
        client.namespace = "prod"
        client.query = AsyncMock(
            side_effect=[
                PROMETHEUS_QUOTA_50_PERCENT,
                Exception("Query failed"),
                PROMETHEUS_TIMESTAMP_50_PERCENT,
            ]
        )

        usage_data = await client.get_user_usage("testuser")

        assert "error" in usage_data
        assert usage_data["username"] == "testuser"

        await client.close()


class TestPrometheusUserWithNoData:
    """Test users without quota data"""

    @pytest.mark.asyncio
    async def test_returns_error_for_user_with_no_quota(self):
        """Should return 'No storage data found' error"""
        client = PrometheusClient()
        client.namespace = "prod"
        client.query = AsyncMock(return_value=PROMETHEUS_EMPTY_RESULT)

        usage_data = await client.get_user_usage("unknownuser")

        assert "error" in usage_data
        assert usage_data["username"] == "unknownuser"
        assert "No storage data found" in usage_data["error"]

        await client.close()

    @pytest.mark.asyncio
    async def test_returns_error_when_quota_exists_but_usage_missing(self):
        """Should handle quota data without usage data"""
        client = PrometheusClient()
        client.namespace = "prod"
        client.query = AsyncMock(
            side_effect=[
                PROMETHEUS_QUOTA_50_PERCENT,
                PROMETHEUS_EMPTY_RESULT,
                PROMETHEUS_EMPTY_RESULT,
            ]
        )

        usage_data = await client.get_user_usage("testuser")

        assert "error" in usage_data
        assert "No storage data found" in usage_data["error"]

        await client.close()

    @pytest.mark.asyncio
    async def test_returns_error_when_usage_exists_but_quota_missing(self):
        """Should handle usage data without quota data"""
        client = PrometheusClient()
        client.namespace = "prod"
        client.query = AsyncMock(
            side_effect=[
                PROMETHEUS_EMPTY_RESULT,
                PROMETHEUS_USAGE_50_PERCENT,
                PROMETHEUS_TIMESTAMP_50_PERCENT,
            ]
        )

        usage_data = await client.get_user_usage("testuser")

        assert "error" in usage_data
        assert "No storage data found" in usage_data["error"]

        await client.close()

    @pytest.mark.asyncio
    async def test_returns_error_when_timestamp_missing(self):
        """Should handle missing timestamp data"""
        client = PrometheusClient()
        client.namespace = "prod"
        client.query = AsyncMock(
            side_effect=[
                PROMETHEUS_QUOTA_50_PERCENT,
                PROMETHEUS_USAGE_50_PERCENT,
                PROMETHEUS_EMPTY_RESULT,
            ]
        )

        usage_data = await client.get_user_usage("testuser")

        assert "error" in usage_data
        assert "No storage data found" in usage_data["error"]

        await client.close()


class TestPrometheusClientQuery:
    """Test the query method of PrometheusClient"""

    @pytest.mark.asyncio
    async def test_query_raises_request_error(self):
        """Should propagate httpx.RequestError"""
        client = PrometheusClient()
        client.prometheus_url = "http://prometheus:9090"

        with respx.mock:
            respx.get("http://prometheus:9090/api/v1/query").mock(
                side_effect=httpx.RequestError("Connection refused")
            )
            with pytest.raises(httpx.RequestError):
                await client.query("up")

        await client.close()

    @pytest.mark.asyncio
    async def test_query_raises_on_http_error_status(self):
        """Should propagate HTTPStatusError on non-2xx responses"""
        client = PrometheusClient()
        client.prometheus_url = "http://prometheus:9090"

        with respx.mock:
            respx.get("http://prometheus:9090/api/v1/query").mock(
                return_value=httpx.Response(500)
            )
            with pytest.raises(httpx.HTTPStatusError):
                await client.query("up")

        await client.close()


class TestPrometheusClientContextManager:
    """Test async context manager protocol"""

    @pytest.mark.asyncio
    async def test_async_context_manager_returns_self(self):
        """__aenter__ should return the client instance"""
        async with PrometheusClient() as client:
            assert isinstance(client, PrometheusClient)

    @pytest.mark.asyncio
    async def test_async_context_manager_closes_on_exit(self):
        """__aexit__ should close the underlying httpx client"""
        async with PrometheusClient() as client:
            underlying = client.client

        assert underlying.is_closed


class TestGetMockDataErrorScenario:
    """Test both branches of _get_mock_data"""

    def test_returns_error_dict_when_scenario_is_error(self, monkeypatch):
        """Should return an error dict when random.choice yields 'error'"""
        monkeypatch.setattr(random, "choice", lambda _: "error")
        client = PrometheusClient()
        result = client._get_mock_data("testuser")

        assert result["username"] == "testuser"
        assert "error" in result
        assert "Prometheus" in result["error"]

    def test_returns_usage_dict_when_scenario_is_numeric(self, monkeypatch):
        """Should return usage data when random.choice yields a numeric scenario"""
        monkeypatch.setattr(random, "choice", lambda _: 0.50)
        client = PrometheusClient()
        result = client._get_mock_data("testuser")

        assert result["username"] == "testuser"
        assert "error" not in result
        assert result["percentage"] == 50.0
        assert "usage_bytes" in result
        assert "quota_bytes" in result
        assert "last_updated" in result


class TestPrometheusEdgeCaseValues:
    """Test edge case values in Prometheus data"""

    @pytest.mark.asyncio
    async def test_handles_very_large_values(self):
        """Should handle very large byte values (petabytes)"""
        client = PrometheusClient()
        client.namespace = "prod"

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

        result = client._parse_value_result(large_value_response)
        assert result == 1125899906842624

    @pytest.mark.asyncio
    async def test_prevents_division_by_zero(self):
        """Should handle division by zero when quota is 0"""
        client = PrometheusClient()
        client.namespace = "prod"

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
                PROMETHEUS_USAGE_50_PERCENT,
                PROMETHEUS_TIMESTAMP_50_PERCENT,
            ]
        )

        usage_data = await client.get_user_usage("testuser")

        assert usage_data["percentage"] == 0

        await client.close()
