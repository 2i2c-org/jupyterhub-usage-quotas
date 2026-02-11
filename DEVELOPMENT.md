# Development Guide

## Setup

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

## Running scripts

See the `scripts` in [pyproject.toml](https://github.com/2i2c-org/jupyterhub-usage-quotas/blob/main/pyproject.toml) to see the configured commands available to `hatch run <env>:<command>`.

### Interact with usage quotas library

Run the CLI app with

```bash
hatch run jupyterhub_usage_quotas --config examples/usage_quotas_config.py
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
