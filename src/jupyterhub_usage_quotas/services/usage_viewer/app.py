"""Usage Viewer Service - Combined Application and Tornado routes."""

import json
import logging

from jinja2 import Environment, FileSystemLoader
from jupyterhub.services.auth import (
    HubOAuth,
    HubOAuthCallbackHandler,
    HubOAuthenticated,
)
from tornado import web
from tornado.httpserver import HTTPServer
from tornado.httputil import url_concat
from tornado.ioloop import IOLoop

from jupyterhub_usage_quotas import get_template_path
from jupyterhub_usage_quotas.config import UsageViewerConfig
from jupyterhub_usage_quotas.services.usage_viewer.quota_client import QuotaClient


class UsageHandler(HubOAuthenticated, web.RequestHandler):
    """Tornado request handler that renders usage for authenticated users."""

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
        jinja_env = self.settings["jinja_env"]
        user = self.get_current_user()
        enable_storage = self.settings["enable_component"]["home_storage"]
        enable_compute = self.settings["enable_component"]["compute"]
        if not enable_storage and not enable_compute:
            self.set_status(404)
            template = jinja_env.get_template("usage-viewer-404.html")
            return self.finish(template.render())
        storage_data, compute_data = None, None
        if enable_storage:
            storage_data = await self.settings["quota_client"].get_user_storage_usage(
                user["name"]
            )
        if enable_compute:
            compute_data = await self.settings["quota_client"].get_user_compute_usage(
                user["name"]
            )
        template = jinja_env.get_template("usage.html")
        self.finish(
            template.render(
                storage_data=storage_data,
                compute_data=compute_data,
                enable_storage=enable_storage,
                enable_compute=enable_compute,
            )
        )


def make_app(
    quota_client: QuotaClient,
    config: UsageViewerConfig,
) -> web.Application:
    """Create and configure the Tornado application.

    Args:
        quota_client: QuotaClient instance for querying usage data
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
        enable_component=config.enable_component,
        quota_client=quota_client,
        jinja_env=jinja_env,
    )


class UsageViewer(UsageViewerConfig):
    """Application for running the usage quota viewer service."""

    name = "jupyterhub-usage-viewer"
    description = "Web service for viewing usage quotas"

    aliases = {
        "port": "UsageViewer.service_port",
        "host": "UsageViewer.service_host",
        "prometheus-url": "UsageViewer.prometheus_url",
        "prometheus-usage-quota-metrics": "UsageViewer.prometheus_usage_quota_metrics",
        "hub_api_url": "UsageViewer.hub_api_url",
        "hub_api_token": "UsageViewer.hub_api_token",
        "hub-namespace": "UsageViewer.hub_namespace",
        "dev-mode": "UsageViewer.dev_mode",
        "service-prefix": "UsageViewer.service_prefix",
        "public-hub-url": "UsageViewer.public_hub_url",
        "session-secret-key": "UsageViewer.session_secret_key",
        "config-file": "UsageViewer.config_file",
    }

    def initialize(self, argv=None):
        """Initialize the service."""
        super().initialize(argv)
        self.log.setLevel(logging.INFO)
        for handler in self.log.handlers:
            handler.setLevel(logging.INFO)
        if self.config_file:
            self.load_config_file(self.config_file)
            self.log.info(f"Loaded config file {self.config_file}")

        self.quota_client = QuotaClient(
            prometheus_usage_quota_metrics=self.prometheus_usage_quota_metrics,
            prometheus_url=self.prometheus_url,
            prometheus_auth=self.prometheus_auth,
            namespace=self.hub_namespace,
            escape_scheme=self.escape_username_scheme,
            dev_mode=self.dev_mode,
        )

        self.log.info("Initialized Usage Viewer service")
        self.log.info(f"Prometheus URL: {self.prometheus_url}")
        self.log.info(f"Hub Namespace: {self.hub_namespace or '(empty)'}")
        if self.dev_mode:
            self.log.warning(
                "Development mode ENABLED - may use mock data for usage viewer service"
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
        app = make_app(self.quota_client, config=self)
        server = HTTPServer(app)
        server.listen(self.service_port, self.service_host)
        IOLoop.current().start()


def main():
    """Entry point for the usage viewer service."""
    UsageViewer.launch_instance()


if __name__ == "__main__":
    main()
