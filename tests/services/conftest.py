"""Shared pytest fixtures for jupyterhub-usage-quotas service tests"""

import pytest


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set up standard environment variables for testing"""
    monkeypatch.setenv("JUPYTERHUB_API_TOKEN", "test-token-123")
    monkeypatch.setenv("JUPYTERHUB_API_URL", "http://test-hub:8081/hub/api")
    monkeypatch.setenv("JUPYTERHUB_SERVICE_PREFIX", "/services/usage-quota/")
    monkeypatch.setenv("JUPYTERHUB_PUBLIC_HUB_URL", "http://test-hub:8000")
    monkeypatch.setenv(
        "JUPYTERHUB_USAGE_QUOTAS_PROMETHEUS_URL", "http://prometheus:9090"
    )
    monkeypatch.setenv("JUPYTERHUB_USAGE_QUOTAS_HUB_NAMESPACE", "prod")
    monkeypatch.setenv("JUPYTERHUB_USAGE_QUOTAS_SESSION_SECRET_KEY", "0" * 64)
    return monkeypatch
