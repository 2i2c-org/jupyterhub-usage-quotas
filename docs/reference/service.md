# Usage Quota Service

The usage quota service is an optional FastAPI web application that lets users view their current home storage usage and quota directly within JupyterHub.

## Installation

Install the package with the `service` extra:

```bash
pip install "jupyterhub-usage-quotas[service]"
```

## How it works

The service:

1. Registers as a JupyterHub external service and authenticates users via JupyterHub's OAuth2 flow
2. Queries Prometheus for storage metrics using the `dirsize_hard_limit_bytes` and `dirsize_total_size_bytes` metrics (provided by [jupyterhub-home-nfs](https://github.com/yuvipanda/jupyterhub-home-nfs) or equivalent)
3. Displays a usage dashboard embedded in JupyterHub via an iframe

When `PROMETHEUS_NAMESPACE` is not set, the service returns randomly generated mock data, which is useful for development.

## JupyterHub configuration

Add the following to your `jupyterhub_config.py`:

```python
from jupyterhub_usage_quotas import UsageHandler, get_template_path

# Register the custom navbar link and iframe wrapper
c.JupyterHub.extra_handlers = [
    (r"/usage", UsageHandler),
]
c.JupyterHub.template_paths = [get_template_path()]

# Register the service as a JupyterHub-managed subprocess
c.JupyterHub.services = [
    {
        "name": "usage-quota",
        "url": "http://localhost:9000",
        "display": False,
        "oauth_client_id": "service-usage-quota",
        "oauth_no_confirm": True,
        "oauth_redirect_uri": "https://<hub-url>/services/usage-quota/oauth_callback",
        "command": ["fastapi", "run", "/path/to/jupyterhub_usage_quotas/service/app.py", "--port", "9000"],
    }
]

c.JupyterHub.load_roles = [
    {
        "name": "usage-quota-service",
        "scopes": ["read:users", "read:servers", "list:users"],
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
| `JUPYTERHUB_SERVICE_NAME` | Service name (sets OAuth client ID) |

The following variables must be configured manually:

| Variable | Default | Description |
|---|---|---|
| `JUPYTERHUB_EXTERNAL_URL` | `http://localhost:8000` | Public Hub URL (used in OAuth redirects) |
| `PROMETHEUS_URL` | `http://prometheus:9090` | Prometheus endpoint |
| `PROMETHEUS_NAMESPACE` | — | Kubernetes namespace to filter metrics by; if unset, returns mock data |
| `SESSION_SECRET_KEY` | random | Secret key for session middleware; set explicitly for stable deployments |
