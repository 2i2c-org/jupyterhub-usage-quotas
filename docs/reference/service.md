# Usage Quota Service

The usage quota service is an optional FastAPI web application that lets users view their current home storage usage and quota directly within JupyterHub.

## Installation

Install the package with the `service` extra:

```bash
pip install "jupyterhub-usage-quotas[service]"
```

## How it works

The service:

1. Registers as a JupyterHub service and authenticates users via JupyterHub's OAuth2 flow
2. Queries Prometheus for storage metrics using the `dirsize_hard_limit_bytes` and `dirsize_total_size_bytes` metrics (provided by [jupyterhub-home-nfs](https://github.com/2i2c-org/jupyterhub-home-nfs) or equivalent)
3. Displays a usage dashboard embedded in JupyterHub via an iframe to show users their current storage usage and quota

When `PROMETHEUS_NAMESPACE` is not set, the service returns randomly generated mock data, which is useful for development.

## JupyterHub configuration

Add the following to your `jupyterhub_config.py`:

```python
from jupyterhub_usage_quotas import UsageHandler, get_template_path

# Register the custom navbar link and iframe wrapper
c.JupyterHub.extra_handlers = [
    (r"/usage", UsageHandler),
]
c.JupyterHub.template_paths.insert(0, get_template_path())

# Register the service as a JupyterHub-managed subprocess
c.JupyterHub.services = [
    {
        "name": "usage-quota",
        "url": "http://localhost:9000",
        "display": False,  # Don't show the inbuilt service link since we show a standalone link in the navbar
        "oauth_no_confirm": True,
        "oauth_redirect_uri": "/services/usage-quota/oauth_callback",
        "command": [
            "python",
            "-m",
            "jupyterhub_usage_quotas.services.usage_viewer",
            "--port=9000",
            "--prometheus-url=http://<prometheus-host>:9090",
            "--prometheus-namespace=<namespace-of-the-hub>",
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
```

When a `command` is provided, JupyterHub launches and manages the service process automatically, injecting the necessary `JUPYTERHUB_*` environment variables.

## Environment variables

JupyterHub automatically sets the following variables when managing the service as a subprocess:

| Variable | Description |
|---|---|
| `JUPYTERHUB_API_TOKEN` | API token for the Hub |
| `JUPYTERHUB_API_URL` | Internal Hub API URL |
| `JUPYTERHUB_SERVICE_PREFIX` | URL prefix for this service |
| `JUPYTERHUB_PUBLIC_HUB_URL` | Public URL for the Hub (used for constructing OAuth redirect URIs) |

The following variables must be configured manually:

| Variable | Default | Description |
|---|---|---|
| `PROMETHEUS_URL` | `http://prometheus:9090` | Prometheus endpoint |
| `PROMETHEUS_NAMESPACE` | — | Kubernetes namespace to filter metrics by; if unset, returns mock data |
| `SESSION_SECRET_KEY` | random | Secret key for session middleware; set explicitly for stable deployments |
