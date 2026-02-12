import jsonschema
from traitlets import Bool, Dict, Integer, List, TraitError, Unicode, validate
from traitlets.config import Configurable

policy_schema = {
    "type": "object",
    "properties": {
        "resource": {"type": "string"},
        "limit": {
            "type": "object",
            "properties": {
                "value": {"type": "number"},
                "unit": {"enum": ["GiB-hours"]},
            },
        },
        "window": {"type": "number"},
    },
    "required": ["resource", "limit", "window"],
}


class Quotas(Configurable):
    """
    Configure application settings for the JupyterHub usage quotas mechanism.
    """

    prometheus_usage_metrics = List(
        Dict(),
        help="""
            List of Prometheus metrics to track usage. Each entry must be a dict defining at least one of:
                - 'memory': PromQL expression
                - 'cpu': PromQL expression
            For example:
                prometheus_usage_metrics = [
                    {
                        "memory": "kube_pod_container_resource_requests{resource='memory'}"
                    },
                    {
                        "cpu" : "kube_pod_container_resource_requests{resource='cpu'}"
                    }
                ]
        """,
    ).tag(config=True)

    @validate("prometheus_usage_metrics")
    def _validate_prometheus_usage_metrics(self, proposal):
        """
        Validate that memory or cpu usage metrics are defined.
        """
        metrics = proposal["value"]
        for i, metric_def in enumerate(metrics):
            if not isinstance(metric_def, dict):
                raise TraitError(f"Entry {i} must be a dict, got {type(metric_def)}")

            if not {"memory", "cpu"} & metric_def.keys():
                raise TraitError(
                    f"Entry {i} must define at least one of 'memory' or 'cpu'. Got keys: {list(metric_def.keys())}"
                )

        return metrics

    prometheus_scrape_interval = Integer(
        15, help="Scrape interval of Prometheus sample collection (seconds)."
    ).tag(config=True)

    bucket_size_seconds = Integer(
        300, help="Granularity of usage buckets (seconds)."
    ).tag(config=True)

    sample_interval_seconds = Integer(
        30, help="How often usage is sampled by the quota system (seconds)."
    ).tag(config=True)

    scope_backup_strategy = Dict(
        per_key_traits={
            "empty": Dict(),
            "intersection": Unicode(),
        },
        help="""
        Set a backup strategy to resolve quotas in the case where the scope of the quota policies are applied to an empty set, or an intersection, i.e. define a default when a user has no or multiple quotas applied.

        In the case where no quota is applied ('empty'), we can supply a default quota policy or leave this as None for unlimited quotas; and where multiple quotas are applied, we can apply either the `min` or `max`.

        For example, 'Apply a default memory quota of 500 GiB-hours over a rolling 7 day window for users with no groups, and apply the maximum quota available for users with multiple groups.' is expressed as:

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
        """,
    ).tag(config=True)

    @validate("scope_backup_strategy")
    def _validate_scope_backup_strategy(self, proposal):
        """
        Validate that the scope backup strategy is defined.
        """
        strategy = proposal["value"]
        required = set(["intersection"])
        allowed = required | set(["empty"])
        if required - set(strategy.keys()):
            raise TraitError(
                f"Must define backup strategy for 'intersection' scope. Got keys: {list(strategy.keys())}"
            )
        extra = set(strategy.keys()) - allowed
        if extra:
            raise TraitError(f"Unexpected keys: {extra}")
        if "empty" in strategy.keys():
            try:
                jsonschema.validate(strategy["empty"], policy_schema)
            except jsonschema.ValidationError as e:
                raise TraitError(e)
        if not strategy["intersection"] in {"min", "max"}:
            raise TraitError(
                f"Backup strategy for 'intersection' scope must be either 'min' or 'max'. Got value: {strategy['intersection']}"
            )

        return strategy

    failover_open = Bool(
        True,
        help="In the case where the quota system fails, set to True to default to a fail-open (allow all server launches) system or set to False to a fail-closed (deny all server launches) system.",
    ).tag(config=True)
