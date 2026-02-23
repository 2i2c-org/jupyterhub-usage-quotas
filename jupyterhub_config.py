"""
Example configuration file for JupyterHub usage quotas.
"""

import pathlib
import secrets
import socket

from jupyterhub_usage_quotas.manager import SpawnException, UsageQuotaManager

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
n_users = 2
c.Authenticator.allowed_users = {f"user-{i}" for i in range(n_users)}
c.JupyterHub.load_groups = {
    f"group-{i}": dict(users=[f"user-{i}"]) for i in range(n_users)
}
c.Authenticator.admin_users = {"admin"}

# Roles and services for local development and testing
c.JupyterHub.load_roles = [
    {
        "name": "usage-quotas-role",
        "scopes": [
            "users",
        ],
        "services": ["usage-quotas-service"],
    },
]

here = pathlib.Path(__file__).parent
token_file = here.joinpath("api_token")
if token_file.exists():
    with token_file.open("r") as f:
        token = f.read()
else:
    token = secrets.token_hex(16)
    with token_file.open("w") as f:
        f.write(token)

c.JupyterHub.services = [
    {
        "name": "usage-quotas-service",
        "api_token": token,
    }
]

# Usage Quotas

c.UsageQuotaManager.prometheus_usage_metrics = {
    "memory": "kube_pod_container_resource_requests{resource='memory'}",
    # "cpu": "kube_pod_container_resource_requests{resource='cpu'}"
}

c.UsageQuotaManager.prometheus_scrape_interval = 20

c.UsageQuotaManager.scope_backup_strategy = {
    "empty": {
        "resource": "memory",
        "limit": {"value": 500, "unit": "GiB-hours"},
        "window": 7,
    },
    "intersection": "max",
}

c.UsageQuotaManager.failover_open = True

c.UsageQuotaManager.policy = [
    {
        "resource": "memory",
        "limit": {
            "value": 5000,
            "unit": "GiB-hours",
        },
        "window": 30,
        "scope": {"group": ["test-group"]},
    },
]

# KubeSpawner

c.JupyterHub.spawner_class = "kubespawner.KubeSpawner"

quota_manager = UsageQuotaManager(config=c)


async def quota_pre_spawn_hook(spawner):
    try:
        launch_flag = await quota_manager.enforce(spawner.user.name)
    except Exception as e:
        raise SpawnException(
            log_message=f"{e}"
        )  # TODO: probably want to restrict what is shown here
    if launch_flag is False:
        raise SpawnException(
            log_message="You are over your compute usage quota limit. Please contact your hub admin for assistance."
        )


c.KubeSpawner.pre_spawn_hook = quota_pre_spawn_hook
