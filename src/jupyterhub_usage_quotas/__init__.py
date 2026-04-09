import os

from jupyterhub_usage_quotas.handler import UsageHandler

__all__ = ["get_template_path", "UsageHandler"]


def get_template_path():
    """Get the path to the templates directory."""
    return os.path.join(os.path.dirname(__file__), "templates")
