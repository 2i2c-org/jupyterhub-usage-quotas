"""Tests for UsageViewer application initialization."""

import pytest
from traitlets import TraitError

from jupyterhub_usage_quotas.services.usage_viewer.app import UsageViewer


def test_initialize_raises_when_config_file_explicitly_set_but_missing(mock_env_vars):
    """Explicitly setting config_file to a missing path should raise TraitError."""
    app = UsageViewer()
    with pytest.raises(TraitError):
        app.config_file = "/nonexistent/jupyterhub_config.py"


def test_initialize_raises_when_default_config_file_not_found(
    mock_env_vars, tmp_path, monkeypatch
):
    """initialize() should raise SystemExit when the default config file doesn't exist.

    This tests the silent-failure case: no --config_file arg, default 'jupyterhub_config.py'
    is absent, but currently no error is raised.
    """
    monkeypatch.chdir(tmp_path)
    app = UsageViewer()
    with pytest.raises(SystemExit):
        app.initialize(argv=[])
