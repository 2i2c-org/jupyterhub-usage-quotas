# Example configuration file for JupyterHub usage quotas.

c = get_config()  # noqa

c.QuotasApp.log_datefmt = "%Y-%m-%d %H:%M:%S"
c.QuotasApp.log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
c.QuotasApp.log_level = "INFO"


# Quota system config

c.Quotas.prometheus_usage_metrics = [
    {"memory": "kube_pod_container_resource_requests{resource='memory'}"},
    {"cpu": "kube_pod_container_resource_requests{resource='cpu'}"},
]

c.Quotas.prometheus_scrape_interval = 20

c.Quotas.scope_backup_strategy = {
    "empty": {
        "resource": "memory",
        "limit": {"value": 500, "unit": "GiB-hours"},
        "window": 7,
    },
    "intersection": "max",
}

c.Quotas.failover_open = True
