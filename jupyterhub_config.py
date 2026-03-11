"""
Example configuration file for JupyterHub usage quotas.
"""

import socket

from jupyterhub_usage_quotas import get_template_path
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
n_users = 3
c.Authenticator.allowed_users = {f"user-{i}" for i in range(n_users)}
c.JupyterHub.load_groups = {
    f"group-{i}": dict(users=[f"user-{i}"]) for i in range(n_users)
}
c.Authenticator.admin_users = {"admin"}

# Usage Quotas

c.UsageQuotaManager.prometheus_usage_metrics = {
    "memory": "kube_pod_container_resource_requests{resource='memory'}",
    # "cpu": "kube_pod_container_resource_requests{resource='cpu'}"
}

c.UsageQuotaManager.prometheus_scrape_interval = 60

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

c.JupyterHub.template_paths = [get_template_path()]

# KubeSpawner

c.JupyterHub.spawner_class = "kubespawner.KubeSpawner"

quota_manager = UsageQuotaManager(config=c)


async def quota_pre_spawn_hook(spawner):
    try:
        output = await quota_manager.enforce(spawner)
        launch_flag = output["allow_server_launch"]
    except Exception:
        raise SpawnException(
            status_code=424,
            log_message="Spawn failed occurred due to a failed dependency in the usage quota system. Please contact your hub admin for assistance.",
        )
    if launch_flag is False:
        raise SpawnException(
            status_code=403,
            log_message=f"{output['error']['message']}",
            html_message=f"<p>Compute {output['quota']['resource']} quota limit exceeded.</p><p style='font-size:100%'>You have used <span style='color:var(--bs-red)'>{output['quota']['used']:.2f}</span> / {output['quota']['limit']['value']:.2f} {output['quota']['limit']['unit']} in the last {output['quota']['window']} days.</p><p style='font-size:100%'>Contact your JupyterHub admin if you need additional quota.</p><i style='font-size:100%;color:var(--bs-gray)'>Last updated: {output["timestamp"]} (UTC).</i>",
        )


c.KubeSpawner.pre_spawn_hook = quota_pre_spawn_hook
