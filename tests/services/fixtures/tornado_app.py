"""Shared Tornado test application infrastructure for service tests"""

from unittest.mock import AsyncMock, MagicMock, patch

from tornado.testing import AsyncHTTPTestCase

from jupyterhub_usage_quotas.config import UsageViewerConfig
from jupyterhub_usage_quotas.services.usage_viewer.app import make_app
from jupyterhub_usage_quotas.services.usage_viewer.quota_client import QuotaClient

MOCK_LOGIN_URL = (
    "http://localhost:8000/hub/api/oauth2/authorize"
    "?client_id=service-usage-quota"
    "&redirect_uri=http://localhost:8000/services/usage-quota/oauth_callback"
    "&response_type=code"
    "&state=test-state-123"
)

TEST_USER = {"name": "testuser", "admin": False, "groups": ["users"]}

STORAGE_MODULE = (
    "jupyterhub_usage_quotas.services.usage_viewer"
    ".quota_client.QuotaClient.get_user_storage_usage"
)

PROMETHEUS_METRICS = {
    "home_storage": {
        "usage": "dirsize_total_size_bytes",
        "quota": "dirsize_hard_limit_bytes",
    },
    "compute": {
        "usage": "jupyterhub_memory_usage_gibibyte_hours",
        "quota": "jupyterhub_memory_limit_gibibyte_hours",
    },
}


class UsageViewerTestCase(AsyncHTTPTestCase):
    """Base test case providing the Tornado application with a mocked HubAuth."""

    def setUp(self):
        mock_hub_auth = MagicMock()
        mock_hub_auth.login_url = MOCK_LOGIN_URL
        mock_hub_auth.get_user = MagicMock(return_value=None)
        self.mock_hub_auth = mock_hub_auth

        self._hub_auth_patcher = patch(
            "jupyterhub.services.auth.HubOAuth.instance",
            return_value=mock_hub_auth,
        )
        self._hub_auth_patcher.start()

        self._storage_patcher = patch(STORAGE_MODULE, new_callable=AsyncMock)
        self.mock_storage = self._storage_patcher.start()

        super().setUp()

    def tearDown(self):
        super().tearDown()
        self._hub_auth_patcher.stop()
        self._storage_patcher.stop()

    def get_app(self):
        client = QuotaClient(
            prometheus_url="http://prometheus:9090",
            prometheus_usage_quota_metrics=PROMETHEUS_METRICS,
            namespace="prod",
            dev_mode=False,
        )
        config = UsageViewerConfig()
        config.service_prefix = "/services/usage-quota/"
        config.public_hub_url = "http://test-hub:8000"
        config.session_secret_key = "0" * 64
        return make_app(client, config)
