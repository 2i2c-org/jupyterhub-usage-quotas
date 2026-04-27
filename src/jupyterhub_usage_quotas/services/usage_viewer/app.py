"""Usage Viewer Service - Combined Application and FastAPI routes."""

import json
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from jinja2 import Environment, FileSystemLoader
from jupyterhub.services.auth import HubOAuth
from starlette.middleware.sessions import SessionMiddleware

from jupyterhub_usage_quotas import get_template_path
from jupyterhub_usage_quotas.config import UsageViewerConfig
from jupyterhub_usage_quotas.services.usage_viewer.storage_quota_client import (
    StorageQuotaClient,
)

logger = logging.getLogger(__name__)


def create_fastapi_app(
    storage_client: StorageQuotaClient,
    config: UsageViewerConfig,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        storage_client: StorageQuotaClient instance for querying storage data
        config: UsageViewerConfig instance containing all configuration

    Returns:
        Configured FastAPI application
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        await storage_client.close()

    app = FastAPI(lifespan=lifespan)
    jinja_env = Environment(
        loader=FileSystemLoader(get_template_path()), autoescape=True
    )

    auth = HubOAuth(
        oauth_redirect_uri=f"{config.service_prefix.rstrip('/')}/oauth_callback",
        cache_max_age=60,
    )

    app.add_middleware(
        SessionMiddleware,
        secret_key=config.session_secret_key,
        session_cookie="jupyterhub_usage_session",
        max_age=3600,
        same_site="lax",
        https_only=not config.dev_mode,
    )

    async def get_current_user(request: Request):
        """Check if the user is logged in, redirecting to JupyterHub if not."""
        token = request.session.get("token")
        if token:
            # use_cache=False ensures we detect JupyterHub logouts immediately
            user = await auth.user_for_token(token, use_cache=False, sync=False)
            if user:
                return user
            # Token revoked (user logged out of JupyterHub) — clear session
            request.session.clear()

        # Generate state for OAuth flow and store in session
        state = auth.generate_state()
        request.session["oauth_state"] = state

        redirect_url = f"{auth.login_url}&state={state}"

        # Use JS to redirect the top-level frame — plain HTTP redirects are blocked
        # by CSP frame-ancestors when the service is embedded in a JupyterHub iframe.
        return HTMLResponse(
            f"<script>window.top.location.href={json.dumps(redirect_url)};</script>"
        )

    @app.get(config.service_prefix)
    async def home(request: Request):
        """Home page that shows usage quota information.

        If the user is not logged in, they will be redirected to JupyterHub to log in
        through get_current_user redirect flow.
        """
        result = await get_current_user(request)
        # Using JS to redirect the top-level frame, so if we get an HTMLResponse back,
        # it means the user is not authenticated and needs to log in.
        if isinstance(result, HTMLResponse):
            return result
        user = result

        # Use storage client to get usage data
        usage_data = await storage_client.get_user_storage_usage(user["name"])

        template = jinja_env.get_template("usage.html")
        html_content = template.render(usage_data=usage_data)
        return HTMLResponse(html_content)

    @app.get(f"{config.service_prefix.rstrip('/')}/oauth_callback")
    async def oauth_callback(request: Request, code: str, state: str):
        """Handle the OAuth2 callback from JupyterHub.

        Validates the state parameter, exchanges the authorization code for an access
        token via HubOAuth, stores the token in the session, and redirects back to the
        original page the user was trying to access.

        Args:
            request: The incoming request object containing session data.
            code: The authorization code provided by JupyterHub's OAuth2 server.
            state: The state parameter for CSRF protection validation.

        Returns:
            Redirects to the original requested URL on success.

        Raises:
            HTTPException:
                - 400 status: If OAuth state is missing or does not match the saved state.
                - 500 status: If token retrieval fails.
        """
        # Validate state using session
        saved_state = request.session.get("oauth_state")
        if not saved_state or saved_state != state:
            raise HTTPException(
                status_code=400,
                detail="OAuth state mismatch or missing",
            )

        token = await auth.token_for_code(code, sync=False)
        if not token:
            raise HTTPException(
                status_code=500, detail="Failed to retrieve access token"
            )

        request.session["token"] = token
        request.session.pop("oauth_state", None)

        return RedirectResponse(url=f"{config.public_hub_url}/hub/usage")

    return app


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
            escape_scheme=self.escape_username_scheme,
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
        """Start the FastAPI service."""
        self.log.info(
            f"Starting Usage Viewer service on {self.service_host}:{self.service_port}"
        )

        app = create_fastapi_app(self.storage_client, config=self)

        uvicorn.run(
            app,
            host=self.service_host,
            port=self.service_port,
            log_level="info",
        )


def main():
    """Entry point for the usage viewer service."""
    UsageViewer.launch_instance()


if __name__ == "__main__":
    main()
