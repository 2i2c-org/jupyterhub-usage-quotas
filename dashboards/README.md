# Grafana dashboards

Grafana dashboard designs are encoded as jsonnet templates, using a library called [Grafonnet](https://grafana.github.io/grafonnet/index.html).

## Jsonnet library

Manually install the Grafonnet jsonnet library:

1. Clone [https://github.com/grafana/grafonnet.git](https://github.com/grafana/grafonnet.git)

   ```bash
   git clone https://github.com/grafana/grafonnet.git vendor
   ```

   into the parent directory of the `jupyterhub-usage-quotas` folder, and name this folder `vendor` e.g.

   ```bash
   .
   ├── jupyterhub-usage-quotas
   └── vendor
   ```

1. Dashboard jsonnet files can import the Grafonnet library with

   ```python
   #!/usr/bin/env -S jsonnet -J ../../vendor
   local grafonnet = import '../../vendor/gen/grafonnet-v11.4.0/main.libsonnet';
   ```

## Rendering templates

To render the jsonnet templates, which is useful during development, you
can:

1. Clone the [jupyterhub/grafana-dashboards](https://github.com/jupyterhub/grafana-dashboards) repository

1. Change directory to the `grafana-dashboards` cloned repo, and then run:

   ```bash
   jsonnet -J vendor /path/to/jupyterhub-usage-quotas/dashboards/compute-quotas.jsonnet
   ```

## Deployment

These dashboards are deployed using a Python `deploy.py` script from [jupyterhub/grafana-dashboards](https://github.com/jupyterhub/grafana-dashboards) library.

Running this command has a pre-requisite that you have jsonnet installed,
specifically the jsonnet binary built using golang called go-jsonnet.
