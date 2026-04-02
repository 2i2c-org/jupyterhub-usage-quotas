"""Tests for FastAPI routes"""

from tests.services.conftest import get_session, set_session


class TestHomeRoute:
    """Test the home route (GET /)"""

    def test_home_redirects_to_oauth_when_not_authenticated(
        self, client, mock_env_vars
    ):
        """Unauthenticated user should get JS redirect to JupyterHub OAuth"""
        response = client.get("/services/usage-quota", follow_redirects=False)

        assert response.status_code == 200
        assert "window.top.location.href" in response.text

        # Extract the redirect URL from the JS snippet
        assert "oauth2/authorize" in response.text
        assert "state=" in response.text
        assert "redirect_uri=" in response.text

    def test_home_displays_usage_when_authenticated(
        self, client, app, mock_env_vars, mock_prometheus_client
    ):
        """Authenticated user should see usage data"""
        set_session(client, app, {"token": "test-token"})

        response = client.get("/services/usage-quota")

        assert response.status_code == 200
        assert "Home storage" in response.text
        assert "50.0%" in response.text
        assert "5.0 GiB used" in response.text
        assert "10.0 GiB quota" in response.text

    def test_home_displays_error_when_prometheus_fails(
        self, client, app, mock_env_vars, mock_prometheus_client_with_error
    ):
        """User should see error message when Prometheus is unavailable"""
        set_session(client, app, {"token": "test-token"})

        response = client.get("/services/usage-quota")

        assert response.status_code == 200
        assert "Unable to reach Prometheus" in response.text
        assert "error-message" in response.text

    def test_home_displays_no_data_error(
        self, client, app, mock_env_vars, mock_prometheus_client_no_data
    ):
        """User should see error when no quota data exists"""
        set_session(client, app, {"token": "test-token"})

        response = client.get("/services/usage-quota")

        assert response.status_code == 200
        assert "No storage data found" in response.text

    def test_home_with_high_usage_displays_warning(
        self, client, app, mock_env_vars, mock_prometheus_client_high_usage
    ):
        """User with high usage should see warning styling"""
        set_session(client, app, {"token": "test-token"})

        response = client.get("/services/usage-quota")

        assert response.status_code == 200
        assert "95.0%" in response.text
        assert "#ef4444" in response.text


class TestOAuthCallbackRoute:
    """Test the OAuth callback route"""

    def test_callback_with_valid_state_and_code(
        self, client, app, mock_env_vars, mock_oauth_state, mock_hub_auth
    ):
        """Valid OAuth callback should authenticate user and redirect"""
        # Override generate_state to return the expected state
        mock_hub_auth.generate_state = lambda next_url="/": mock_oauth_state

        set_session(client, app, {"oauth_state": mock_oauth_state})

        response = client.get(
            f"/services/usage-quota/oauth_callback?code=auth123&state={mock_oauth_state}",
            follow_redirects=False,
        )

        assert response.status_code == 307
        # Redirects to /hub/usage (embedded view with JupyterHub nav bar)
        assert response.headers["Location"] == "http://test-hub:8000/hub/usage"

        session = get_session(client, app)
        assert "token" in session
        assert session["token"] == "test-token"
        assert "oauth_state" not in session

    def test_callback_with_invalid_state_returns_400(self, client, app, mock_env_vars):
        """Invalid state should return 400 error (CSRF protection)"""
        set_session(client, app, {"oauth_state": "expected_state"})

        response = client.get(
            "/services/usage-quota/oauth_callback?code=auth123&state=wrong_state",
            follow_redirects=False,
        )

        assert response.status_code == 400
        assert "OAuth state mismatch" in response.text

    def test_callback_with_missing_state_returns_400(self, client, mock_env_vars):
        """Missing state should return 400 error"""
        response = client.get(
            "/services/usage-quota/oauth_callback?code=auth123&state=somestate",
            follow_redirects=False,
        )

        assert response.status_code == 400
        assert "OAuth state mismatch" in response.text

    def test_callback_with_token_exchange_failure(
        self, client, app, mock_env_vars, mock_oauth_state, mock_hub_auth
    ):
        """Failed token exchange should return 500"""

        # Override token_for_code to return None (failure)
        async def mock_token_for_code_failure(code, sync=False):
            return None

        mock_hub_auth.token_for_code = mock_token_for_code_failure
        mock_hub_auth.generate_state = lambda next_url="/": mock_oauth_state

        set_session(client, app, {"oauth_state": mock_oauth_state})

        response = client.get(
            f"/services/usage-quota/oauth_callback?code=badcode&state={mock_oauth_state}",
            follow_redirects=False,
        )

        assert response.status_code == 500
        assert "Failed to retrieve access token" in response.text

    def test_callback_stores_token_not_user(
        self, client, app, mock_env_vars, mock_oauth_state, mock_hub_auth
    ):
        """OAuth callback should store token in session (not user data)"""
        mock_hub_auth.generate_state = lambda next_url="/": mock_oauth_state

        set_session(client, app, {"oauth_state": mock_oauth_state})

        response = client.get(
            f"/services/usage-quota/oauth_callback?code=auth123&state={mock_oauth_state}",
            follow_redirects=False,
        )

        assert response.status_code == 307
        session = get_session(client, app)
        assert "token" in session
        assert session["token"] == "test-token"
        # User data is NOT stored in callback, it's fetched later when needed
        assert "user" not in session

    def test_callback_successful_with_token(
        self, client, app, mock_env_vars, mock_oauth_state, mock_hub_auth
    ):
        """Successful auth should store token in session"""
        mock_hub_auth.generate_state = lambda next_url="/": mock_oauth_state

        set_session(client, app, {"oauth_state": mock_oauth_state})

        response = client.get(
            f"/services/usage-quota/oauth_callback?code=auth123&state={mock_oauth_state}",
            follow_redirects=False,
        )

        assert response.status_code == 307
        # Redirects to /hub/usage (embedded view with JupyterHub nav bar)
        assert response.headers["Location"] == "http://test-hub:8000/hub/usage"

        session = get_session(client, app)
        assert "token" in session
        assert session["token"] == "test-token"

    def test_callback_clears_oauth_state_from_session(
        self, client, app, mock_env_vars, mock_oauth_state, mock_hub_auth
    ):
        """OAuth state should be removed after successful auth"""
        mock_hub_auth.generate_state = lambda next_url="/": mock_oauth_state

        set_session(client, app, {"oauth_state": mock_oauth_state})
        session = get_session(client, app)
        assert "oauth_state" in session

        response = client.get(
            f"/services/usage-quota/oauth_callback?code=auth123&state={mock_oauth_state}",
            follow_redirects=False,
        )

        assert response.status_code == 307

        session = get_session(client, app)
        assert "oauth_state" not in session


class TestServicePrefixConfiguration:
    """Test that SERVICE_PREFIX is properly used in routes"""

    def test_home_route_uses_service_prefix(self, client, mock_env_vars):
        response = client.get("/services/usage-quota", follow_redirects=False)
        assert response.status_code in [200, 307]

    def test_callback_route_uses_service_prefix(self, client, mock_env_vars):
        response = client.get(
            "/services/usage-quota/oauth_callback?code=test&state=test",
            follow_redirects=False,
        )
        assert response.status_code == 400

    def test_oauth_callback_includes_correct_redirect_uri(self, client, mock_env_vars):
        response = client.get("/services/usage-quota", follow_redirects=False)

        assert response.status_code == 200
        assert "window.top.location.href" in response.text

        # The JS redirect should include the correct redirect_uri (URL-encoded)
        assert "redirect_uri=" in response.text
        # Check for URL-encoded version: /services/usage-quota/oauth_callback -> %2Fservices%2Fusage%2Foauth_callback
        assert "oauth_callback" in response.text
