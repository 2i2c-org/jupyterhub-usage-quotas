# Example configuration file for JupyterHub usage quotas.

c = get_config()  # noqa

# Application config

c.QuotasApp.server_ip = "127.0.0.1"
c.QuotasApp.server_port = 8000

c.QuotasApp.log_datefmt = "%Y-%m-%d %H:%M:%S"
c.QuotasApp.log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
c.QuotasApp.log_level = "INFO"

# Quota system config

c.Quotas.prometheus_usage_metrics = [
    {"memory": "kube_pod_container_resource_requests{resource='memory'}"},
    {"cpu": "kube_pod_container_resource_requests{resource='cpu'}"},
]

c.Quotas.prometheus_scrape_interval = 15
