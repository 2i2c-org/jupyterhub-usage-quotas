"""Tests for UsageViewer application initialization."""

import pytest
from traitlets import TraitError

from jupyterhub_usage_quotas.services.usage_viewer.app import UsageViewer


def test_prometheus_auth_raises_on_missing_keys():
    """Setting prometheus_auth with wrong keys should raise TraitError immediately."""
    app = UsageViewer()
    with pytest.raises(TraitError, match="missing required keys"):
        app.prometheus_auth = {"user": "x", "pass": "y"}


def test_initialize_raises_when_config_file_explicitly_set_but_missing(mock_env_vars):
    """Explicitly setting config_file to a missing path should raise TraitError."""
    app = UsageViewer()
    with pytest.raises(TraitError):
        app.config_files = "[/nonexistent/jupyterhub_config.py]"
