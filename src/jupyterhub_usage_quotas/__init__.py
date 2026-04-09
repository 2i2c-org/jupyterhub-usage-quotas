import os

from jupyterhub_usage_quotas.handler import UsageHandler

__all__ = ["get_template_path", "UsageHandler"]


def get_template_path():
    """Get the path to the templates directory."""
    return os.path.join(os.path.dirname(__file__), "templates")


def setup_usage_quotas(c):
    """
    Setup common config to enable the usage quotas system.

    Expects to be called from a `jupyterhub_config.py` file, with `c`
    the config object being passed in.
    """

    c.JupyterHub.template_paths = [get_template_path()]

    c.JupyterHub.extra_handlers = [
        (r"/usage", UsageHandler),
    ]
