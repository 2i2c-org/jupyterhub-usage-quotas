"""
Traitlets based configuration for jupyterhub_usage_quotas
"""

import copy
import os
import sys
import typing

import jsonschema
from traitlets import Bool, Dict, Integer, List, TraitError, Unicode, default, validate
from traitlets.config import Application

Schema = typing.Dict[str, typing.Any]

# JSON schema for the scope backup policy for usage quotas
policy_schema_backup: Schema = {
    "type": "object",
    "properties": {
        "resource": {"enum": ["memory", "cpu"]},
        "limit": {
            "type": "object",
            "properties": {
                "value": {"type": "number"},
                "unit": {"enum": ["GiB-hours", "CPU-hours"]},
            },
        },
        "window": {"type": "number"},
    },
    "required": ["resource", "limit", "window"],
    "additionalProperties": False,
}

# Add scope to usage quota policy
policy_schema = copy.deepcopy(policy_schema_backup)
policy_schema["properties"].update(
    {
        "scope": {
            "type": "object",
            "properties": {"group": {"type": "array", "items": {"type": "string"}}},
            "additionalProperties": False,
        }
    }
)
policy_schema["required"].append("scope")


class UsageConfig(Application):
    """Base configuration shared across JupyterHub usage quota components."""

    config_file = Unicode("jupyterhub_config.py", help="The config file to load").tag(
        config=True
    )

    @validate("config_file")
    def _validate_config_file(self, proposal):
        if not os.path.isfile(proposal.value):
            print(
                f"ERROR: Failed to find specified config file: {proposal.value}",
                file=sys.stderr,
            )
            sys.exit(1)
        return proposal.value

    prometheus_url = Unicode(
        "http://127.0.0.1:9090",
        help="The url of the Prometheus server, usually of the form 'http://<k8s-service-name>.<k8s-namespace>.svc.cluster.local' in a Kubernetes cluster. Defaults to 'http://127.0.0.1:9090' for local development.",
    ).tag(config=True)

    @default("prometheus_url")
    def _prometheus_url_default(self):
        return os.environ.get(
            "JUPYTERHUB_USAGE_QUOTAS_PROMETHEUS_URL", "http://127.0.0.1:9090"
        )

    prometheus_auth = Dict(
        help="""
        Username and password credentials for authenticating with Prometheus.
        For example:
            c.BaseConfig.prometheus_auth = {
                "username": "username",
                "password": "password",
            }
        """
    ).tag(config=True)

    hub_namespace = Unicode(
        help="Kubernetes namespace of the JupyterHub deployment, used to filter Prometheus usage metrics in multi-tenant environments. Leave empty for single-tenant or development. Can be set via JUPYTERHUB_USAGE_QUOTAS_HUB_NAMESPACE environment variable.",
    ).tag(config=True)

    @default("hub_namespace")
    def _hub_namespace_default(self):
        return os.environ.get("JUPYTERHUB_USAGE_QUOTAS_HUB_NAMESPACE", "")


class UsageQuotaConfig(UsageConfig):
    """
    Configure application settings for the JupyterHub usage quotas system.
    """

    # System config

    prometheus_usage_metrics = Dict(
        help="""
            Dict of Prometheus metrics to track usage. Must define at least one of:
                - 'memory': PromQL expression
                - 'cpu': PromQL expression
            For example:
                prometheus_usage_metrics = {
                        "memory": "kube_pod_container_resource_requests{resource='memory'}",
                        "cpu" : "kube_pod_container_resource_requests{resource='cpu'}"
                    }
        """,
    ).tag(config=True)

    @validate("prometheus_usage_metrics")
    def _validate_prometheus_usage_metrics(self, proposal):
        """
        Validate that memory or cpu usage metrics are defined.
        """
        metrics = proposal["value"]
        if not isinstance(metrics, dict):
            raise TraitError(
                f"Prometheus usage metrics {metrics} must be a dict, got {type(metrics)}"
            )

        for metric_def in metrics:
            if not metric_def in {"memory", "cpu"}:
                raise TraitError(
                    f"Prometheus usage metrics {metrics} must define at least one of 'memory' or 'cpu' keys. Got keys: {list(metrics.keys())}"
                )

        return metrics

    prometheus_scrape_interval = Integer(
        60, help="Scrape interval of Prometheus sample collection (seconds)."
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
        default_value={"intersection": "min"},
        help="""
        Set a backup strategy to resolve quotas in the case where the scope of the quota policies are applied to an empty set, or an intersection, i.e. define a default when a user has no or multiple quotas applied.

        In the case where no quota is applied ('empty'), we can supply a default quota policy or leave this as None for unlimited quotas; and where multiple quotas are applied, we can apply either the `min`, `max` or `sum`.

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
                jsonschema.validate(strategy["empty"], policy_schema_backup)
            except jsonschema.ValidationError as e:
                raise TraitError(e)
        if not strategy["intersection"] in {"min", "max", "sum"}:
            raise TraitError(
                f"Backup strategy for 'intersection' scope must be either 'min', 'max' or 'sum'. Got value: {strategy['intersection']}"
            )

        return strategy

    failover_open = Bool(
        True,
        help="In the case where the quota system fails, set to True to default to a fail-open (allow all server launches) system or set to False to a fail-closed (deny all server launches) system.",
    ).tag(config=True)

    # Policy config

    policy = List(
        Dict(),
        help="""
        List usage quota policies, including resource, limits, rolling window period and policy scope.

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
        """,
    ).tag(config=True)

    @validate("policy")
    def _validate_policy(self, proposal):
        policies = proposal["value"]
        for i, policy_def in enumerate(policies):
            if not isinstance(policy_def, dict):
                raise TraitError(f"Entry {i} must be a dict, got {type(policy_def)}")
            try:
                jsonschema.validate(policy_def, policy_schema)
            except jsonschema.ValidationError as e:
                raise TraitError(e)
        return policies


class UsageViewerConfig(UsageConfig):
    """Configuration for the Usage Viewer service.

    Service-specific settings including Prometheus connection and service binding.
    """

    prometheus_storage_quota_metric = Unicode(
        help="Prometheus metric name for storage quota/hard limit. Defaults to "
        "'dirsize_hard_limit_bytes'. Can be set via "
        "JUPYTERHUB_USAGE_QUOTAS_PROMETHEUS_STORAGE_QUOTA_METRIC environment variable.",
    ).tag(config=True)

    @default("prometheus_storage_quota_metric")
    def _prometheus_storage_quota_metric_default(self):
        return os.environ.get(
            "JUPYTERHUB_USAGE_QUOTAS_PROMETHEUS_STORAGE_QUOTA_METRIC",
            "dirsize_hard_limit_bytes",
        )

    prometheus_storage_usage_metric = Unicode(
        help="Prometheus metric name for current storage usage. Defaults to "
        "'dirsize_total_size_bytes'. Can be set via "
        "JUPYTERHUB_USAGE_QUOTAS_PROMETHEUS_STORAGE_USAGE_METRIC environment variable.",
    ).tag(config=True)

    @default("prometheus_storage_usage_metric")
    def _prometheus_storage_usage_metric_default(self):
        return os.environ.get(
            "JUPYTERHUB_USAGE_QUOTAS_PROMETHEUS_STORAGE_USAGE_METRIC",
            "dirsize_total_size_bytes",
        )

    escape_username_safe_scheme = Bool(
        True,
        help=" Kubespawner slug scheme for naming directories with escaped usernames: set to True for modern safe slugs, or False for legacy escaped slugs.",
    ).tag(config=True)

    dev_mode = Bool(
        False,
        help="""
        Enable development mode with mock data.

        When True, the service returns mock storage usage data instead of querying
        Prometheus. This is useful for local development without a real Prometheus
        instance.

        Mock data is only used when ALL three conditions are met:
        - dev_mode is True, AND
        - prometheus_url is the default (http://127.0.0.1:9090), AND
        - hub_namespace is empty

        If either prometheus_url or hub_namespace is configured, the service
        will query Prometheus even when dev_mode is True.

        Default: False (production mode - always query Prometheus)
        """,
    ).tag(config=True)

    service_port = Integer(
        9000,
        help="Port to bind the usage viewer service to",
    ).tag(config=True)

    service_host = Unicode(
        "0.0.0.0",
        help="Host to bind the usage viewer service to",
    ).tag(config=True)

    service_prefix = Unicode(
        help="URL prefix for the service. Automatically set by JupyterHub when running as a managed service. Defaults to /services/usage-quota.",
    ).tag(config=True)

    @default("service_prefix")
    def _service_prefix_default(self):
        # Try environment variable first (set by JupyterHub)
        prefix = os.environ.get("JUPYTERHUB_SERVICE_PREFIX")
        return prefix or "/services/usage-quota/"

    public_hub_url = Unicode(
        help="Public URL of the JupyterHub instance. Required. Automatically set by JupyterHub via JUPYTERHUB_PUBLIC_HUB_URL environment variable.",
    ).tag(config=True)

    @default("public_hub_url")
    def _public_hub_url_default(self):
        # Try environment variable first (set by JupyterHub)
        url = os.environ.get("JUPYTERHUB_PUBLIC_HUB_URL", "")
        if not url:
            raise TraitError(
                "public_hub_url is required but not set. "
                "Set it via config (c.UsageViewer.public_hub_url) or "
                "JUPYTERHUB_PUBLIC_HUB_URL environment variable."
            )
        return url.rstrip("/")

    session_secret_key = Unicode(
        help="Secret key for session cookie encryption. Required for secure sessions. Set via config or JUPYTERHUB_USAGE_QUOTAS_SESSION_SECRET_KEY environment variable.",
    ).tag(config=True)

    @default("session_secret_key")
    def _session_secret_key_default(self):
        key = os.environ.get("JUPYTERHUB_USAGE_QUOTAS_SESSION_SECRET_KEY", "")
        if not key:
            raise TraitError(
                "session_secret_key is required but not set. "
                "Set it via config (c.UsageViewer.session_secret_key) or "
                "JUPYTERHUB_USAGE_QUOTAS_SESSION_SECRET_KEY environment variable."
            )
        return key
