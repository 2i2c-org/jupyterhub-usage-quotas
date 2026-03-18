"""Integration tests for end-to-end user flows"""

from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlparse

import pytest
import respx
from fastapi.testclient import TestClient
from httpx import Response

from tests.service.conftest import set_session


@pytest.mark.integration
class TestEndToEndUserFlow:
    """Test complete user flows from start to finish"""

    def test_complete_unauthenticated_to_viewing_usage(
        self, client, mock_env_vars, mock_prometheus_client
    ):
        """Test: unauthenticated → OAuth → view usage"""
        with respx.mock:
            respx.post("http://test-hub:8081/hub/api/oauth2/token").mock(
                return_value=Response(200, json={"access_token": "test-token"})
            )
            respx.get("http://test-hub:8081/hub/api/user").mock(
                return_value=Response(
                    200,
                    json={"name": "testuser", "admin": False, "groups": ["users"]},
                )
            )

            with client:
                response = client.get("/services/usage/", follow_redirects=False)
                assert response.status_code == 307
                assert "oauth2/authorize" in response.headers["Location"]

                location = response.headers["Location"]
                parsed = urlparse(location)
                query_params = parse_qs(parsed.query)
                state = query_params["state"][0]

                response = client.get(
                    f"/services/usage/oauth_callback?code=auth123&state={state}",
                    follow_redirects=False,
                )
                assert response.status_code == 307
                assert response.headers["Location"] == "/services/usage/"

                response = client.get("/services/usage/", follow_redirects=False)
                assert response.status_code == 200
                assert "Home storage" in response.text
                assert "50.0%" in response.text
                assert "5.0 GiB used" in response.text

    def test_returning_user_with_valid_session(
        self, client, app, mock_env_vars, mock_prometheus_client
    ):
        """Test: authenticated user returns → sees usage immediately"""
        with client:
            set_session(
                client,
                app,
                {"user": {"name": "testuser", "admin": False, "groups": ["users"]}},
            )

            response = client.get("/services/usage/", follow_redirects=False)

            assert response.status_code == 200
            assert "Home storage" in response.text
            assert "50.0%" in response.text


@pytest.mark.integration
class TestMultiUserScenarios:
    """Test scenarios with multiple users"""

    def test_different_users_see_their_own_data(self, app, mock_env_vars, mocker):
        """Each user should see only their own usage data"""
        client1 = TestClient(app)
        client2 = TestClient(app)

        def mock_get_user_usage(username):
            if username == "user1":
                return {
                    "username": "user1",
                    "usage_bytes": 5368709120,
                    "quota_bytes": 10737418240,
                    "usage_gb": 5.0,
                    "quota_gb": 10.0,
                    "percentage": 50.0,
                    "last_updated": "2026-02-24T12:00:00+00:00",
                }
            elif username == "user2":
                return {
                    "username": "user2",
                    "usage_bytes": 8589934592,
                    "quota_bytes": 10737418240,
                    "usage_gb": 8.0,
                    "quota_gb": 10.0,
                    "percentage": 80.0,
                    "last_updated": "2026-02-24T12:00:00+00:00",
                }

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get_user_usage.side_effect = mock_get_user_usage

        mocker.patch(
            "jupyterhub_usage_quotas.service.app.PrometheusClient",
            return_value=mock_client,
        )

        set_session(client1, app, {"user": {"name": "user1"}})
        response1 = client1.get("/services/usage/")
        assert response1.status_code == 200
        assert "50.0%" in response1.text
        assert "5.0 GiB used" in response1.text

        set_session(client2, app, {"user": {"name": "user2"}})
        response2 = client2.get("/services/usage/")
        assert response2.status_code == 200
        assert "80.0%" in response2.text
        assert "8.0 GiB used" in response2.text


@pytest.mark.integration
class TestErrorRecovery:
    """Test error handling and recovery"""

    def test_user_can_retry_after_prometheus_error(
        self, client, app, mock_env_vars, mock_prometheus_client
    ):
        """User should be able to refresh after transient error"""
        with client:
            set_session(client, app, {"user": {"name": "testuser"}})

            mock_prometheus_client.get_user_usage.return_value = {
                "username": "testuser",
                "error": "Unable to reach Prometheus. Please try again later.",
            }

            response = client.get("/services/usage/")
            assert response.status_code == 200
            assert "Unable to reach Prometheus" in response.text

            mock_prometheus_client.get_user_usage.return_value = {
                "username": "testuser",
                "usage_bytes": 5368709120,
                "quota_bytes": 10737418240,
                "usage_gb": 5.0,
                "quota_gb": 10.0,
                "percentage": 50.0,
                "last_updated": "2026-02-24T12:00:00+00:00",
            }

            response = client.get("/services/usage/")
            assert response.status_code == 200
            assert "50.0%" in response.text

    def test_user_can_re_authenticate_after_session_clear(self, client, app, mock_env_vars):
        """User should be redirected to OAuth if session expires"""
        with respx.mock:
            respx.post("http://test-hub:8081/hub/api/oauth2/token").mock(
                return_value=Response(200, json={"access_token": "test-token"})
            )
            respx.get("http://test-hub:8081/hub/api/user").mock(
                return_value=Response(200, json={"name": "testuser"})
            )

            with client:
                set_session(client, app, {"user": {"name": "testuser"}})

                client.cookies.clear()

                response = client.get("/services/usage/", follow_redirects=False)
                assert response.status_code == 307
                assert "oauth2/authorize" in response.headers["Location"]

                location = response.headers["Location"]
                state = parse_qs(urlparse(location).query)["state"][0]

                response = client.get(
                    f"/services/usage/oauth_callback?code=new_auth&state={state}",
                    follow_redirects=False,
                )
                assert response.status_code == 307
