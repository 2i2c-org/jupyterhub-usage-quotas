"""
Example configuration file for JupyterHub usage quotas.
"""

import os
import socket

from jupyterhub_usage_quotas import setup_usage_quotas
from jupyterhub_usage_quotas.manager import SpawnException, UsageQuotaManager
from jupyterhub_usage_quotas.metrics import MetricsExporter

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

# Set up common Usage config
setup_usage_quotas(c)

c.UsageConfig.config_file = os.path.abspath(__file__)
c.UsageConfig.prometheus_auth = {"username": "", "password": ""}
c.UsageConfig.prometheus_url = "http://localhost:9090"
c.UsageConfig.hub_namespace = "staging"

# Usage Viewer Service (optional — displays storage usage to users)
# Install with: pip install jupyterhub-usage-quotas[service]

c.UsageViewer.session_secret_key = "use-a-secure-random-key-in-production"
c.UsageViewer.dev_mode = False
c.UsageViewer.service_port = 9000
c.UsageViewer.service_host = "0.0.0.0"
c.UsageViewer.service_prefix = "/services/usage-quota/"
c.UsageViewer.public_hub_url = "http://localhost:8000"
c.UsageViewer.escape_username_safe_scheme = False


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
            "--UsageConfig.config_file",
            c.UsageConfig.config_file,
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

# Usage Quota Config

c.JupyterHub.spawner_class = "kubespawner.KubeSpawner"

c.UsageQuotaManager.prometheus_usage_metrics = {
    "memory": "kube_pod_container_resource_requests{resource='memory'}",
    # "cpu": "kube_pod_container_resource_requests{resource='cpu'}"
}

c.UsageQuotaManager.prometheus_scrape_interval = 60

c.UsageQuotaManager.hub_namespace = "showcase"

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
            "--port=9000",
            "--public-hub-url=http://localhost:8000",
            "--prometheus-url=http://localhost:9090",
            "--hub-namespace=showcase",
            "--session-secret-key=use-a-secure-random-key-in-production",
            "--dev-mode=true",
        ],
    }
]

c.JupyterHub.load_roles = [
    {
        "name": "usage-quota-service",
        "scopes": ["read:users", "list:users"],
        "services": ["usage-quota"],
    },
    {
        "name": "user",
        "scopes": ["access:services!service=usage-quota", "self"],
    },
]

# KubeSpawner

c.JupyterHub.spawner_class = "kubespawner.KubeSpawner"

quota_manager = UsageQuotaManager(config=c)


async def quota_pre_spawn_hook(spawner):
    try:
        user_name = spawner.user.name
        user_groups = [g.name for g in spawner.user.groups]
        output = await quota_manager.enforce(user_name, user_groups)
        launch_flag = output["allow_server_launch"]
    except Exception as e:
        if c.UsageQuotaManager.failover_open is True:
            launch_flag = True
            quota_manager.log.error(
                f"Usage quota system failed open for user {user_name} with exception: {e}."
            )
        else:
            raise SpawnException(
                status_code=424,
                log_message="Spawn failure occurred due to a failed dependency in the usage quota system. Please contact your hub admin for assistance.",
            )
    if launch_flag is False:
        raise SpawnException(
            status_code=422,
            log_message=f"{output['error']['message']}",
            html_message=f"<p>Compute {output['quota']['resource']} quota limit exceeded.</p><p style='font-size:100%'>You have used <span style='color:var(--bs-red)'>{output['quota']['used']:.2f}</span> / {output['quota']['limit']['value']:.2f} {output['quota']['limit']['unit']} in the last {output['quota']['window']} days.</p><p style='font-size:100%'>Your quota will reset on <b><time datetime='{output['error']['retry_time']}'>{output['error']['retry_time']}</time></b>.</p><p style='font-size:100%'>Contact your JupyterHub admin if you need additional quota.</p><i style='font-size:100%;color:var(--bs-gray)'>Last updated: <time datetime='{output['timestamp']}'>{output["timestamp"]}</time>.</i>",
        )


c.KubeSpawner.pre_spawn_hook = quota_pre_spawn_hook

metrics_exporter = MetricsExporter(quota_manager)

metrics_exporter.start()
