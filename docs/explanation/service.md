# Usage Quota Dashboard Service

The usage quota dashboard service is an optional Tornado web application that lets users view their current home storage usage and quota directly within JupyterHub.

## Installation

Install the package with the `service` extra:

```bash
pip install "jupyterhub-usage-quotas[service]"
```

## How it works

The service:

- Registers as a JupyterHub service and authenticates users via JupyterHub's OAuth2 flow
- Queries Prometheus for storage metrics using the `dirsize_hard_limit_bytes` and `dirsize_total_size_bytes` metrics (provided by [jupyterhub-home-nfs](https://github.com/2i2c-org/jupyterhub-home-nfs) or equivalent)
- Queries Prometheus for compute metrics using the `jupyterhub_memory_usage_gibibyte_hours` and `jupyterhub_memory_limit_gibibyte_hours` (provided by [jupyterhub-usage-quotas](https://github.com/2i2c-org/jupyterhub-usage-quotas))
- Displays a usage dashboard embedded in JupyterHub via an iframe to show users their current usage and quota

When `dev_mode` is enabled (via `--dev-mode` flag), the service can return randomly generated mock data, which is useful for development without a Prometheus instance. Mock data is only used when ALL three conditions are met: (1) `dev_mode` is True, AND (2) `prometheus_url` is the default (`http://127.0.0.1:9090`), AND (3) hub_namespace is empty. If either `prometheus_url` or hub_namespace is configured, the service will query Prometheus even when `dev_mode` is `True`.

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
            "--public-hub-url=<your-public-hub-url>",
            "--prometheus-url=http://<prometheus-host>:9090",
            "--hub-namespace=<namespace-of-the-hub>",
            "--session-secret-key=<your-secret-key>",
            # Optional: Enable development mode for mock data
            # "--dev-mode",
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

## Configuration

The service is configured via CLI flags (preferred) or traitlet configuration:

| CLI Flag               | Config Attribute     | Default                 | Description                                                               |
| ---------------------- | -------------------- | ----------------------- | ------------------------------------------------------------------------- |
| `--prometheus-url`     | `prometheus_url`     | `http://127.0.0.1:9090` | Prometheus server endpoint                                                |
| `--hub-namespace`      | `hub_namespace`      | `""`                    | Kubernetes namespace of the JupyterHub deployment, used to filter metrics |
| `--dev-mode`           | `dev_mode`           | `False`                 | Enable development mode with mock data                                    |
| `--port`               | `service_port`       | `9000`                  | Port to bind the service to                                               |
| `--host`               | `service_host`       | `0.0.0.0`               | Host to bind the service to                                               |
| `--session-secret-key` | `session_secret_key` | **(required)**          | Secret key for session cookie encryption                                  |
| `--public-hub-url`     | `public_hub_url`     | **(required)**          | Public URL of the JupyterHub instance                                     |

### Environment variables

All configuration options can be set via environment variables as alternatives to CLI flags:

| Variable                                      | Description                                                                                |
| --------------------------------------------- | ------------------------------------------------------------------------------------------ |
| `JUPYTERHUB_PUBLIC_HUB_URL`                   | Public URL of the JupyterHub instance **(required)**                                       |
| `JUPYTERHUB_USAGE_QUOTAS_SESSION_SECRET_KEY`  | Secret key for session cookie encryption **(required)**                                    |
| `JUPYTERHUB_USAGE_QUOTAS_PROMETHEUS_URL`      | Prometheus server endpoint (default: `http://127.0.0.1:9090`)                              |
| `JUPYTERHUB_USAGE_QUOTAS_PROMETHEUS_USERNAME` | (Optional) Prometheus server username                                                      |
| `JUPYTERHUB_USAGE_QUOTAS_PROMETHEUS_PASSWORD` | (Optional) Prometheus server password                                                      |
| `JUPYTERHUB_USAGE_QUOTAS_HUB_NAMESPACE`       | Kubernetes namespace of the JupyterHub deployment, used to filter metrics (default: empty) |
