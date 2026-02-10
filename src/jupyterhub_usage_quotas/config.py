from traitlets import Bool, Dict, Integer, List, TraitError, validate
from traitlets.config import Configurable


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
                    f"Entry {i} must define at least one of "
                    f"'memory' or 'cpu'. Got keys: {list(metric_def.keys())}"
                )

        return metrics

    prometheus_scrape_interval = Integer(
        15, help="Scrape interval of Prometheus sample collection (seconds)."
    )

    bucket_size_seconds = Integer(
        300, help="Granularity of usage buckets (seconds)."
    ).tag(config=True)

    sample_interval_seconds = Integer(
        30, help="How often usage is sampled by the quota system (seconds)."
    ).tag(config=True)

    failover_mode = Bool(
        True,
        help="In the case where the quota system fails, set to True to default to a fail-open (allow all server launches) system or set to False to a fail-closed (deny all server launches) system.",
    ).tag(config=True)
