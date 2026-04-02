"""Usage Viewer Service - Combined Application and FastAPI routes."""

import json
import logging
import secrets

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from jinja2 import Environment, FileSystemLoader
from jupyterhub.services.auth import HubOAuth
from starlette.middleware.sessions import SessionMiddleware
from traitlets.config import Application
import uvicorn

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
    app = FastAPI()
    jinja_env = Environment(
        loader=FileSystemLoader(get_template_path()), autoescape=True
    )

    SERVICE_PREFIX = config.service_prefix
    OAUTH_CALLBACK_PATH = f"{SERVICE_PREFIX}/oauth_callback"
    PUBLIC_HUB_URL = config.public_hub_url
    SESSION_SECRET_KEY = config.session_secret_key

    auth = HubOAuth(
        oauth_redirect_uri=OAUTH_CALLBACK_PATH,
        cache_max_age=60,
    )

    app.add_middleware(
        SessionMiddleware,
        secret_key=SESSION_SECRET_KEY,
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
        state = secrets.token_hex(16)
        request.session["oauth_state"] = state

        redirect_url = f"{auth.login_url}&state={state}"

        # Use JS to redirect the top-level frame — plain HTTP redirects are blocked
        # by CSP frame-ancestors when the service is embedded in a JupyterHub iframe.
        return HTMLResponse(
            f"<script>window.top.location.href={json.dumps(redirect_url)};</script>"
        )

    @app.get(SERVICE_PREFIX)
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

    @app.get(OAUTH_CALLBACK_PATH)
    async def oauth_callback(request: Request, code: str, state: str):
        """Handle the OAuth2 callback from JupyterHub.

        Validates the state parameter, exchanges the authorization code for an access
        token via HubOAuth, stores the token in the session, and redirects back to the
        original page the user was trying to access.

        Args:
            request (Request): The incoming request object containing session data.
            code (str): The authorization code provided by JupyterHub's OAuth2 server.
            state (str): The state parameter for CSRF protection validation.

        Returns:
            RedirectResponse: Redirects to the original requested URL on success.

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

        return RedirectResponse(url=f"{PUBLIC_HUB_URL}/hub/usage")

    return app


class UsageViewer(Application, UsageViewerConfig):
    """Application for running the usage quota viewer service."""

    name = "jupyterhub-usage-viewer"
    description = "Web service for viewing storage usage quotas"

    aliases = {
        "port": "UsageViewer.service_port",
        "host": "UsageViewer.service_host",
        "prometheus-url": "UsageViewer.prometheus_url",
        "prometheus-namespace": "UsageViewer.prometheus_namespace",
        "dev-mode": "UsageViewer.dev_mode",
        "service-prefix": "UsageViewer.service_prefix",
        "public-hub-url": "UsageViewer.public_hub_url",
        "session-secret-key": "UsageViewer.session_secret_key",
    }

    def initialize(self, argv=None):
        """Initialize the service."""
        super().initialize(argv)

        self.storage_client = StorageQuotaClient(
            prometheus_url=self.prometheus_url,
            namespace=self.prometheus_namespace,
            dev_mode=self.dev_mode,
        )

        self.log.info("Initialized Usage Viewer service")
        self.log.info(f"Prometheus URL: {self.prometheus_url}")
        self.log.info(f"Prometheus Namespace: {self.prometheus_namespace or '(empty)'}")
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
