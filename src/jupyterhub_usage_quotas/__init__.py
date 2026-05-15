import os

from prometheus_client import REGISTRY, Counter

from jupyterhub_usage_quotas.handler import UsageHandler
from jupyterhub_usage_quotas.manager import SpawnException, UsageQuotaManager
from jupyterhub_usage_quotas.metrics import MetricsExporter

__all__ = ["get_template_path", "UsageHandler"]


def get_template_path():
    """Get the path to the templates directory."""
    return os.path.join(os.path.dirname(__file__), "templates")


def setup_usage_quotas(c):
    """
    Setup common config to enable the usage quotas system.

    Expects to be called from a `jupyterhub_config.py` file, with `c`
    the config object being passed in.
    """

    c.JupyterHub.template_paths.insert(0, get_template_path())

    c.JupyterHub.extra_handlers.append((r"/usage", UsageHandler))

    c.JupyterHub.spawner_class = "kubespawner.KubeSpawner"

    c.UsageQuotaManager.prometheus_usage_metrics = {
        "memory": "kube_pod_container_resource_requests{resource='memory'}",
        # "cpu": "kube_pod_container_resource_requests{resource='cpu'}"
    }

    quota_manager = UsageQuotaManager(config=c)

    FAIL_OPEN_TOTAL = Counter(
        f"{quota_manager.prometheus_emit_namespace}_usage_quotas_fail_open_total",
        "Number of fail open instances from the usage quota system",
        ["namespace", "username"],
        registry=REGISTRY,
    )

    async def quota_pre_spawn_hook(spawner):
        try:
            user_name = spawner.user.name
            user_groups = [g.name for g in spawner.user.groups]
            output = await quota_manager.enforce(user_name, user_groups)
            launch_flag = output["allow_server_launch"]
        except Exception as e:
            if quota_manager.failover_open is True:
                launch_flag = True
                FAIL_OPEN_TOTAL.labels(
                    namespace=quota_manager.hub_namespace, username=user_name
                ).inc()
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

    # Start Prometheus metrics exporter
    metrics_exporter = MetricsExporter(quota_manager)
    metrics_exporter.start()
