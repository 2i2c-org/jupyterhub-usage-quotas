# Development Guide

## Setup

See [Hatch docs](https://hatch.pypa.io/latest/install/) for a general walkthrough.

1. Install hatch globally with pipx

   ```bash
   pipx install hatch
   hatch --version
   ```

1. (Optional) Create hatch environments. You can skip this since environments are automatically created when you run hatch commands in general

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

## Linting & code style

### Pre-commit

In the dev environment, install the hooks and run with

```bash
pre-commit install
```

and manually run against all files with

```bash
pre-commit run --all-files
```

## Running tests

You can run tests for this package using Hatch.

To run the tests on a single python version use:
`hatch run test.py3.14:run`

To run all tests on all python versions use:

`hatch run test:run`

If you are using an IDE like VSCode you can help it find the hatch environment
to support running your tests in the test explorer.

To find the location or your Hatch environments, use:
`hatch env find test`

```bash
/Your/Path/hatch/env/virtual/jupyterhub-usage-quotas/CVSwGsfq/test.py3.12
/Your/Path/hatch/env/virtual/jupyterhub-usage-quotas/CVSwGsfq/test.py3.13
/Your/Path/hatch/env/virtual/jupyterhub-usage-quotas/CVSwGsfq/test.py3.14
```

Then in VSCode, you can select the Hatch environment that you want to use.

You can also enter the environment directly. The command below will open a shell
with the test environment for python 3.14.

`hatch shell test.py3.14`.
