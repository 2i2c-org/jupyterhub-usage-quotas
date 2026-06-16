"""
Example configuration file for JupyterHub usage quotas.
"""

import socket

from jupyterhub_usage_quotas import setup_usage_quotas

c = get_config()  # noqa

load_subconfig("jupyterhub_config_secret.py")  # noqa

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

c.JupyterHub.spawner_class = "kubespawner.KubeSpawner"


def my_hook(spawner):
    username = spawner.user.name
    spawner.environment["GREETING"] = f"Hello {username}"


c.Spawner.pre_spawn_hook = my_hook

# Usage Quotas

c.UsageConfig.hub_namespace = "staging"
c.UsageConfig.hub_url = "http://localhost:8000"

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

c.UsageViewer.public_hub_url = "http://localhost:8000"
c.UsageViewer.hub_template_paths = c.JupyterHub.template_paths

c.JupyterHub.services.append(
    {
        "name": "usage-quota",
        "url": "http://localhost:9000",
        "display": True,
        "oauth_no_confirm": True,
        "command": [
            "python",
            "-m",
            "jupyterhub_usage_quotas.services.usage_viewer",
            "--config-files=jupyterhub_config.py",
            "--config-files=jupyterhub_config_secret.py",
        ],
    }
)

c.JupyterHub.load_roles = [
    {
        "name": "usage-quota-role",
        "scopes": ["read:users", "list:services", "read:services"],
        "services": ["usage-quota"],
    },
    {
        "name": "user",
        "scopes": ["access:services!service=usage-quota", "self"],
    },
    {
        "name": "metrics-exporter-role",
        "scopes": ["users"],
        "services": ["metrics-exporter"],
    },
]

# Set up usage quotas config
setup_usage_quotas(c)
