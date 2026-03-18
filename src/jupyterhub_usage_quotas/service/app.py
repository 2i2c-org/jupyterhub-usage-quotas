import json
import os
import secrets

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from jinja2 import Environment, FileSystemLoader
from jupyterhub.services.auth import HubOAuth
from starlette.middleware.sessions import SessionMiddleware

from jupyterhub_usage_quotas import get_template_path
from jupyterhub_usage_quotas.service.prometheus_client import PrometheusClient

app = FastAPI()
jinja_env = Environment(loader=FileSystemLoader(get_template_path()), autoescape=True)

# -----------------------------------------------------------------------------
# CONFIGURATION
# -----------------------------------------------------------------------------
# The prefix for this service (e.g., /services/my-service/)
SERVICE_PREFIX = os.environ.get("JUPYTERHUB_SERVICE_PREFIX", "/")
# The external URL users use to access the Hub (e.g., http://localhost:8000)
PUBLIC_HUB_URL = os.environ.get(
    "JUPYTERHUB_EXTERNAL_URL", "http://localhost:8000"
).rstrip("/")

# HubOAuth reads JUPYTERHUB_API_TOKEN, JUPYTERHUB_API_URL, JUPYTERHUB_SERVICE_PREFIX automatically.
# Override auth/redirect URLs to use the external (browser-facing) URL.
auth = HubOAuth(
    oauth_redirect_uri=f"{PUBLIC_HUB_URL}{SERVICE_PREFIX}oauth_redirect",
    oauth_authorization_url=f"{PUBLIC_HUB_URL}/hub/api/oauth2/authorize",
    cache_max_age=60,
)

# Add Session Middleware to store the OAuth state and token
# 'secret_key' should be random in production, but can be set via SESSION_SECRET_KEY for testing
SESSION_SECRET_KEY = os.environ.get("SESSION_SECRET_KEY", secrets.token_hex(32))
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET_KEY)


# -----------------------------------------------------------------------------
# OAUTH DEPENDENCY
# -----------------------------------------------------------------------------
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

    state = auth.generate_state(next_url=str(request.url.path))
    request.session["oauth_state"] = state

    redirect_url = f"{auth.login_url}&state={state}"
    # Use JS to redirect the top-level frame — plain HTTP redirects are blocked
    # by CSP frame-ancestors when the service is embedded in a JupyterHub iframe.
    return HTMLResponse(
        f"<script>window.top.location.href={json.dumps(redirect_url)};</script>"
    )


# -----------------------------------------------------------------------------
# ROUTES
# -----------------------------------------------------------------------------


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

    async with PrometheusClient() as prom_client:
        usage_data = await prom_client.get_user_usage(user["name"])

    template = jinja_env.get_template("usage.html")
    html_content = template.render(usage_data=usage_data)
    return HTMLResponse(html_content)


@app.get(f"{SERVICE_PREFIX}oauth_redirect")
async def oauth_redirect(request: Request, code: str, state: str):
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
    saved_state = request.session.get("oauth_state")
    if not saved_state or saved_state != state:
        raise HTTPException(status_code=400, detail="OAuth state mismatch or missing")

    token = await auth.token_for_code(code, sync=False)
    if not token:
        raise HTTPException(status_code=500, detail="Failed to retrieve access token")

    request.session["token"] = token
    request.session.pop("oauth_state", None)

    # Redirect to /hub/usage (the embedded view within JupyterHub with nav bar)
    # NOT to SERVICE_PREFIX which is the standalone service view without nav
    return RedirectResponse(url=f"{PUBLIC_HUB_URL}/hub/usage")
