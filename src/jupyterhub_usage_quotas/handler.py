"""Custom JupyterHub handler for the usage wrapper page.

This handler renders an iframe that embeds the usage-quota service within
JupyterHub's standard page template.
"""

from jupyterhub.handlers import BaseHandler
from tornado import web


class UsageHandler(BaseHandler):
    """Handler that displays the usage-quota service in an iframe."""

    service_prefix = "/services/usage-quota/"

    @property
    def template_namespace(self):
        """Add current user and service prefix to template namespace."""
        ns = super().template_namespace
        ns["user"] = self.current_user
        ns["jupyterhub_usage_quotas_service_prefix"] = self.service_prefix
        return ns

    @web.authenticated
    async def get(self):
        """Render the usage wrapper template."""
        html = await self.render_template("usage_wrapper.html")
        self.write(html)
