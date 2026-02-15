"""
Example configuration file for JupyterHub usage quotas.
"""

import socket

c = get_config()  # noqa

# JupyterHub

c.JupyterHub.ip = "127.0.0.1"
c.JupyterHub.hub_ip = "127.0.0.1"
c.JupyterHub.authenticator_class = "dummy"
c.JupyterHub.spawner_class = "kubespawner.KubeSpawner"

# Find private IP address of your local machine that the kubernetes cluster can talk to on your local area network.
# Graciously used from https://stackoverflow.com/a/166589
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.connect(("8.8.8.8", 80))
host_ip = s.getsockname()[0]
s.close()
c.JupyterHub.hub_connect_ip = host_ip

# Quotas

c.QuotasApp.log_datefmt = "%Y-%m-%d %H:%M:%S"
c.QuotasApp.log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
c.QuotasApp.log_level = "INFO"

c.Quotas.prometheus_usage_metrics = [
    {"memory": "kube_pod_container_resource_requests{resource='memory'}"},
    {"cpu": "kube_pod_container_resource_requests{resource='cpu'}"},
]

c.Quotas.prometheus_scrape_interval = 20

c.Quotas.scope_backup_strategy = {
    "empty": {
        "resource": "memory",
        "limit": {"value": 500, "unit": "GiB-hours"},
        "window": 7,
    },
    "intersection": "max",
}

c.Quotas.failover_open = True
