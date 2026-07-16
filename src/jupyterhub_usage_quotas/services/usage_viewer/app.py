"""Usage Viewer Service - Combined Application and Tornado routes."""

import logging
import os
import sys
import typing

import jsonschema
from jinja2 import Environment, FileSystemLoader
from jupyterhub.services.auth import (
    HubOAuth,
    HubOAuthCallbackHandler,
    HubOAuthenticated,
)
from markupsafe import Markup
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    generate_latest,
)
from tornado import web
from tornado.httpserver import HTTPServer
from tornado.httputil import url_concat
from tornado.ioloop import IOLoop
from traitlets import Bool, Dict, Integer, List, TraitError, Unicode, default, validate
from traitlets.config import Application

from jupyterhub_usage_quotas import get_template_path
from jupyterhub_usage_quotas.config import UsageViewerConfig
from jupyterhub_usage_quotas.services.usage_viewer.quota_client import QuotaClient
from jupyterhub_usage_quotas.services.usage_viewer.utils import get_displayable_services

Schema = typing.Dict[str, typing.Any]

# Prometheus Usage Quota Metrics schema
prometheus_usage_quota_metrics_schema: Schema = {
    "type": "object",
    "properties": {
        "home_storage": {
            "type": "object",
            "properties": {
                "usage": {"type": "string"},
                "quota": {"type": "string"},
            },
            "required": ["usage", "quota"],
            "additionalProperties": False,
        },
        "compute": {
            "type": "object",
            "properties": {
                "usage": {"type": "string"},
                "quota": {"type": "string"},
            },
            "required": ["usage", "quota"],
            "additionalProperties": False,
        },
    },
    "additionalProperties": False,
}

service_registry = CollectorRegistry()

SERVICE_ERROR_TOTAL = Counter(
    "jupyterhub_usage_quotas_service_error_total",
    "Number of dashboard service errors from the usage quota system",
    ["namespace", "username"],
    registry=service_registry,
)


class BaseHandler(HubOAuthenticated, web.RequestHandler):
    """Base class handler to authenticate users with service"""

    async def prepare(self):
        """Redirect unauthenticated users to the JupyterHub login page."""
        if not self.get_current_user():
            next_url = self.request.uri
            state = self.hub_auth.set_state_cookie(self, next_url=next_url)
            login_url = url_concat(self.hub_auth.login_url, {"state": state})
            self.redirect(login_url)


class UsageHandler(BaseHandler):
    """Tornado request handler that renders usage for authenticated users."""

    async def _hub_context(self):
        """Return template context variables needed by JupyterHub's page.html."""
        user = self.get_current_user()
        if user["admin"]:
            parsed_scopes = frozenset(user["scopes"] + ["admin-ui"])
        else:
            parsed_scopes = frozenset(user["scopes"])
        return dict(
            user=user,
            base_url=self.settings["public_hub_url"],
            logout_url=self.settings["logout_url"],
            services=await get_displayable_services(self.settings, self.hub_auth),
            parsed_scopes=parsed_scopes,
            version_hash=None,
            no_spawner_check=True,
        )

    async def get(self):
        """Render the storage usage page for the authenticated user."""
        jinja_env = self.settings["jinja_env"]
        user = self.get_current_user()
        enable_storage = self.settings["enable_home_storage"]
        enable_compute = self.settings["enable_compute"]
        if not enable_storage and not enable_compute:
            SERVICE_ERROR_TOTAL.labels(
                username=user["name"], namespace=self.settings["namespace"]
            ).inc()
            status_code = 404
            self.set_status(status_code)
            ns = dict(status_code=status_code, status_message="Not Found")
            ns.update(await self._hub_context())
            template = jinja_env.get_template(f"{status_code}.html")
            return self.finish(template.render(ns))
        storage_data, compute_data = None, None
        if enable_storage:
            storage_data = await self.settings["quota_client"].get_user_storage_usage(
                user["name"]
            )
            if "error" in set(storage_data.keys()):
                SERVICE_ERROR_TOTAL.labels(
                    username=user["name"], namespace=self.settings["namespace"]
                ).inc()
                self.set_status(424)
        if enable_compute:
            compute_data = await self.settings["quota_client"].get_user_compute_usage(
                user["name"]
            )
            if "error" in set().union(*(c.keys() for c in compute_data)):
                SERVICE_ERROR_TOTAL.labels(
                    username=user["name"], namespace=self.settings["namespace"]
                ).inc()
                self.set_status(424)
        template = jinja_env.get_template("usage.html")
        self.finish(
            template.render(
                storage_data=storage_data,
                compute_data=compute_data,
                enable_storage=enable_storage,
                enable_compute=enable_compute,
                footer_note=Markup(self.settings["footer_note"]),
                **(await self._hub_context()),
            )
        )


class MetricsHandler(BaseHandler):
    """Handler for service metrics endpoint."""

    def get(self):
        user = self.get_current_user()
        if not user["admin"]:
            self.set_status(403)
        else:
            self.set_header("Content-Type", CONTENT_TYPE_LATEST)
            self.write(generate_latest(service_registry))


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
    public_hub_url = config.public_hub_url  # already rstripped of trailing /
    config.hub_template_paths.append(
        get_template_path()
    )  # append usage-quota templates to default hub templates list
    jinja_env = Environment(
        loader=FileSystemLoader(config.hub_template_paths),
        autoescape=True,
    )
    jinja_env.globals["static_url"] = (
        lambda path, **_: f"{public_hub_url}/static/{path}"
    )

    HubOAuth.instance(cache_max_age=60)
    return web.Application(
        [
            (prefix + r"/?", UsageHandler),
            (prefix + r"/oauth_callback", HubOAuthCallbackHandler),
            (prefix + r"/metrics", MetricsHandler),
        ],
        cookie_secret=config.session_secret_key,
        enable_home_storage=config.enable_home_storage,
        enable_compute=config.enable_compute,
        namespace=config.hub_namespace,
        quota_client=quota_client,
        jinja_env=jinja_env,
        public_hub_url=public_hub_url,
        logout_url=public_hub_url + "logout",
        footer_note=config.footer_note,
    )


class UsageViewer(Application):
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
        "config-files": "UsageViewer.config_files",
    }

    config_files = List(
        Unicode(),
        default_value=[],
        help="List of config files to load. If not set, then no config file is loaded.",
    ).tag(config=True)

    @validate("config_files")
    def _validate_config_file(self, proposal):
        for item in proposal.value:
            if item and not os.path.isfile(item):
                raise TraitError(f"Failed to find specified config file: {item}")
        return proposal.value

    prometheus_url = Unicode(
        "http://127.0.0.1:9090",
        help="The url of the Prometheus server, usually of the form 'http://<k8s-service-name>.<k8s-namespace>.svc.cluster.local' in a Kubernetes cluster. Defaults to 'http://127.0.0.1:9090' for local development.",
    ).tag(config=True)

    @default("prometheus_url")
    def _prometheus_url_default(self):
        return os.environ.get(
            "JUPYTERHUB_USAGE_QUOTAS_PROMETHEUS_URL", "http://127.0.0.1:9090"
        )

    prometheus_auth = Dict(
        per_key_traits={"username": Unicode(), "password": Unicode()},
        help="""
        Username and password credentials for authenticating with Prometheus.
        Can be set via JUPYTERHUB_USAGE_QUOTAS_PROMETHEUS_USERNAME and
        JUPYTERHUB_USAGE_QUOTAS_PROMETHEUS_PASSWORD environment variables.
        For example:
            c.UsageConfig.prometheus_auth = {
                "username": "username",
                "password": "password",
            }
        """,
    ).tag(config=True)

    @default("prometheus_auth")
    def _prometheus_auth_default(self):
        username = os.environ.get("JUPYTERHUB_USAGE_QUOTAS_PROMETHEUS_USERNAME", "")
        password = os.environ.get("JUPYTERHUB_USAGE_QUOTAS_PROMETHEUS_PASSWORD", "")
        if username and password:
            return {"username": username, "password": password}
        if username or password:
            raise TraitError(
                "Both JUPYTERHUB_USAGE_QUOTAS_PROMETHEUS_USERNAME and "
                "JUPYTERHUB_USAGE_QUOTAS_PROMETHEUS_PASSWORD must be set together."
            )
        return {}

    @validate("prometheus_auth")
    def _validate_prometheus_auth(self, proposal):
        auth = proposal["value"]
        if not auth:
            return auth
        required = set(self.traits()["prometheus_auth"]._per_key_traits.keys())
        missing = required - auth.keys()
        if missing:
            expected = {k: "..." for k in sorted(required)}
            raise TraitError(
                f"prometheus_auth is missing required keys: {sorted(missing)}. "
                f"Expected: {expected}"
            )
        return auth

    hub_url = Unicode(
        help="JupyterHub URL, e.g. http://localhost:8000 for local development."
    ).tag(config=True)

    @default("hub_url")
    def _hub_url_default(self):
        return f"http://{os.environ.get('HUB_SERVICE_HOST')}:{os.environ.get('HUB_SERVICE_PORT')}"

    hub_namespace = Unicode(
        help="Kubernetes namespace of the JupyterHub deployment, used to filter Prometheus usage metrics in multi-tenant environments. Leave empty for single-tenant or development. Can be set via JUPYTERHUB_USAGE_QUOTAS_HUB_NAMESPACE environment variable.",
    ).tag(config=True)

    @default("hub_namespace")
    def _hub_namespace_default(self):
        return os.environ.get("JUPYTERHUB_USAGE_QUOTAS_HUB_NAMESPACE", "")

    escape_username_scheme = Dict(
        per_key_traits={
            "directory": Unicode(),
            "pod": Unicode(),
            "max_length": Integer(),
        },
        help="""
        Kubespawner slug scheme for naming directories and pod names with escaped usernames. E.g
            - modern safe slugs for k8s pods and legacy slug for directory names (default): {"directory": "legacy", pod": "safe", max_length: 48},
        """,
    ).tag(config=True)

    @default("escape_username_scheme")
    def _escape_username_scheme_default(self):
        return {"directory": "legacy", "pod": "safe", "max_length": 48}

    enable_home_storage = Bool(
        help="Enable home storage component on the usage quotas dashboard",
        default_value=True,
    ).tag(config=True)

    enable_compute = Bool(
        help="Enable compute component on the usage quotas dashboard",
        default_value=True,
    ).tag(config=True)

    footer_note = Unicode(
        "Contact your JupyterHub Admin if you need additional quota.",
        help="HTML content shown in the footer of the usage dashboard page. Set to empty string to hide the footer.",
    ).tag(config=True)

    prometheus_usage_quota_metrics = Dict(
        help="""
        Prometheus metrics for querying storage and/or compute usage and quotas. Defaults to:

        c.UsageViewerConfig.prometheus_usage_quota_metrics = {
            "home_storage": {
                "usage": "dirsize_total_size_bytes",
                "quota": "dirsize_hard_limit_bytes"
            },
            "compute": {
                "usage": "jupyterhub_memory_usage_gibibyte_hours",
                "quota": "jupyterhub_memory_limit_gibibyte_hours"
            }
        }
        """,
        default_value={
            "home_storage": {
                "usage": "dirsize_total_size_bytes",
                "quota": "dirsize_hard_limit_bytes",
            },
            "compute": {
                "usage": "jupyterhub_memory_usage_gibibyte_hours",
                "quota": "jupyterhub_memory_limit_gibibyte_hours",
            },
        },
    ).tag(config=True)

    @validate("prometheus_usage_quota_metrics")
    def _validate_prometheus_usage_quota_metrics(self, proposal):
        resources = proposal["value"]
        allowed = set(["home_storage", "compute"])
        extra = set(resources.keys()) - allowed
        if extra:
            raise TraitError(f"Unexpected keys: {extra}")
        try:
            jsonschema.validate(resources, prometheus_usage_quota_metrics_schema)
        except jsonschema.ValidationError as e:
            raise TraitError(e)
        return resources

    dev_mode = Bool(
        False,
        help="""
        Enable development mode with mock data.

        When True, the service returns mock storage usage data instead of querying
        Prometheus. This is useful for local development without a real Prometheus
        instance.

        Mock data is only used when ALL three conditions are met:
        - dev_mode is True, AND
        - prometheus_url is the default (http://127.0.0.1:9090), AND
        - hub_namespace is empty

        If either prometheus_url or hub_namespace is configured, the service
        will query Prometheus even when dev_mode is True.

        Default: False (production mode - always query Prometheus)
        """,
    ).tag(config=True)

    service_port = Integer(
        9000,
        help="Port to bind the usage viewer service to",
    ).tag(config=True)

    service_host = Unicode(
        "0.0.0.0",
        help="Host to bind the usage viewer service to",
    ).tag(config=True)

    service_prefix = Unicode(
        help="URL prefix for the service. Automatically set by JupyterHub when running as a managed service. Defaults to /services/usage-quota.",
    ).tag(config=True)

    @default("service_prefix")
    def _service_prefix_default(self):
        # Try environment variable first (set by JupyterHub)
        prefix = os.environ.get("JUPYTERHUB_SERVICE_PREFIX")
        return prefix or "/services/usage-quota/"

    public_hub_url = Unicode(
        help="Public URL of the JupyterHub instance. Required. Automatically set by JupyterHub via JUPYTERHUB_PUBLIC_HUB_URL environment variable.",
    ).tag(config=True)

    @default("public_hub_url")
    def _public_hub_url_default(self):
        # Try environment variable first (set by JupyterHub)
        url = os.environ.get("JUPYTERHUB_PUBLIC_HUB_URL", "")
        if not url:
            raise TraitError(
                "public_hub_url is required but not set. "
                "Set it via config (c.UsageViewer.public_hub_url) or "
                "JUPYTERHUB_PUBLIC_HUB_URL environment variable."
            )
        return url.rstrip("/")

    session_secret_key = Unicode(
        help="Secret key for session cookie encryption. Required for secure sessions. Set via config or JUPYTERHUB_USAGE_QUOTAS_SESSION_SECRET_KEY environment variable.",
    ).tag(config=True)

    @default("session_secret_key")
    def _session_secret_key_default(self):
        key = os.environ.get("JUPYTERHUB_USAGE_QUOTAS_SESSION_SECRET_KEY", "")
        if not key:
            raise TraitError(
                "session_secret_key is required but not set. "
                "Set it via config (c.UsageViewer.session_secret_key) or "
                "JUPYTERHUB_USAGE_QUOTAS_SESSION_SECRET_KEY environment variable."
            )
        return key

    # we use page.html from JupyterHub templates to maintain the same look and feel for the usage viewer service.
    # so we need the path to the JupyterHub templates as well as any custom templates so that if there is any
    # custom page.html defined in the custom templates, it can be picked up by the usage viewer service.
    hub_template_paths = List(
        Unicode(),
        help="List of additional paths to search for JupyterHub templates, in order of preference. "
        "The default JupyterHub templates path is always appended so custom paths take precedence "
        "while falling back to JupyterHub's default templates.",
    ).tag(config=True)

    @default("hub_template_paths")
    def _hub_template_paths_default(self):
        return [os.path.join(sys.prefix, "share", "jupyterhub", "templates")]

    @validate("hub_template_paths")
    def _validate_hub_template_paths(self, proposal):
        paths = list(proposal["value"])
        default_path = os.path.join(sys.prefix, "share", "jupyterhub", "templates")
        if default_path not in paths:
            paths.append(default_path)
        return paths

    def initialize(self, argv=None):
        """Initialize the service."""
        super().initialize(argv)
        self.log.setLevel(logging.INFO)
        for handler in self.log.handlers:
            handler.setLevel(logging.INFO)
        if self.config_files:
            for config_file in self.config_files:
                self.load_config_file(config_file)
                self.log.info(f"Loaded config file {config_file}")

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
