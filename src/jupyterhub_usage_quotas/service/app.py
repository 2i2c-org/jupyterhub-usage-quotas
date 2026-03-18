import json
import os
import secrets
from urllib.parse import urlencode

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from jinja2 import Environment, FileSystemLoader
from starlette.middleware.sessions import SessionMiddleware

from jupyterhub_usage_quotas import get_template_path
from jupyterhub_usage_quotas.service.prometheus_client import PrometheusClient

app = FastAPI()
jinja_env = Environment(loader=FileSystemLoader(get_template_path()), autoescape=True)

# -----------------------------------------------------------------------------
# CONFIGURATION
# -----------------------------------------------------------------------------
# The API token to talk to the Hub
HUB_TOKEN = os.environ.get("JUPYTERHUB_API_TOKEN")
# The URL for the Hub API; could be an internal URL (e.g., http://hub:8081/hub/api)
HUB_API_URL = os.environ.get("JUPYTERHUB_API_URL", "http://jupyterhub:8081/hub/api")
# The prefix for this service (e.g., /services/my-service/)
SERVICE_PREFIX = os.environ.get("JUPYTERHUB_SERVICE_PREFIX", "/")
# The external URL users use to access the Hub (e.g., http://localhost:8000)
PUBLIC_HUB_URL = os.environ.get(
    "JUPYTERHUB_EXTERNAL_URL", "http://localhost:8000"
).rstrip("/")
# OAuth client ID for this service
CLIENT_ID = f"service-{os.environ.get('JUPYTERHUB_SERVICE_NAME', 'fastapi-service')}"

# Authorization URL (External/Browser-facing)
AUTH_URL = f"{PUBLIC_HUB_URL}/hub/api/oauth2/authorize"

# Callback URL (The path within your service)
CALLBACK_PATH = "oauth_callback"

# The computed Redirect URI (MUST match what the browser sees)
# Example: http://localhost:8000/services/my-service/oauth_callback
REDIRECT_URI = f"{PUBLIC_HUB_URL}{SERVICE_PREFIX}{CALLBACK_PATH}"

# Add Session Middleware to store the OAuth state
# 'secret_key' should be random in production, but can be set via SESSION_SECRET_KEY for testing
SESSION_SECRET_KEY = os.environ.get("SESSION_SECRET_KEY", secrets.token_hex(32))
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET_KEY)


# -----------------------------------------------------------------------------
# OAUTH DEPENDENCY
# -----------------------------------------------------------------------------
async def get_current_user(request: Request):
    """Check if the user is logged in, redirecting to JupyterHub if not."""
    user = request.session.get("user")
    access_token = request.session.get("access_token")
    if user and access_token:
        # Verify the token is still valid (catches JupyterHub logout)
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{HUB_API_URL}/user",
                headers={"Authorization": f"token {access_token}"},
            )
        if resp.status_code == 200:
            return user
        # Token revoked (user logged out of JupyterHub) — clear session
        request.session.clear()

    state = secrets.token_hex(16)
    request.session["oauth_state"] = state

    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "state": state,
    }

    redirect_url = f"{AUTH_URL}?{urlencode(params)}"
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


@app.get(f"{SERVICE_PREFIX}{CALLBACK_PATH}")
async def oauth_callback(request: Request, code: str, state: str):
    """
    Handle the OAuth2 callback from JupyterHub.

    This endpoint processes the OAuth2 authorization code flow callback from JupyterHub.
    It validates the state parameter to prevent CSRF attacks, exchanges the authorization
    code for an access token, retrieves the authenticated user's information, and stores
    both the user data and access token in the session for subsequent authenticated requests.

    Args:
        request (Request): The incoming request object containing session data.
        code (str): The authorization code provided by JupyterHub's OAuth2 server.
        state (str): The state parameter for CSRF protection validation.

    Returns:
        RedirectResponse: Redirects to the JupyterHub usage page upon successful authentication.

    Raises:
        HTTPException:
            - 400 status: If OAuth state is missing or does not match the saved state.
            - 500 status: If token retrieval or user data retrieval fails.
    """
    saved_state = request.session.get("oauth_state")
    if not saved_state or saved_state != state:
        raise HTTPException(status_code=400, detail="OAuth state mismatch or missing")

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{HUB_API_URL}/oauth2/token",
            data={
                "client_id": CLIENT_ID,
                "client_secret": HUB_TOKEN,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI,
            },
        )

        if resp.status_code != 200:
            raise HTTPException(
                status_code=500, detail="Failed to retrieve access token"
            )

        token_data = resp.json()
        access_token = token_data["access_token"]

        resp = await client.get(
            f"{HUB_API_URL}/user",
            headers={"Authorization": f"token {access_token}"},
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=500, detail="Failed to retrieve user data")

    user = resp.json()
    request.session["user"] = user
    request.session["access_token"] = access_token
    request.session.pop("oauth_state", None)

    return RedirectResponse(url=f"{PUBLIC_HUB_URL}/hub/usage")
