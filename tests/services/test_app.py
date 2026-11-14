"""Tests for UsageViewer application initialization."""

import os
from unittest.mock import MagicMock

import pytest
from traitlets import TraitError
from traitlets.config import Config

from jupyterhub_usage_quotas.services.usage_viewer.app import UsageViewer, hub_base_path


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


HUB_ENV_VARS = [
    "JUPYTERHUB_API_TOKEN",
    "JUPYTERHUB_API_URL",
    "JUPYTERHUB_CLIENT_ID",
    "JUPYTERHUB_PUBLIC_HUB_URL",
    "JUPYTERHUB_PUBLIC_URL",
    "JUPYTERHUB_SERVICE_NAME",
    "JUPYTERHUB_SERVICE_PREFIX",
]


@pytest.fixture
def clean_env(mocker):
    mocker.patch.dict(os.environ)
    for name in HUB_ENV_VARS:
        os.environ.pop(name, None)


@pytest.mark.parametrize(
    "public_hub_url, expected",
    [
        ("https://hub.example.org", "/"),
        ("https://hub.example.org/", "/"),
        ("https://hub.example.org/hub", "/"),
        ("https://hub.example.org/hub/", "/"),
        ("https://hub.example.org/jhub/", "/jhub/"),
        ("https://hub.example.org/jhub/hub/", "/jhub/"),
    ],
)
def test_hub_base_path(public_hub_url, expected):
    assert hub_base_path(public_hub_url) == expected


def test_hub_settings_derived_defaults(clean_env):
    app = UsageViewer(public_hub_url="https://hub.example.org/jhub/hub/")
    assert app.service_name == "usage-quota"
    assert app.service_prefix == "/jhub/services/usage-quota/"
    assert app.oauth_client_id == "service-usage-quota"
    assert app.hub_prefix == "/jhub/hub/"
    assert app.hub_api_url == "http://hub:8081/jhub/hub/api"


def test_hub_settings_derived_from_service_name(clean_env):
    app = UsageViewer(public_hub_url="https://hub.example.org/", service_name="quota")
    assert app.service_prefix == "/services/quota/"
    assert app.oauth_client_id == "service-quota"


def test_hub_settings_from_env(clean_env):
    os.environ.update(
        {
            "JUPYTERHUB_API_TOKEN": "env-token",
            "JUPYTERHUB_API_URL": "http://10.0.0.1:8081/hub/api",
            "JUPYTERHUB_CLIENT_ID": "env-client",
            "JUPYTERHUB_PUBLIC_HUB_URL": "https://hub.example.org/hub/",
            "JUPYTERHUB_SERVICE_NAME": "env-name",
            "JUPYTERHUB_SERVICE_PREFIX": "/services/env-prefix/",
        }
    )
    app = UsageViewer()
    assert app.hub_api_token == "env-token"
    assert app.hub_api_url == "http://10.0.0.1:8081/hub/api"
    assert app.oauth_client_id == "env-client"
    assert app.service_name == "env-name"
    assert app.service_prefix == "/services/env-prefix/"


def test_hub_settings_config_overrides_env(clean_env):
    os.environ.update(
        {
            "JUPYTERHUB_API_TOKEN": "env-token",
            "JUPYTERHUB_API_URL": "http://10.0.0.1:8081/hub/api",
            "JUPYTERHUB_SERVICE_NAME": "env-name",
        }
    )
    config = Config()
    config.UsageViewer.hub_api_token = "config-token"
    config.UsageViewer.hub_api_url = "http://hub:8081/hub/api"
    config.UsageViewer.service_name = "config-name"
    config.UsageViewer.public_hub_url = "https://hub.example.org/"
    app = UsageViewer(config=config)
    assert app.hub_api_token == "config-token"
    assert app.hub_api_url == "http://hub:8081/hub/api"
    assert app.service_name == "config-name"
    assert app.service_prefix == "/services/config-name/"


def test_hub_api_token_required(clean_env):
    with pytest.raises(TraitError, match="hub_api_token is required"):
        UsageViewer().hub_api_token


def test_make_app_configures_hub_oauth(clean_env, mocker):
    instance = mocker.patch(
        "jupyterhub_usage_quotas.services.usage_viewer.app.HubOAuth.instance"
    )
    app = UsageViewer(
        public_hub_url="https://hub.example.org/",
        hub_api_url="http://hub:8081/hub/api",
        hub_api_token="token",
        session_secret_key="0" * 64,
    )
    tornado_app = app.make_app(MagicMock())

    instance.assert_called_once_with(
        cache_max_age=60,
        base_url="/services/usage-quota/",
        hub_prefix="/hub/",
        api_url="http://hub:8081/hub/api",
        api_token="token",
        oauth_client_id="service-usage-quota",
        access_scopes={"access:services!service=usage-quota"},
    )
    assert (
        os.environ["JUPYTERHUB_PUBLIC_URL"]
        == "https://hub.example.org/services/usage-quota/"
    )
    assert tornado_app.settings["public_hub_url"] == "https://hub.example.org/hub/"
    assert tornado_app.settings["logout_url"] == "https://hub.example.org/hub/logout"
