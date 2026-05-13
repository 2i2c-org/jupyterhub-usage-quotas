"""
Example configuration file for JupyterHub usage quotas.
"""

import socket

from jupyterhub_usage_quotas import setup_usage_quotas

c = get_config()  # noqa

# JupyterHub

c.JupyterHub.ip = "127.0.0.1"
c.JupyterHub.port = 8000
c.JupyterHub.hub_ip = "127.0.0.1"
c.JupyterHub.authenticator_class = "dummy"

# Find private IP address of your local machine that the kubernetes cluster can talk to on your local area network.
# Graciously used from https://stackoverflow.com/a/166589
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.connect(("8.8.8.8", 80))
host_ip = s.getsockname()[0]
s.close()
c.JupyterHub.hub_connect_ip = host_ip

# Initialize with n_users, with 1 user per group
n_users = 3
c.Authenticator.allowed_users = {f"user-{i}" for i in range(n_users)}
c.JupyterHub.load_groups = {
    f"group-{i}": dict(users=[f"user-{i}"]) for i in range(n_users)
}
c.Authenticator.admin_users = {"admin"}

# Usage Quotas

c.UsageConfig.prometheus_auth = {"username": "", "password": ""}
c.UsageConfig.hub_namespace = "staging"

# Usage Quota Config

c.UsageQuotaManager.scope_backup_strategy = {
    "empty": {
        "resource": "memory",
        "limit": {"value": 10, "unit": "GiB-hours"},
        "window": 30,
    },
    "intersection": "max",
}

c.UsageQuotaManager.failover_open = False

c.UsageQuotaManager.policy = [
    {
        "resource": "memory",
        "limit": {
            "value": 35,
            "unit": "GiB-hours",
        },
        "window": 30,
        "scope": {"group": ["group-0", "group-1"]},
    },
    {
        "resource": "memory",
        "limit": {
            "value": 20,
            "unit": "GiB-hours",
        },
        "window": 7,
        "scope": {"group": ["group-1"]},
    },
]

# Usage Quota Service (optional — displays storage usage to users)
# Install with: pip install jupyterhub-usage-quotas[service]

c.UsageViewer.session_secret_key = "use-a-secure-random-key-in-production"

c.JupyterHub.services = [
    {
        "name": "usage-quota",
        "url": "http://localhost:9000",
        "display": False,  # Don't show in Services menu - we have a custom navbar link
        "oauth_no_confirm": True,
        "command": [
            "python",
            "-m",
            "jupyterhub_usage_quotas.services.usage_viewer",
            "--config-file=jupyterhub_config.py",
        ],
    }
]

c.JupyterHub.load_roles = [
    {
        "name": "usage-quota-service",
        "scopes": ["read:users"],
        "services": ["usage-quota"],
    },
    {
        "name": "user",
        "scopes": ["access:services!service=usage-quota", "self"],
    },
]

# Set up common usage quotas config
setup_usage_quotas(c)
