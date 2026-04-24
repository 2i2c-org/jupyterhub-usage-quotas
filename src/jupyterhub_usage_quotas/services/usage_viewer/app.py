"""Usage Viewer Service - Combined Application and Tornado routes."""

import json
import logging

from jinja2 import Environment, FileSystemLoader
from jupyterhub.services.auth import HubOAuth, HubOAuthCallbackHandler, HubOAuthenticated
from tornado import web
from tornado.httpserver import HTTPServer
from tornado.httputil import url_concat
from tornado.ioloop import IOLoop

from jupyterhub_usage_quotas import get_template_path
from jupyterhub_usage_quotas.config import UsageViewerConfig
from jupyterhub_usage_quotas.services.usage_viewer.storage_quota_client import (
    StorageQuotaClient,
)

logger = logging.getLogger(__name__)


class UsageHandler(HubOAuthenticated, web.RequestHandler):
    """Tornado request handler that renders storage usage for authenticated users."""

    async def prepare(self):
        """Send a JS redirect for unauthenticated users before the handler runs.

        A plain HTTP redirect would be blocked by CSP frame-ancestors when this
        service is embedded in a JupyterHub iframe, so we use a JS top-frame redirect.
        When embedded in an iframe, the Referer header contains the parent page URL,
        so we use it as next_url to return the user there after login rather than
        to the service's own path.
        """
        if not self.get_current_user():
            next_url = self.request.headers.get("Referer") or self.request.uri
            state = self.hub_auth.set_state_cookie(self, next_url=next_url)
            login_url = url_concat(self.hub_auth.login_url, {"state": state})
            self.finish(
                f"<script>window.top.location.href={json.dumps(login_url)};</script>"
            )

    async def get(self):
        """Render the storage usage page for the authenticated user."""
        user = self.get_current_user()
        usage_data = await self.settings["storage_client"].get_user_storage_usage(
            user["name"]
        )
        jinja_env = self.settings["jinja_env"]
        template = jinja_env.get_template("usage.html")
        self.finish(template.render(usage_data=usage_data))


def make_app(
    storage_client: StorageQuotaClient,
    config: UsageViewerConfig,
) -> web.Application:
    """Create and configure the Tornado application.

    Args:
        storage_client: StorageQuotaClient instance for querying storage data
        config: UsageViewerConfig instance containing all configuration

    Returns:
        Configured Tornado application
    """
    prefix = config.service_prefix.rstrip("/")
    jinja_env = Environment(
        loader=FileSystemLoader(get_template_path()), autoescape=True
    )
    HubOAuth.instance(cache_max_age=60)
    return web.Application(
        [
            (prefix + r"/?", UsageHandler),
            (prefix + r"/oauth_callback", HubOAuthCallbackHandler),
        ],
        cookie_secret=config.session_secret_key,
        storage_client=storage_client,
        jinja_env=jinja_env,
    )


class UsageViewer(UsageViewerConfig):
    """Application for running the usage quota viewer service."""

    name = "jupyterhub-usage-viewer"
    description = "Web service for viewing storage usage quotas"

    aliases = {
        "port": "UsageViewer.service_port",
        "host": "UsageViewer.service_host",
        "prometheus-url": "UsageViewer.prometheus_url",
        "hub-namespace": "UsageViewer.hub_namespace",
        "prometheus-storage-quota-metric": "UsageViewer.prometheus_storage_quota_metric",
        "prometheus-storage-usage-metric": "UsageViewer.prometheus_storage_usage_metric",
        "dev-mode": "UsageViewer.dev_mode",
        "service-prefix": "UsageViewer.service_prefix",
        "public-hub-url": "UsageViewer.public_hub_url",
        "session-secret-key": "UsageViewer.session_secret_key",
    }

    def initialize(self, argv=None):
        """Initialize the service."""
        super().initialize(argv)
        if self.config_file:
            self.load_config_file(self.config_file)

        self.storage_client = StorageQuotaClient(
            prometheus_url=self.prometheus_url,
            prometheus_auth=self.prometheus_auth,
            namespace=self.hub_namespace,
            safe_scheme=self.escape_username_safe_scheme,
            dev_mode=self.dev_mode,
            quota_metric=self.prometheus_storage_quota_metric,
            usage_metric=self.prometheus_storage_usage_metric,
        )

        self.log.info("Initialized Usage Viewer service")
        self.log.info(f"Prometheus URL: {self.prometheus_url}")
        self.log.info(f"Hub Namespace: {self.hub_namespace or '(empty)'}")
        if self.dev_mode:
            self.log.warning(
                "Development mode ENABLED - may use mock data for storage quotas"
            )
        else:
            self.log.info(
                "Development mode disabled - querying Prometheus for real data"
            )

    def start(self):
        """Start the Tornado service."""
        self.log.info(
            f"Starting Usage Viewer service on {self.service_host}:{self.service_port}"
        )
        app = make_app(self.storage_client, config=self)
        server = HTTPServer(app)
        server.listen(self.service_port, self.service_host)
        IOLoop.current().start()


def main():
    """Entry point for the usage viewer service."""
    UsageViewer.launch_instance()


if __name__ == "__main__":
    main()
