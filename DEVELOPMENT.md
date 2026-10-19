# Development Guide

## Setup Hatch

See [Hatch docs](https://hatch.pypa.io/latest/install/) for a general walkthrough.

1. Install hatch globally with `pipx`

   ```bash
   pipx install hatch
   hatch --version
   ```

1. (Optional) Create hatch environments. You can skip this step since environments are automatically created when you run hatch commands in general

   ```bash
   hatch env create
   ```

1. Spawn a shell in the default hatch environment

   ```bash
   hatch shell
   ```

   or spawn a shell in a specific environment, e.g. `dev` for local development

   ```bash
   hatch shell dev
   ```

   Use `exit` to exit the shell environment.

## Local development environment

You can run JupyterHub on your local machine that can communicate with pods in a Kubernetes cluster.

1. Install [minikube](https://kubernetes.io/docs/tasks/tools/install-minikube/)
   with a container manager such as [docker](https://minikube.sigs.k8s.io/docs/drivers/docker/). If you are using macOS, then instead of minikube you may need to run a kubernetes cluster with a docker daemon inside a virtual machine manager such as [colima](https://colima.run/), e.g. `colima start --kubernetes --network-address`.

1. Get the kubernetes pod subnet range – for minikube, run

   ```bash
   export POD_SUBNET=$(kubectl get node minikube -o jsonpath="{.spec.podCIDR}")
   ```

   or for colima run

   ```bash
   export POD_SUBNET=$(kubectl get node colima -o jsonpath="{.spec.podCIDR}")
   ```

1. Get gateway IP address of the kubernetes cluster – for minikube, run

   ```bash
   export GATEWAY_IP=$(minikube ip)
   ```

   or for colima, get the virtual machine IP address with

   ```bash
   export GATEWAY_IP=$(colima ssh -- hostname -I | awk '{print $2}')
   ```

   ```{note}
   Note that for more recent macOS versions there appears to be a networking bug in `colima`. A workaround is to edit `~/.kube/config` so that the server address for the `colima` cluster from `https://192.168.64.2:<port number>` to `https://127.0.0.1:<port number>` and `export GATEWAY_IP=127.0.0.1`. See [upstream issue](https://github.com/abiosoft/colima/issues/1339).
   ```

1. Add a route for your local host to reach the the pod subnet via the gateway IP address

   ```bash
   # Linux
   sudo ip route add $POD_SUBNET via $GATEWAY_IP
   # later on you can undo this with
   sudo ip route del $POD_SUBNET

   # MACOS
   sudo route -n add -net $POD_SUBNET $GATEWAY_IP
   # later on you can undo this with
   sudo route delete -net $POD_SUBNET
   ```

1. Spawn a shell in the local development environment

   ```bash
   hatch shell dev
   ```

1. Run jupyterhub with the command

   ```bash
   jupyterhub
   ```

## Running the usage viewer service locally

The usage viewer (the usage quota dashboard) runs as an [external JupyterHub service](https://jupyterhub.readthedocs.io/en/stable/reference/services.html#externally-managed-services), in a separate process. `jupyterhub_config_secret.py` registers it at `http://localhost:9000`.

1. In a terminal, start JupyterHub as described in the previous section.

1. In a second terminal, spawn a shell in the local development environment

   ```bash
   hatch shell dev
   ```

1. Start the usage viewer service

   ```bash
   python -m jupyterhub_usage_quotas.services.usage_viewer \
     --config-files=usage_viewer_config.py \
     --config-files=jupyterhub_config_secret.py
   ```

   JupyterHub sets the `JUPYTERHUB_*` environment variables for the services that it starts. An external service must set them itself. `usage_viewer_config.py` sets these variables. If you change the `api_token` of the `usage-quota` service in `jupyterhub_config_secret.py`, change `JUPYTERHUB_API_TOKEN` in `usage_viewer_config.py` to the same value.

1. Go to http://localhost:8000, log in, and click **Services > usage-quota** in the navbar.

The usage viewer configuration is in `usage_viewer_config.py`. The secrets for both JupyterHub and the usage viewer are in `jupyterhub_config_secret.py`.

### Using mock data for local development

To use mock data without a real Prometheus instance, add the `--dev-mode` flag to the command that starts the usage viewer service:

```bash
python -m jupyterhub_usage_quotas.services.usage_viewer \
  --config-files=usage_viewer_config.py \
  --config-files=jupyterhub_config_secret.py \
  --dev-mode
```

Alternatively, set `c.UsageViewer.dev_mode = True` in `usage_viewer_config.py`.

The service returns randomly generated mock data only when `dev_mode` is enabled and both `hub_namespace` and `prometheus_url` have their default values. `usage_viewer_config.py` sets `hub_namespace`, so remove that line to use mock data.

## Running hatch scripts

See the `scripts` in [pyproject.toml](https://github.com/2i2c-org/jupyterhub-usage-quotas/blob/main/pyproject.toml) to see the configured commands available to `hatch run <env>:<command>`.

### Interact with usage quotas library

Run the CLI app with

```bash
hatch run jupyterhub_usage_quotas --config jupyterhub_config.py
```

### Build/serve documentation

To run a live server:

```bash
hatch run docs:serve
```

To build html:

```bash
hatch run docs:build
```

### Update the configuration reference

The pages `UsageQuotaManager.md`, `UsageViewer.md` and `helm-chart.md` in `docs/reference` are generated from the traitlets configuration and from the Helm chart's `values.schema.yaml` and `values.yaml`. When we change a configuration option or a chart value, we regenerate the pages and commit them with the change:

```bash
hatch run docs:python docs/scripts/update_configuration_reference.py
```

The docs build also runs this script. CI fails if the committed pages are not up to date.

### Run tests

To run all tests on all python versions use:

```bash
hatch run test:run
```

To run the tests on a single python version use:

```bash
hatch run test.py3.14:run
```

To open a shell with the test environment for python 3.14, run

```bash
hatch shell test.py3.14
```

## Linting and code style

### Pre-commit

We use pre-commit to automatically apply linting and code style checks when a `git commit` is made. See the configuration in the [.pre-commit-config.yaml](https://github.com/2i2c-org/jupyterhub-usage-quotas/blob/main/.pre-commit-config.yaml) file.

In the `dev` shell, you can install the hooks and run with

```bash
pre-commit install
```

and optionally, you can manually run this against all files with

```bash
pre-commit run --all-files
```
