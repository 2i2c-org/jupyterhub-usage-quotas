"""Integration tests for end-to-end user flows"""

from unittest.mock import MagicMock

from tests.services.fixtures.tornado_app import TEST_USER, UsageViewerTestCase
from tests.services.fixtures.usage_data import STORAGE_USAGE_50_PCT


class TestEndToEndUserFlow(UsageViewerTestCase):
    """Test complete user flows from start to finish"""

    def test_complete_unauthenticated_to_viewing_usage(self):
        """Verify that an unauthenticated user is redirected to log in and, after authentication, can view their usage information."""
        self.mock_storage.return_value = STORAGE_USAGE_50_PCT

        # Step 1: unauthenticated user gets 302 redirect to OAuth
        response = self.fetch("/services/usage-quota/", follow_redirects=False)
        assert response.code == 302
        location = response.headers.get("Location", "")
        assert "oauth2/authorize" in location

        # Step 2: simulate completed OAuth — authenticate the mock
        self.mock_hub_auth.get_user = MagicMock(return_value=TEST_USER)

        # Step 3: authenticated request renders usage page
        response = self.fetch("/services/usage-quota/", follow_redirects=False)
        assert response.code == 200
        body = response.body.decode()
        assert "Home storage" in body
        assert "50.0%" in body
        assert "5.0 GiB used" in body
