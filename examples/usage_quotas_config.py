# Example configuration file for JupyterHub usage quotas.

c = get_config()  # noqa

c.Quotas.server_ip = "127.0.0.1"
c.Quotas.server_port = 8000
c.Quotas.log_level = "DEBUG"

c.QuotasConfig.prometheus_usage_metrics = [
    {"memory": "kube_pod_container_resource_requests{resource='memory'}"},
    {"cpu": "kube_pod_container_resource_requests{resource='cpu'}"},
]
