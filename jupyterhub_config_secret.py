# Example config file for secret data, e.g. credentials and keys. Make sure you ignore/encrypt this file if using with a version control system.

c.UsageQuotaManager.prometheus_auth = {
    "username": "",
    "password": "",
}

c.UsageViewer.prometheus_auth = {
    "username": "",
    "password": "",
}

c.UsageViewer.session_secret_key = "use-a-secure-random-key-in-production"

c.UsageViewer.hub_api_token = "use-another-secure-random-key-in-production"

c.UsageQuotaManager.metrics_exporter_token = "use-a-secure-random-key-in-production"

c.JupyterHub.services = [
    {
        "name": "metrics-exporter",
        "api_token": c.UsageQuotaManager.metrics_exporter_token,
    },
    {
        # The usage viewer, run as an external service.
        "name": "usage-quota",
        "url": "http://localhost:9000",
        "api_token": c.UsageViewer.hub_api_token,
        "display": True,
        "oauth_no_confirm": True,
    },
]
