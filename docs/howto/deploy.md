# Deployment guide

## Deployment

See the [Admins](#admins) section in the [Getting Started](./quickstart.md) page for a quick-start guide to deploying `jupyterhub-usage-quotas` in a [Zero to JupyterHub](https://z2jh.jupyter.org/en/stable/) context.

## Monitoring and Alerting

The [Usage Quota Dashboard](./usage-quota-dashboard.md) makes use of Prometheus metrics exported by the usage quota system. You can use the same metrics to configure your own monitoring and alerting systems to detect events such as:

- Cumulative compute usage

  ```sql
  # PromQL
  max(jupyterhub_memory_usage_gibibyte_hours{namespace=~"$hub"}) by (namespace, username, policy_group, window)
  ```

- Number of fail opens

  ```sql
  # PromQL
  sum by (namespace) (changes(jupyterhub_usage_quotas_fail_open_total[30m]))
  ```

- Denied server launches over the last 30 minutes

  ```sql
  # PromQL
  changes((max by (namespace) (jupyterhub_request_duration_seconds_count{code="422",handler="jupyterhub.handlers.pages.SpawnPendingHandler"} or 0 * jupyterhub_request_duration_seconds_count))[30m:1m])
  ```

## Tips

- The `jupyterhub-usage-quotas` library is installed within the hub image, so make sure that you give enough memory and compute [requests and limits](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/) for the kubernetes pod to work
  - You may have to fine-tune this over time, since the memory used by the usage quota system scales weakly with the number of hub users
