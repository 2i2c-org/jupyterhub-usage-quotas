"""Tests for OAuth authentication and session management"""

import re
from urllib.parse import parse_qs, urlparse

import pytest
import respx
from httpx import Response

from tests.service.conftest import get_session, set_session


class MockRequest:
    """Mock Request object for testing get_current_user"""

    def __init__(self, session_data=None):
        self.session = session_data or {}


class TestGetCurrentUserDependency:
    """Test the get_current_user dependency function"""

    @pytest.mark.asyncio
    async def test_unauthenticated_returns_js_redirect_not_307(self, mock_env_vars):
        """Unauthenticated request must return HTML with JS redirect, not a 307.

        A plain HTTP 307 redirect inside an iframe is blocked by JupyterHub's
        CSP frame-ancestors directive on the login page. The JS approach redirects
        the top-level frame instead, bypassing the CSP restriction.
        """
        from jupyterhub_usage_quotas.service.app import get_current_user

        request = MockRequest(session_data={})
        response = await get_current_user(request)

        assert response.status_code == 200
        assert "window.top.location.href" in response.body.decode()

    @pytest.mark.asyncio
    async def test_js_redirect_targets_public_hub_url(self, mock_env_vars):
        """JS redirect URL must use PUBLIC_HUB_URL (external URL, not internal)"""
        from jupyterhub_usage_quotas.service.app import get_current_user

        request = MockRequest(session_data={})
        response = await get_current_user(request)

        body = response.body.decode()
        assert "http://localhost:8000/hub/api/oauth2/authorize" in body

    @pytest.mark.asyncio
    async def test_js_redirect_not_internal_hub_url(self, mock_env_vars):
        """JS redirect must NOT use the internal Hub API URL (unreachable by browser)"""
        from jupyterhub_usage_quotas.service.app import get_current_user

        request = MockRequest(session_data={})
        response = await get_current_user(request)

        body = response.body.decode()
        assert "http://test-hub:8081" not in body

    @pytest.mark.asyncio
    async def test_returns_user_when_in_session(self, mock_env_vars):
        """Should return user directly when already in session"""
        from jupyterhub_usage_quotas.service.app import get_current_user

        mock_user = {"name": "testuser", "admin": False}
        request = MockRequest(session_data={"user": mock_user})

        result = await get_current_user(request)
        assert result == mock_user


class TestCompleteOAuthFlow:
    """Integration test for complete OAuth flow"""

    def _extract_oauth_url_from_js(self, body: str) -> str:
        """Extract the redirect URL from the JS frame-break snippet."""
        match = re.search(r'window\.top\.location\.href\s*=\s*"([^"]+)"', body)
        assert match, f"No JS redirect URL found in: {body}"
        return match.group(1)

    def test_unauthenticated_home_returns_js_not_307(self, client, app, mock_env_vars):
        """GET / when unauthenticated must return 200 with JS redirect, not 307."""
        with client:
            response = client.get("/services/usage/", follow_redirects=False)
            assert response.status_code == 200
            assert "window.top.location.href" in response.text

    def test_full_oauth_flow_success(self, client, app, mock_env_vars, mock_prometheus_client):
        """Test complete flow: JS redirect → callback → authenticated access"""
        with respx.mock:
            respx.post("http://test-hub:8081/hub/api/oauth2/token").mock(
                return_value=Response(200, json={"access_token": "test-token"})
            )
            respx.get("http://test-hub:8081/hub/api/user").mock(
                return_value=Response(
                    200, json={"name": "testuser", "admin": False, "groups": ["users"]}
                )
            )

            with client:
                # Step 1: unauthenticated hit → JS frame-break redirect
                response = client.get("/services/usage/", follow_redirects=False)
                assert response.status_code == 200
                assert "window.top.location.href" in response.text

                oauth_url = self._extract_oauth_url_from_js(response.text)
                state = parse_qs(urlparse(oauth_url).query)["state"][0]

                session = get_session(client, app)
                assert session.get("oauth_state") == state

                # Step 2: OAuth callback exchanges code for token
                response = client.get(
                    f"/services/usage/oauth_callback?code=auth123&state={state}",
                    follow_redirects=False,
                )
                assert response.status_code == 307
                assert response.headers["Location"] == "/services/usage/"

                session = get_session(client, app)
                assert "user" in session
                assert session["user"]["name"] == "testuser"
                assert "oauth_state" not in session

                # Step 3: now authenticated, home returns content
                response = client.get("/services/usage/", follow_redirects=False)
                assert response.status_code == 200
                assert "Home storage" in response.text


class TestSessionWithRoutes:
    """Test session behavior with actual routes"""

    def test_session_cleared_user_must_reauthenticate(self, client, app, mock_env_vars):
        """User with cleared session should get JS redirect, not a 307"""
        set_session(client, app, {"user": {"name": "testuser"}})

        client.cookies.clear()

        response = client.get("/services/usage/", follow_redirects=False)
        assert response.status_code == 200
        assert "window.top.location.href" in response.text
