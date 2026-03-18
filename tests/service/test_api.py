"""Tests for FastAPI routes"""

from urllib.parse import parse_qs, urlparse

import respx
from httpx import Response

from tests.service.conftest import get_session, set_session


class TestHomeRoute:
    """Test the home route (GET /)"""

    def test_home_redirects_to_oauth_when_not_authenticated(self, client, mock_env_vars):
        """Unauthenticated user should be redirected to JupyterHub OAuth"""
        response = client.get("/services/usage/", follow_redirects=False)

        assert response.status_code == 307
        assert "Location" in response.headers

        location = response.headers["Location"]
        assert "oauth2/authorize" in location
        assert "client_id=" in location
        assert "state=" in location
        assert "redirect_uri=" in location

    def test_home_displays_usage_when_authenticated(
        self, client, app, mock_env_vars, mock_prometheus_client
    ):
        """Authenticated user should see usage data"""
        set_session(
            client,
            app,
            {"user": {"name": "testuser", "admin": False, "groups": ["users"]}},
        )

        response = client.get("/services/usage/")

        assert response.status_code == 200
        assert "Home storage" in response.text
        assert "50.0%" in response.text
        assert "5.0 GiB used" in response.text
        assert "10.0 GiB quota" in response.text

    def test_home_displays_error_when_prometheus_fails(
        self, client, app, mock_env_vars, mock_prometheus_client_with_error
    ):
        """User should see error message when Prometheus is unavailable"""
        set_session(client, app, {"user": {"name": "testuser"}})

        response = client.get("/services/usage/")

        assert response.status_code == 200
        assert "Unable to reach Prometheus" in response.text
        assert "error-message" in response.text

    def test_home_displays_no_data_error(
        self, client, app, mock_env_vars, mock_prometheus_client_no_data
    ):
        """User should see error when no quota data exists"""
        set_session(client, app, {"user": {"name": "testuser"}})

        response = client.get("/services/usage/")

        assert response.status_code == 200
        assert "No storage data found" in response.text

    def test_home_with_high_usage_displays_warning(
        self, client, app, mock_env_vars, mock_prometheus_client_high_usage
    ):
        """User with high usage should see warning styling"""
        set_session(client, app, {"user": {"name": "testuser"}})

        response = client.get("/services/usage/")

        assert response.status_code == 200
        assert "95.0%" in response.text
        assert "#ef4444" in response.text


class TestOAuthCallbackRoute:
    """Test the OAuth callback route"""

    def test_callback_with_valid_state_and_code(self, client, app, mock_env_vars, mock_oauth_state):
        """Valid OAuth callback should authenticate user and redirect"""
        with respx.mock:
            respx.post("http://test-hub:8081/hub/api/oauth2/token").mock(
                return_value=Response(
                    200, json={"access_token": "test-token", "token_type": "Bearer"}
                )
            )
            respx.get("http://test-hub:8081/hub/api/user").mock(
                return_value=Response(
                    200,
                    json={"name": "testuser", "admin": False, "groups": ["users"]},
                )
            )

            set_session(client, app, {"oauth_state": mock_oauth_state})

            response = client.get(
                f"/services/usage/oauth_callback?code=auth123&state={mock_oauth_state}",
                follow_redirects=False,
            )

        assert response.status_code == 307
        assert response.headers["Location"] == "/services/usage/"

        session = get_session(client, app)
        assert "user" in session
        assert session["user"]["name"] == "testuser"
        assert "oauth_state" not in session

    def test_callback_with_invalid_state_returns_400(self, client, app, mock_env_vars):
        """Invalid state should return 400 error (CSRF protection)"""
        set_session(client, app, {"oauth_state": "expected_state"})

        response = client.get(
            "/services/usage/oauth_callback?code=auth123&state=wrong_state",
            follow_redirects=False,
        )

        assert response.status_code == 400
        assert "OAuth state mismatch" in response.text

    def test_callback_with_missing_state_returns_400(self, client, mock_env_vars):
        """Missing state should return 400 error"""
        response = client.get(
            "/services/usage/oauth_callback?code=auth123&state=somestate",
            follow_redirects=False,
        )

        assert response.status_code == 400
        assert "OAuth state mismatch" in response.text

    def test_callback_with_token_exchange_failure(
        self, client, app, mock_env_vars, mock_oauth_state
    ):
        """Failed token exchange should return 500"""
        with respx.mock:
            respx.post("http://test-hub:8081/hub/api/oauth2/token").mock(
                return_value=Response(400, json={"error": "invalid_grant"})
            )

            set_session(client, app, {"oauth_state": mock_oauth_state})

            response = client.get(
                f"/services/usage/oauth_callback?code=badcode&state={mock_oauth_state}",
                follow_redirects=False,
            )

        assert response.status_code == 500
        assert "Failed to retrieve access token" in response.text

    def test_callback_with_user_fetch_failure(self, client, app, mock_env_vars, mock_oauth_state):
        """Failed user fetch should return 500"""
        with respx.mock:
            respx.post("http://test-hub:8081/hub/api/oauth2/token").mock(
                return_value=Response(200, json={"access_token": "test-token"})
            )
            respx.get("http://test-hub:8081/hub/api/user").mock(
                return_value=Response(500, json={"error": "server_error"})
            )

            set_session(client, app, {"oauth_state": mock_oauth_state})

            response = client.get(
                f"/services/usage/oauth_callback?code=auth123&state={mock_oauth_state}",
                follow_redirects=False,
            )

        assert response.status_code == 500
        assert "Failed to retrieve user data" in response.text

    def test_callback_stores_user_in_session(self, client, app, mock_env_vars, mock_oauth_state):
        """Successful auth should store complete user data in session"""
        with respx.mock:
            respx.post("http://test-hub:8081/hub/api/oauth2/token").mock(
                return_value=Response(200, json={"access_token": "test-token"})
            )

            user_data = {
                "name": "testuser",
                "admin": False,
                "groups": ["users", "team-a"],
                "server": "/user/testuser/",
            }
            respx.get("http://test-hub:8081/hub/api/user").mock(
                return_value=Response(200, json=user_data)
            )

            set_session(client, app, {"oauth_state": mock_oauth_state})

            response = client.get(
                f"/services/usage/oauth_callback?code=auth123&state={mock_oauth_state}",
                follow_redirects=False,
            )

        assert response.status_code == 307

        session = get_session(client, app)
        assert session["user"] == user_data

    def test_callback_clears_oauth_state_from_session(
        self, client, app, mock_env_vars, mock_oauth_state
    ):
        """OAuth state should be removed after successful auth"""
        with respx.mock:
            respx.post("http://test-hub:8081/hub/api/oauth2/token").mock(
                return_value=Response(200, json={"access_token": "test-token"})
            )
            respx.get("http://test-hub:8081/hub/api/user").mock(
                return_value=Response(200, json={"name": "testuser"})
            )

            set_session(client, app, {"oauth_state": mock_oauth_state})
            session = get_session(client, app)
            assert "oauth_state" in session

            response = client.get(
                f"/services/usage/oauth_callback?code=auth123&state={mock_oauth_state}",
                follow_redirects=False,
            )

        assert response.status_code == 307

        session = get_session(client, app)
        assert "oauth_state" not in session


class TestServicePrefixConfiguration:
    """Test that SERVICE_PREFIX is properly used in routes"""

    def test_home_route_uses_service_prefix(self, client, mock_env_vars):
        response = client.get("/services/usage/", follow_redirects=False)
        assert response.status_code in [200, 307]

    def test_callback_route_uses_service_prefix(self, client, mock_env_vars):
        response = client.get(
            "/services/usage/oauth_callback?code=test&state=test",
            follow_redirects=False,
        )
        assert response.status_code == 400

    def test_oauth_redirect_includes_correct_redirect_uri(self, client, mock_env_vars):
        response = client.get("/services/usage/", follow_redirects=False)

        assert response.status_code == 307
        location = response.headers["Location"]

        parsed = urlparse(location)
        query_params = parse_qs(parsed.query)

        assert "redirect_uri" in query_params
        redirect_uri = query_params["redirect_uri"][0]
        assert "/services/usage/oauth_callback" in redirect_uri
