# Technical Summary

The configuration for `jupyterhub-usage-quotas` include the following requirements:

- Admins can declaratively define quota limits over a rolling window[^1]
- Quota limits are defined at the user group-level and *individually* applied to members on a per-hub basis
- Prometheus provides a single source of truth for usage metrics
- Consistent usage and quota information can be re-used, e.g. consumed by a user-facing JupyterHub service.

## Input

We apply the design principle of [separating mechanism from policy](https://en.wikipedia.org/wiki/Separation_of_mechanism_and_policy). We avoid mixing *how* the system may apply quotas (mechanism) with *who* and *what* quotas may apply to (policy).

See [](configuration.md#usagequotaconfig) for all possible configuration options.

### Policy configuration

#### Compute quotas

A quota policy for compute can be defined as

```python
c.UsageQuotaManager.policy = [
  {
    "resource": "memory" | "cpu", str,
    "limit": {
        "value": int,
        "unit": str,
    },
    "window": int,
    "scope": {
        "group": [str],
        "user": [str],
        "service": [str],
    }
  }
]
```

This accepts *what* resource the quota applies to, its limit value, and the time period for the rolling window. The scope of *who* the quota applies to mirrors the [JupyterHub RBAC framework](https://jupyterhub.readthedocs.io/en/latest/rbac/index.html), where groups will be the initial target for development.

````{tip} Example
> "Apply a memory quota of 5,000 GiB-hours over 30 days for user group A.”

is expressed as

```python
c.UsageQuotaManager.policy = [
  {
    "resource": "memory",
    "limit": {
      "value": 5000,
      "unit": "GiB-hours",
    },
    "window": 30, # days
    "scope": {
        "group": ["A"]
    }
  }
]
```
````

#### Backup strategy

`c.UsageQuotaManager.scope_backup_strategy` is used to set a quota resolution strategy in the case where the scope of the quota policies cover no users, or applies multiple policies to a single user. In the case where no quota is applied, we can supply a default quota policy or leave this empty for unlimited quotas; and where multiple quotas are applied, we can apply operators `min`, `max` or `sum` to the limit.

````{tip} Example
> “Apply a default memory quota of 500 GiB-hours over a rolling 7 day window for users with no groups, and apply the maximum quota available for users with multiple groups.”

is expressed as

```python
c.UsageQuotaManager.scope_backup_strategy = {
    "empty": {
        "resource": "memory",
        "limit": {"value": 500, "unit": "GiB-hours"},
        "window": 7,
    },
    "intersection": "max",
}
```
````

### Mechanism configuration

This describes *how* the quota system is applied. For example, we can configure the Prometheus metric to track resource usage as memory requests with

```python
c.UsageQuotaManager.prometheus_usage_metrics = {
    "memory": "kube_pod_container_resource_requests{resource='memory'}",
}
```

to be used as an input for the decision logic.

Another example of configuring the quota system mechanism is the case where the quota system fails. We can set `c.UsageQuotaManager.failover_open` to `True` to allow all server launches with no restriction, or to `closed` to deny all server launches to prevent unaccounted compute usage.

## Decision Logic

In this explanation, we constrain compute usage by memory requests to a rolling window of 30 days to demonstrate the decision logic of the quota system.

### Usage metrics

[kube-state-metrics](https://github.com/kubernetes/kube-state-metrics) exports the metric `kube_pod_container_resource_requests`[^2], which measures the amount of compute resources requested by the Kubernetes scheduler in bytes. We can multiply this value by $2^30$ to convert to **GiB**.

### Policy resolver

The policy resolver matches users with policy scopes to determine the quota limit applied. When a user is a member of multiple groups, the configured strategy from `c.UsageQuotaManager.scope_backup_strategy["intersection"]` is applied. When a user is not a member of any group, the system can be configured to default to no quota limits or quota limits specified in `c.UsageQuotaManager.scope_backup_strategy[“empty”]`. In the case where multiple quota policies apply over different rolling windows, then each policy is returned and applied with no limit stacking.

```{tip} Example
`empty`: Backup policy applies to users who are out of scope of policy definitions.

`intersection`: Policy A limits 30 memory hours over the last 30 days to group 1, policy B limits 60 memory hours over the last 30 days to group 1. The policy backup strategy specifies the `max` operator, therefore the policy of `max(30, 60) = 60` memory hours over the last 30 days applies to group 1.

`multiple`:  Policy A limits 30 memory hours over the last 30 days to group 1, policy B limits 7 memory hours over the last 7 days to group 1. Both quota policies are returned (and eventually applied with no limit stacking).
```

### Metric aggregation

Prometheus collects metric samples on a regular basis that can be passed to `c.UsageQuotaManager.scrape_interval`. If the scrape interval is 60 seconds, then over 30 days there will be 43,200 samples. We divide the scrape interval by `60 * 60` to convert to **hours**.

To calculate usage over the last 30 day window, we need to integrate over time for a result independent of the sample granularity:

```sql
sum(sum_over_time(kube_pod_container_resource_requests{resource="memory|cpu"}[30d])) * scrape_interval
```

The result[^3] of the above PromQL pseudo-query is then compared against the each policy quota limit returned by the policy resolver.

If the result is less than the policy limit, then we return `output["allow_server_launch"]=True`. If the result is greater than the policy limit then `output["allow_server_launch"]=False` and a structured error is processed and returned.

### Retry time

With a rolling window, quota expires continuously. When a user exceeds their quota, a useful output to calculate is the `retry_time` so that users know when resources are available again. We can calculate this by projecting the usage window forward in time by an offset until we find the time when the usage falls below the limit again. We can improve the precision of the retry time by performing a binary search with the offset.

## Output

The output of the `jupyterhub-usage-quotas` system is structured as:

```python
output = {
  "allow_server_launch": True | False,
  "error": None | {
    "code": str,
    "message": str,
    "retry_time": str | None
  }
  "quota": {
    "resource": str,
    "used": float,
    "limit": {
       "value": float,
       "unit": str,
     },
    "window": int,
    "scope": {
      "group": [str],
      },
  },
  "timestamp": str,
}
```

This can be consumed by [kubespawner](https://github.com/jupyterhub/kubespawner) with a pre-spawn hook that will launch a server if `allow_server_launch` is `True`. If `allow_server_launch` is `False`, then a response can present information from `error` to the user to explain why a server launch was denied.

[^1]: Compared to monthly limit resets, a rolling window discourages usage spikes at reset time and is fairer to users who join mid-month.

[^2]: From a dollar-cost point of view, requested cloud resources are what providers charge for even if they are under-utilised. This metric is the same one that is used in the memory/cpu requests panel in the User Diagnostics Dashboard of [jupyterhub/grafana-dashboards](https://github.com/jupyterhub/grafana-dashboards).

[^3]: Dimensional analysis: \[sum_over_time(kube_pod_container_resource_requests{resource="memory|cpu"}[30d]) * scrape_interval\] = ( sample * bytes ) * ( time / sample ) = bytes * time = [GiB-hour] ✅
