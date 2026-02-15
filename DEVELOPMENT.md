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
   POD_SUBNET=$(kubectl get node minikube -o jsonpath="{.spec.podCIDR}")
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
