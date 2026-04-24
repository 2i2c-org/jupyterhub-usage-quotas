"""Tests for Tornado routes"""

from tests.services.fixtures.tornado_app import TEST_USER, UsageViewerTestCase
from tests.services.fixtures.usage_data import (
    USAGE_50_PCT,
    USAGE_95_PCT,
    USAGE_NO_DATA,
    USAGE_PROMETHEUS_ERROR,
)


class TestHomeRoute(UsageViewerTestCase):
    """Test the home route (GET /)"""

    def test_home_redirects_to_oauth_when_not_authenticated(self):
        """Unauthenticated user should get JS redirect to JupyterHub OAuth"""
        response = self.fetch("/services/usage-quota/", follow_redirects=False)

        assert response.code == 200
        body = response.body.decode()
        assert "window.top.location.href" in body
        assert "oauth2/authorize" in body
        assert "redirect_uri=" in body

    def test_home_displays_usage_when_authenticated(self):
        """Authenticated user should see usage data"""
        self.mock_storage.return_value = USAGE_50_PCT
        self.mock_hub_auth.get_user.return_value = TEST_USER

        response = self.fetch("/services/usage-quota")
        assert response.code == 200
        body = response.body.decode()
        assert "Home storage" in body
        assert "50.0%" in body
        assert "5.0 GiB used" in body
        assert "10.0 GiB quota" in body

    def test_home_displays_error_when_prometheus_fails(self):
        """User should see error message when Prometheus is unavailable"""
        self.mock_storage.return_value = USAGE_PROMETHEUS_ERROR
        self.mock_hub_auth.get_user.return_value = TEST_USER

        response = self.fetch("/services/usage-quota")
        assert response.code == 200
        body = response.body.decode()
        assert "Unable to reach Prometheus" in body
        assert "error-message" in body

    def test_home_displays_no_data_error(self):
        """User should see error when no quota data exists"""
        self.mock_storage.return_value = USAGE_NO_DATA
        self.mock_hub_auth.get_user.return_value = TEST_USER

        response = self.fetch("/services/usage-quota")
        assert response.code == 200
        assert b"No storage data found" in response.body

    def test_home_with_high_usage_displays_warning(self):
        """User with high usage should see warning styling"""
        self.mock_storage.return_value = USAGE_95_PCT
        self.mock_hub_auth.get_user.return_value = TEST_USER

        response = self.fetch("/services/usage-quota")
        assert response.code == 200
        body = response.body.decode()
        assert "95.0%" in body
        assert "#ef4444" in body


class TestOAuthCallbackRoute(UsageViewerTestCase):
    """Test that the OAuth callback route is mounted"""

    def test_callback_route_is_mounted(self):
        """OAuth callback endpoint should be mounted (not 404)"""
        # Without proper OAuth params, HubOAuthCallbackHandler returns an error,
        # but the route must exist — any response other than 404 confirms it.
        response = self.fetch(
            "/services/usage-quota/oauth_callback?code=test&state=test",
            follow_redirects=False,
        )
        assert response.code != 404
