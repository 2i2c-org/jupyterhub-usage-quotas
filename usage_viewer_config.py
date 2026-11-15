"""
Example configuration file for the usage viewer service, for local development.

The usage viewer runs as an external JupyterHub service, in a separate process.
See the "Running the usage viewer service locally" section in DEVELOPMENT.md.
"""

import socket

c = get_config()  # noqa

# jupyterhub_config.py sets hub_connect_ip to the private IP address of the
# local machine, so the Hub API listens on that address. This finds the
# address in the same way.
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.connect(("8.8.8.8", 80))
hub_ip = s.getsockname()[0]
s.close()

# Usage viewer

c.UsageViewer.public_hub_url = "http://localhost:8000/"
c.UsageViewer.hub_api_url = f"http://{hub_ip}:8081/hub/api"
# c.UsageViewer.hub_namespace = "prod"
