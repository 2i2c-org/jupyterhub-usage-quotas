# UsageQuotaConfig

(config)=

```
UsageQuotaConfig(LoggingConfigurable) options
---------------------------------------------
--UsageQuotaConfig.bucket_size_seconds=<Int>
    Granularity of usage buckets (seconds).
    Default: 300
--UsageQuotaConfig.failover_open=<Bool>
    In the case where the quota system fails, set to True to default to a fail-
    open (allow all server launches) system or set to False to a fail-closed
    (deny all server launches) system.
    Default: True
--UsageQuotaConfig.policy=<list-item-1>...
    List usage quota policies, including resource, limits, rolling window period
    and policy scope.
    For example: '5,000 GiB-hours over 30 days for group A', is expressed as
    c.UsageQuotaConfig.policy = [{
        "resource": "memory",
        "limit": {
            "value": 5000,
            "unit": "GiB-hours",
        }
        "window": 30, # days
        "scope": {
            "group": ["A"]
        }
    }]
    Default: []
--UsageQuotaConfig.prometheus_scrape_interval=<Int>
    Scrape interval of Prometheus sample collection (seconds).
    Default: 60
--UsageQuotaConfig.prometheus_url=<Unicode>
    The url of the Prometheus server, usually of the form 'http://<k8s-service-
    name>.<k8s-namespace>.svc.cluster.local' in a Kubernetes cluster. Defaults
    to 'http://localhost:9090' for local development if left blank.
    Default: 'http://127.0.0.1:9090'
--UsageQuotaConfig.prometheus_usage_metrics=<key-1>=<value-1>...
    Dict of Prometheus metrics to track usage. Must define at least one of:
        - 'memory': PromQL expression
        - 'cpu': PromQL expression
    For example:
        prometheus_usage_metrics = {
                "memory": "kube_pod_container_resource_requests{resource='memory'}",
                "cpu" : "kube_pod_container_resource_requests{resource='cpu'}"
            }
    Default: {}
--UsageQuotaConfig.sample_interval_seconds=<Int>
    How often usage is sampled by the quota system (seconds).
    Default: 30
--UsageQuotaConfig.scope_backup_strategy=<key-1>=<value-1>...
    Set a backup strategy to resolve quotas in the case where the scope of the
    quota policies are applied to an empty set, or an intersection, i.e. define
    a default when a user has no or multiple quotas applied.
    In the case where no quota is applied ('empty'), we can supply a default
    quota policy or leave this as None for unlimited quotas; and where multiple
    quotas are applied, we can apply either the `min`, `max` or `sum`.
    For example, 'Apply a default memory quota of 500 GiB-hours over a rolling 7
    day window for users with no groups, and apply the maximum quota available
    for users with multiple groups.' is expressed as:
    {
        "empty": {
            "resource": "memory",
            "limit": {
            "value": 500,
            "unit": "GiB-hours"
            },
            "window": 7,
        },
        "intersection": "max"
    }
    Default: {'intersection': 'min'}
```
