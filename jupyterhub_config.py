"""
Example configuration file for JupyterHub usage quotas.
"""

import socket

from jupyterhub_usage_quotas.main import SpawnException, UsageQuotaManager

c = get_config()  # noqa

# JupyterHub

c.JupyterHub.ip = "127.0.0.1"
c.JupyterHub.hub_ip = "127.0.0.1"
c.JupyterHub.authenticator_class = "dummy"

# Find private IP address of your local machine that the kubernetes cluster can talk to on your local area network.
# Graciously used from https://stackoverflow.com/a/166589
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.connect(("8.8.8.8", 80))
host_ip = s.getsockname()[0]
s.close()
c.JupyterHub.hub_connect_ip = host_ip

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
        raise SpawnException(log_message=f"{e}")
    if launch_flag is False:
        raise SpawnException(
            log_message="You are over your compute usage quota limit. Please contact your hub admin for assistance."
        )


c.KubeSpawner.pre_spawn_hook = quota_pre_spawn_hook
