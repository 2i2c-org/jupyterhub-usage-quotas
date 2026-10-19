"""
Example configuration file for the usage viewer service, for local development.

The usage viewer runs as an external JupyterHub service, in a separate process.
See the "Running the usage viewer service locally" section in DEVELOPMENT.md.
"""

import os
import socket

c = get_config()  # noqa

# JupyterHub sets these environment variables for the services that it starts.
# An external service must set them itself. HubOAuth reads most of them when
# the service starts, after this file loads. The usage viewer passes the
# service prefix to HubOAuth from c.UsageViewer.service_prefix.

# jupyterhub_config.py sets hub_connect_ip to the private IP address of the
# local machine, so the Hub API listens on that address. This finds the
# address in the same way.
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.connect(("8.8.8.8", 80))
hub_ip = s.getsockname()[0]
s.close()

os.environ["JUPYTERHUB_SERVICE_NAME"] = "usage-quota"
os.environ["JUPYTERHUB_CLIENT_ID"] = "service-usage-quota"
os.environ["JUPYTERHUB_SERVICE_PREFIX"] = "/services/usage-quota/"
os.environ["JUPYTERHUB_API_URL"] = f"http://{hub_ip}:8081/hub/api"
# The api_token of the usage-quota service in jupyterhub_config_secret.py
os.environ["JUPYTERHUB_API_TOKEN"] = "use-another-secure-random-key-in-production"

# Usage viewer

c.UsageViewer.service_prefix = "/services/usage-quota/"
# c.UsageViewer.hub_namespace = "prod"
c.UsageViewer.public_hub_url = "http://localhost:8000/hub/"
