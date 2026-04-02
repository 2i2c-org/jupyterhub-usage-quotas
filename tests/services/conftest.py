"""Shared pytest fixtures for jupyterhub-usage-quotas service tests"""

import os
import sys
from unittest.mock import AsyncMock

import pytest
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient


def set_session(client: TestClient, app, session_data: dict):
    """Set session data in the TestClient by making a request that sets the session."""

    @app.get("/__test_set_session__")
    async def set_test_session(request: Request):
        for key, value in session_data.items():
            request.session[key] = value
        return JSONResponse({"status": "ok"})

    client.get("/__test_set_session__")

    for i, route in enumerate(app.routes):
        if hasattr(route, "path") and route.path == "/__test_set_session__":
            app.routes.pop(i)
            break


def get_session(client: TestClient, app) -> dict:
    """Get session data from the TestClient by making a request."""

    @app.get("/__test_get_session__")
    async def get_test_session(request: Request):
        return JSONResponse(dict(request.session))

    response = client.get("/__test_get_session__")

    for i, route in enumerate(app.routes):
        if hasattr(route, "path") and route.path == "/__test_get_session__":
            app.routes.pop(i)
            break

    return response.json()


@pytest.fixture
def app(mock_env_vars, mocker):
    """Provide the FastAPI application instance with reloaded environment variables"""
    # Clear any cached modules FIRST
    if "jupyterhub_usage_quotas.services.usage_viewer.app" in sys.modules:
        del sys.modules["jupyterhub_usage_quotas.services.usage_viewer.app"]

    # Set up HubOAuth mock BEFORE importing
    async def mock_token_for_code(code, sync=False):
        if code == "badcode":
            return None
        return "test-token"

    async def mock_user_for_token(token, use_cache=True, sync=False):
        if token == "valid-token" or token == "test-token":
            return {"name": "testuser", "admin": False, "groups": ["users"]}
        return None

    # Create a mock auth object
    mock_auth = mocker.MagicMock()
    mock_auth.token_for_code = mock_token_for_code
    mock_auth.user_for_token = mock_user_for_token
    mock_auth.generate_state = mocker.MagicMock(return_value="test-state-123")
    mock_auth.login_url = "http://localhost:8000/hub/api/oauth2/authorize?client_id=service-usage-quota&redirect_uri=http://localhost:8000/services/usage-quota/oauth_callback&response_type=code"

    # Mock HubOAuth constructor BEFORE importing the module
    mocker.patch(
        "jupyterhub_usage_quotas.services.usage_viewer.app.HubOAuth",
        return_value=mock_auth,
    )

    # NOW import and create the app
    from jupyterhub_usage_quotas.services.usage_viewer.app import create_fastapi_app
    from jupyterhub_usage_quotas.services.usage_viewer.storage_quota_client import (
        StorageQuotaClient,
    )

    # Create storage client directly for the Usage Viewer service
    storage_client = StorageQuotaClient(
        prometheus_url=os.environ.get("PROMETHEUS_URL", "http://prometheus:9090"),
        namespace=os.environ.get("PROMETHEUS_NAMESPACE", ""),
        dev_mode=False,  # Tests use mocked Prometheus responses, not dev mode mock data
    )

    # Create app with storage_quota_client (HubOAuth is now mocked)
    # Use dev_mode=True in tests so https_only=False (TestClient uses HTTP)
    app = create_fastapi_app(storage_client, dev_mode=True)

    return app


@pytest.fixture
def mock_hub_auth(app, mocker):
    """Return the mocked HubOAuth instance for tests that need to customize it"""
    # The mock was already set up in the app fixture
    # This fixture just provides access to it for tests that need to customize behavior

    async def mock_token_for_code(code, sync=False):
        if code == "badcode":
            return None
        return "test-token"

    async def mock_user_for_token(token, use_cache=True, sync=False):
        if token == "valid-token" or token == "test-token":
            return {"name": "testuser", "admin": False, "groups": ["users"]}
        return None

    mock_auth = mocker.MagicMock()
    mock_auth.token_for_code = mock_token_for_code
    mock_auth.user_for_token = mock_user_for_token
    mock_auth.generate_state = mocker.MagicMock(return_value="test-state-123")
    mock_auth.login_url = "http://localhost:8000/hub/oauth_login"

    return mock_auth


@pytest.fixture
def client(app):
    """Provide TestClient for making HTTP requests"""
    return TestClient(app)


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set up standard environment variables for testing"""
    monkeypatch.setenv("JUPYTERHUB_API_TOKEN", "test-token-123")
    monkeypatch.setenv("JUPYTERHUB_API_URL", "http://test-hub:8081/hub/api")
    monkeypatch.setenv("JUPYTERHUB_SERVICE_PREFIX", "/services/usage/")
    monkeypatch.setenv("JUPYTERHUB_PUBLIC_HUB_URL", "http://test-hub:8000")
    monkeypatch.setenv("PROMETHEUS_URL", "http://prometheus:9090")
    monkeypatch.setenv("PROMETHEUS_NAMESPACE", "prod")
    monkeypatch.setenv("SESSION_SECRET_KEY", "0" * 64)
    return monkeypatch


@pytest.fixture
def mock_session_user():
    """Mock authenticated user session data"""
    return {
        "name": "testuser",
        "admin": False,
        "groups": ["users"],
        "server": "/user/testuser/",
    }


def _make_mock_manager(mocker, usage_data: dict) -> AsyncMock:
    """Helper to create a mock storage client with get_user_storage_usage returning usage_data"""

    async def mock_get_user_storage_usage(username):
        return usage_data

    mocker.patch(
        "jupyterhub_usage_quotas.services.usage_viewer.storage_quota_client.StorageQuotaClient.get_user_storage_usage",
        side_effect=mock_get_user_storage_usage,
    )


@pytest.fixture
def mock_prometheus_client(mocker):
    """Mock manager.get_storage_usage for route tests (50% usage)"""
    _make_mock_manager(
        mocker,
        {
            "username": "testuser",
            "usage_bytes": 5368709120,
            "quota_bytes": 10737418240,
            "usage_gb": 5.0,
            "quota_gb": 10.0,
            "percentage": 50.0,
            "last_updated": "2026-02-24T12:00:00+00:00",
        },
    )


@pytest.fixture
def mock_prometheus_client_with_error(mocker):
    """Mock manager.get_storage_usage that returns an error"""
    _make_mock_manager(
        mocker,
        {
            "username": "testuser",
            "error": "Unable to reach Prometheus. Please try again later.",
        },
    )


@pytest.fixture
def mock_prometheus_client_no_data(mocker):
    """Mock manager.get_storage_usage that returns no data error"""
    _make_mock_manager(
        mocker,
        {
            "username": "testuser",
            "error": "No storage data found for your account.",
        },
    )


@pytest.fixture
def mock_prometheus_client_high_usage(mocker):
    """Mock manager.get_storage_usage that returns high usage (95%)"""
    _make_mock_manager(
        mocker,
        {
            "username": "testuser",
            "usage_bytes": 10200547328,
            "quota_bytes": 10737418240,
            "usage_gb": 9.5,
            "quota_gb": 10.0,
            "percentage": 95.0,
            "last_updated": "2026-02-24T12:00:00+00:00",
        },
    )


@pytest.fixture
def mock_oauth_state():
    """Generate mock OAuth state token"""
    return "abc123def456ghi789"


@pytest.fixture
def usage_data_50_percent():
    """Usage data dict for 50% usage (normal)"""
    return {
        "username": "testuser",
        "usage_bytes": 5368709120,
        "quota_bytes": 10737418240,
        "usage_gb": 5.0,
        "quota_gb": 10.0,
        "percentage": 50.0,
        "last_updated": "2026-02-24T12:00:00+00:00",
    }


@pytest.fixture
def usage_data_90_percent():
    """Usage data dict for 90% usage (warning threshold)"""
    return {
        "username": "testuser",
        "usage_bytes": 9663676416,
        "quota_bytes": 10737418240,
        "usage_gb": 9.0,
        "quota_gb": 10.0,
        "percentage": 90.0,
        "last_updated": "2026-02-24T12:00:00+00:00",
    }


@pytest.fixture
def usage_data_95_percent():
    """Usage data dict for 95% usage (high warning)"""
    return {
        "username": "testuser",
        "usage_bytes": 10200547328,
        "quota_bytes": 10737418240,
        "usage_gb": 9.5,
        "quota_gb": 10.0,
        "percentage": 95.0,
        "last_updated": "2026-02-24T12:00:00+00:00",
    }


@pytest.fixture
def usage_data_0_percent():
    """Usage data dict for 0% usage"""
    return {
        "username": "testuser",
        "usage_bytes": 0,
        "quota_bytes": 10737418240,
        "usage_gb": 0.0,
        "quota_gb": 10.0,
        "percentage": 0.0,
        "last_updated": "2026-02-24T12:00:00+00:00",
    }


@pytest.fixture
def usage_data_100_percent():
    """Usage data dict for 100% usage"""
    return {
        "username": "testuser",
        "usage_bytes": 10737418240,
        "quota_bytes": 10737418240,
        "usage_gb": 10.0,
        "quota_gb": 10.0,
        "percentage": 100.0,
        "last_updated": "2026-02-24T12:00:00+00:00",
    }


@pytest.fixture
def usage_data_prometheus_error():
    """Usage data dict with Prometheus error"""
    return {
        "username": "testuser",
        "error": "Unable to reach Prometheus. Please try again later.",
    }


@pytest.fixture
def usage_data_no_quota():
    """Usage data dict with no quota data error"""
    return {
        "username": "testuser",
        "error": "No storage data found for your account.",
    }


@pytest.fixture
def usage_data_terabytes():
    """Usage data dict with terabyte values"""
    return {
        "username": "testuser",
        "usage_bytes": 549755813888,
        "quota_bytes": 1099511627776,
        "usage_gb": 512.0,
        "quota_gb": 1024.0,
        "percentage": 50.0,
        "last_updated": "2026-02-24T12:00:00+00:00",
    }
