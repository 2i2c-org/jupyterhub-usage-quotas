# Usage Quota Dashboard Service

The usage quota dashboard service (the usage viewer) is a Tornado web application. It shows users their current home storage and compute usage and quotas in JupyterHub.

## How it works

The service:

- Runs as an [external JupyterHub service](https://jupyterhub.readthedocs.io/en/stable/reference/services.html#externally-managed-services), in its own process. On Kubernetes, it runs in its own pod.
- Uses the JupyterHub OAuth flow to identify the user.
- Queries Prometheus for the home storage metrics `dirsize_hard_limit_bytes` and `dirsize_total_size_bytes`. [jupyterhub-home-nfs](https://github.com/2i2c-org/jupyterhub-home-nfs) or an equivalent tool supplies these metrics.
- Queries Prometheus for the compute metrics `jupyterhub_memory_usage_byte_hours_total` and `jupyterhub_memory_limit_byte_hours_total`. The usage quota system in the hub emits these metrics.
- Shows the dashboard as a page with the same look as JupyterHub. The page extends the JupyterHub `page.html` template.

The JupyterHub proxy sends requests for `/services/<service-name>/` to the service. The default service name is `usage-quota`.

### Network traffic

| From             | To               | Purpose                                                            |
| ---------------- | ---------------- | ------------------------------------------------------------------ |
| User's browser   | JupyterHub proxy | Open the dashboard at `/services/usage-quota/`                     |
| JupyterHub proxy | Usage viewer     | Send the dashboard requests to the service                         |
| Usage viewer     | JupyterHub API   | Complete the OAuth flow, and get the user and the list of services |
| Usage viewer     | Prometheus       | Get the usage and quota metrics                                    |
| JupyterHub hub   | Usage viewer     | Check that the service is available                                |

The Helm chart adds a Kubernetes NetworkPolicy. By default, it accepts traffic to the service only from the JupyterHub proxy and hub pods.

## Trust boundary

The hub process does not run the service. This gives the following advantages:

- A problem in the service, for example a crash or high memory use, does not stop the hub.
- The service does not have access to the hub secrets, for example the cookie secret, the database, or the tokens of other services.

The service has only the permissions of its own API token. The configuration in this documentation gives the service the `read:users`, `list:services` and `read:services` scopes. The service uses `list:services` and `read:services` to show the services menu in the navbar.

Users need the `access:services!service=usage-quota` scope to open the dashboard.

The service still has access to the Prometheus metrics of all users. So we should keep the Prometheus credentials of the service in a secret.

## Configuration

We can configure the service in three ways:

- A configuration file, with the `--config-files` flag. The file can be a Python file (`c.UsageViewer.<option> = ...`) or a JSON file (`{"UsageViewer": {...}}`).
- Command line flags.
- Environment variables.

For all options, see the [UsageViewer reference](../reference/configuration.md).

### Environment variables from JupyterHub

JupyterHub sets these environment variables for the services that it starts. An external service must set them itself. The Helm chart sets them.

| Variable                        | Example                                         | Description                                                                                            |
| ------------------------------- | ----------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| `JUPYTERHUB_SERVICE_NAME`       | `usage-quota`                                   | The service name in the JupyterHub configuration                                                       |
| `JUPYTERHUB_CLIENT_ID`          | `service-usage-quota`                           | The OAuth client ID, `service-<service name>`                                                          |
| `JUPYTERHUB_SERVICE_PREFIX`     | `/services/usage-quota/`                        | The URL prefix of the service                                                                          |
| `JUPYTERHUB_API_URL`            | `http://hub:8081/hub/api`                       | The JupyterHub API URL, as the service sees it                                                         |
| `JUPYTERHUB_API_TOKEN`          |                                                 | The `api_token` of the service in the JupyterHub configuration                                         |
| `JUPYTERHUB_PUBLIC_HUB_URL`     | `https://hub.example.org/hub/`                  | The public URL of the hub. Also sets `public_hub_url`.                                                 |
| `JUPYTERHUB_PUBLIC_URL`         | `https://hub.example.org/services/usage-quota/` | (Optional) The public URL of the service. If it starts with `https`, the OAuth state cookie is secure. |
| `JUPYTERHUB_OAUTH_CALLBACK_URL` | `/services/usage-quota/oauth_callback`          | (Optional) The OAuth callback URL. The default is `<prefix>oauth_callback`.                            |

### Environment variables for the usage viewer

| Variable                                      | Description                                                                                                                                                |
| --------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `JUPYTERHUB_USAGE_QUOTAS_SESSION_SECRET_KEY`  | The key that signs the session cookies. If it is not set, the service makes a random key each time it starts, and users must log in again after a restart. |
| `JUPYTERHUB_USAGE_QUOTAS_PROMETHEUS_URL`      | The Prometheus server URL. The default is `http://127.0.0.1:9090`.                                                                                         |
| `JUPYTERHUB_USAGE_QUOTAS_PROMETHEUS_USERNAME` | (Optional) The Prometheus username                                                                                                                         |
| `JUPYTERHUB_USAGE_QUOTAS_PROMETHEUS_PASSWORD` | (Optional) The Prometheus password                                                                                                                         |
| `JUPYTERHUB_USAGE_QUOTAS_HUB_NAMESPACE`       | The Kubernetes namespace of the JupyterHub deployment. The service uses it to filter the metrics. The default is empty.                                    |

### Command line flags

| Flag                   | Option               | Default                    | Description                                                            |
| ---------------------- | -------------------- | -------------------------- | ---------------------------------------------------------------------- |
| `--config-files`       | `config_files`       | `[]`                       | A configuration file to load. The flag can be used more than one time. |
| `--prometheus-url`     | `prometheus_url`     | `http://127.0.0.1:9090`    | The Prometheus server URL                                              |
| `--hub-namespace`      | `hub_namespace`      | `""`                       | The Kubernetes namespace of the JupyterHub deployment                  |
| `--public-hub-url`     | `public_hub_url`     | **(required)**             | The public URL of the hub                                              |
| `--session-secret-key` | `session_secret_key` | A random key at each start | The key that signs the session cookies                                 |
| `--service-prefix`     | `service_prefix`     | `/services/usage-quota/`   | The URL prefix of the service                                          |
| `--port`               | `service_port`       | `9000`                     | The port that the service listens on                                   |
| `--host`               | `service_host`       | `0.0.0.0`                  | The IP address that the service listens on                             |
| `--dev-mode`           | `dev_mode`           | `False`                    | Enable development mode with mock data                                 |

## Deployment

For Kubernetes, use the Helm chart in this repository. It installs the service next to a [Zero to JupyterHub](https://z2jh.jupyter.org/en/stable/) deployment, and sets the environment variables above. See the [Deployment guide](../howto/deploy.md).

To run the service on a local computer for development, see the [Development guide](../contributing/DEVELOPMENT.md).

## Development mode

When we start the service with the `--dev-mode` flag, the service can return randomly generated mock data. This is useful for development without a Prometheus instance.

The service uses mock data only when all of these conditions are true:

1. `dev_mode` is `True`.
1. `prometheus_url` has the default value (`http://127.0.0.1:9090`).
1. `hub_namespace` is empty.

If `prometheus_url` or `hub_namespace` is set, the service queries Prometheus, also when `dev_mode` is `True`.
