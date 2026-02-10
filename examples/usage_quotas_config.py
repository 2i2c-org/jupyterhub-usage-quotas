# Example configuration file for JupyterHub usage quotas.

c = get_config()  # noqa

# Application config

c.QuotasApp.server_ip = "127.0.0.1"
c.QuotasApp.server_port = 8000
c.QuotasApp.log_level = "DEBUG"

# Quota system config

c.Quotas.prometheus_usage_metrics = [
    {"memory": "kube_pod_container_resource_requests{resource='memory'}"},
    {"cpu": "kube_pod_container_resource_requests{resource='cpu'}"},
]

c.Quotas.prometheus_scrape_interval = 15
