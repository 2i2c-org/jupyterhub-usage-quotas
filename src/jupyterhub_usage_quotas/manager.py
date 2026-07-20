import datetime
import itertools
import logging
import os
import re
import typing
from collections import defaultdict

import jsonschema
from kubespawner.slugs import escape_slug, safe_slug
from tornado import web
from traitlets import Bool, Dict, Integer, List, TraitError, Unicode, default, validate
from traitlets.config import LoggingConfigurable

from jupyterhub_usage_quotas.client import PrometheusClient
from jupyterhub_usage_quotas.schemas import policy_schema, policy_schema_fallback


class UsageQuotaManager(LoggingConfigurable):
    """Class for enforcing compute usage quotas."""

    prometheus_url = Unicode(
        "http://127.0.0.1:9090",
        help="""
        The url of the Prometheus server, usually of the form 'http://<k8s-service-name>.<k8s-namespace>.svc.cluster.local' in a Kubernetes cluster. Defaults to 'http://127.0.0.1:9090' for local development.
        """,
    ).tag(config=True)

    @default("prometheus_url")
    def _prometheus_url_default(self):
        return os.environ.get(
            "JUPYTERHUB_USAGE_QUOTAS_PROMETHEUS_URL", "http://127.0.0.1:9090"
        )

    prometheus_auth = Dict(
        per_key_traits={"username": Unicode(), "password": Unicode()},
        help="""
        Username and password credentials for authenticating with Prometheus.
        Can be set via JUPYTERHUB_USAGE_QUOTAS_PROMETHEUS_USERNAME and
        JUPYTERHUB_USAGE_QUOTAS_PROMETHEUS_PASSWORD environment variables.
        For example:
            c.UsageConfig.prometheus_auth = {
                "username": "username",
                "password": "password",
            }
        """,
    ).tag(config=True)

    @default("prometheus_auth")
    def _prometheus_auth_default(self):
        username = os.environ.get("JUPYTERHUB_USAGE_QUOTAS_PROMETHEUS_USERNAME", "")
        password = os.environ.get("JUPYTERHUB_USAGE_QUOTAS_PROMETHEUS_PASSWORD", "")
        if username and password:
            return {"username": username, "password": password}
        if username or password:
            raise TraitError(
                "Both JUPYTERHUB_USAGE_QUOTAS_PROMETHEUS_USERNAME and "
                "JUPYTERHUB_USAGE_QUOTAS_PROMETHEUS_PASSWORD must be set together."
            )
        return {}

    @validate("prometheus_auth")
    def _validate_prometheus_auth(self, proposal):
        auth = proposal["value"]
        if not auth:
            return auth
        required = set(self.traits()["prometheus_auth"]._per_key_traits.keys())
        missing = required - auth.keys()
        if missing:
            expected = {k: "..." for k in sorted(required)}
            raise TraitError(
                f"prometheus_auth is missing required keys: {sorted(missing)}. "
                f"Expected: {expected}"
            )
        return auth

    hub_url = Unicode(
        help="JupyterHub URL, e.g. http://localhost:8000 for local development."
    ).tag(config=True)

    @default("hub_url")
    def _hub_url_default(self):
        return f"http://{os.environ.get('HUB_SERVICE_HOST')}:{os.environ.get('HUB_SERVICE_PORT')}"

    hub_namespace = Unicode(
        help="Kubernetes namespace of the JupyterHub deployment, used to filter Prometheus usage metrics in multi-tenant environments. Leave empty for single-tenant or development. Can be set via JUPYTERHUB_USAGE_QUOTAS_HUB_NAMESPACE environment variable.",
    ).tag(config=True)

    @default("hub_namespace")
    def _hub_namespace_default(self):
        return os.environ.get("JUPYTERHUB_USAGE_QUOTAS_HUB_NAMESPACE", "")

    escape_username_scheme = Dict(
        per_key_traits={
            "directory": Unicode(),
            "pod": Unicode(),
            "max_length": Integer(),
        },
        help="""
        Kubespawner slug scheme for naming directories and pod names with escaped usernames. E.g
            - modern safe slugs for k8s pods and legacy slug for directory names (default): {"directory": "legacy", pod": "safe", max_length: 48},
        """,
    ).tag(config=True)

    @default("escape_username_scheme")
    def _escape_username_scheme_default(self):
        return {"directory": "legacy", "pod": "safe", "max_length": 48}

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

    prometheus_emit_interval = Integer(
        60, help="Emit interval of Prometheus metric export (seconds)."
    ).tag(config=True)

    prometheus_emit_namespace = Unicode(
        "jupyterhub", help="Prometheus namespace to prefix metric names."
    ).tag(config=True)

    metrics_exporter_token = Unicode(
        help="API token to authenticate requests from metrics exporter."
    ).tag(config=True)

    scope_fallback_strategy = Dict(
        per_key_traits={
            "empty": Dict(),
            "intersection": Unicode(),
        },
        default_value={"intersection": "min"},
        help="""
        Set a fallback strategy to resolve quotas in the case where the scope of the quota policies are applied to an empty set, or an intersection, i.e. define a default when a user has no or multiple quotas applied.

        In the case where no quota is applied ('empty'), we can supply a default quota policy or leave this as None for unlimited quotas; and where multiple quotas are applied, we can apply either the `min`, `max` or `sum`.

        For example, 'Apply a default memory quota of 500 GiB-hours over a rolling 7 day window for users with no groups, and apply the maximum quota available for users with multiple groups.' is expressed as:

        {
            "empty": {
                "resource": "memory",
                "limit": "500G",
                "window": 7,
            },
            "intersection": "max"
        }
        """,
    ).tag(config=True)

    @validate("scope_fallback_strategy")
    def _validate_scope_fallback_strategy(self, proposal):
        """
        Validate that the scope fallback strategy is defined.
        """
        strategy = proposal["value"]
        required = set(["intersection"])
        allowed = required | set(["empty"])
        if required - set(strategy.keys()):
            raise TraitError(
                f"Must define fallback strategy for 'intersection' scope. Got keys: {list(strategy.keys())}"
            )
        extra = set(strategy.keys()) - allowed
        if extra:
            raise TraitError(f"Unexpected keys: {extra}")
        if "empty" in strategy.keys():
            try:
                jsonschema.validate(strategy["empty"], policy_schema_fallback)
            except jsonschema.ValidationError as e:
                raise TraitError(e)
            self._validate_policy_limit(strategy["empty"]["limit"])
        if not strategy["intersection"] in {"min", "max", "sum"}:
            raise TraitError(
                f"Fallback strategy for 'intersection' scope must be either 'min', 'max' or 'sum'. Got value: {strategy['intersection']}"
            )

        return strategy

    failover_open = Bool(
        True,
        help="In the case where the quota system fails, set to True to default to a fail-open (allow all server launches) system or set to False to a fail-closed (deny all server launches) system.",
    ).tag(config=True)

    # Policy config

    def _validate_policy_limit(self, value: typing.Union[int, str]):
        """Validate policy limits are formatted nX where n is an integer and X is an optional [KMGT] unit prefix to denote kilo-, mega-, giga- and tera-."""
        if type(value) is str:
            pattern = re.compile(r"^\d+[KMGT]$", re.IGNORECASE)
            if not pattern.match(value):
                raise TraitError(
                    f"Policy limit {value} is not valid. Must be an integer or a string with optional suffix K, M, G, T."
                )

    policy = List(
        Dict(),
        help="""
        List usage quota policies, including resource, limits, rolling window period and policy scope.

        For example: '5,000 GiB-hours over 30 days for group A', is expressed as

        c.UsageQuotaConfig.policy = [{
            "resource": "memory",
            "limit": "5000G",
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
            self._validate_policy_limit(policy_def["limit"])
        return policies

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        parent_log = logging.getLogger("JupyterHub")
        self.log = logging.getLogger(__name__)
        self.log.parent = parent_log
        self.prometheus_client = PrometheusClient(
            self.prometheus_url, self.prometheus_auth
        )
        self.UNIT_SUFFIXES = {
            "K": 1024,
            "M": 1024**2,
            "G": 1024**3,
            "T": 1024**4,
        }
        self.seconds_to_hours = 60**2

    @staticmethod
    def convert_memory_to_bytes(policy: dict, unit_suffixes: dict) -> dict:
        if type(policy["limit"]) is str:
            n = int(re.findall("[0-9]+", policy["limit"])[0])
            s = re.findall("[a-zA-Z]+", policy["limit"])[0]
            policy["limit"] = n * unit_suffixes[s]
            policy["unit"] = s
        return policy

    def convert_bytes_to_memory(self, policy: dict) -> dict:
        if policy["unit"]:
            policy["limit"] = policy["limit"] / self.UNIT_SUFFIXES[policy["unit"]]
        return policy

    def resolve_empty(self) -> list:
        """
        Resolve quota policy for users with no group memberships.
        """
        policy_empty: list = []
        if "empty" not in self.scope_fallback_strategy.keys():
            self.log.debug("No fallback policy found.")
            return policy_empty
        if isinstance(self.scope_fallback_strategy["empty"], dict):
            policy_empty.append(self.scope_fallback_strategy["empty"])
        return policy_empty

    def resolve_intersection(self, values: list[dict], operator: str) -> list:
        """
        Resolve quota policy for users with multiple policies applied.

        Apply min/max/sum operators to merge policies sharing the same resource over the same rolling window for the same groups.
        """

        limits = [v["limit"] for v in values]

        if operator == "min":
            combined_value = min(limits)
        elif operator == "max":
            combined_value = max(limits)
        elif operator == "sum":
            combined_value = sum(limits)
        else:
            raise ValueError(f"Operator must be one of: min, max, sum, got {operator}")

        return combined_value

    def resolve_policy(self, user_name: str, user_groups: list) -> list:
        """
        Resolve and merge group quota policies that apply to the user.

        Example 1 - empty: fallback policy applies to users who are out of scope of policy definitions.

        Example 2 - intersection: Policy A limits 30 memory hours over the last 30 days to group 1, policy B limits 60 memory hours over the last 30 days to group 1. The policy fallback strategy specifies the 'max' operator, therefore the policy of max(30, 60) = 60 memory hours over the last 30 days applies to group 1.

        Example 3 - multiple:  Policy A limits 30 memory hours over the last 30 days to group 1, policy B limits 7 memory hours over the last 7 days to group 1. Both quota policies are returned (and eventually applied with no limit stacking).
        """
        self.log.debug(f"User {user_name} is a member of groups: {user_groups}")
        # Find policies applied to user group
        policies = [
            p for p in self.policy if set(user_groups) & set(p["scope"]["group"])
        ]
        # Standardise memory units to pure bytes
        policies = [
            self.convert_memory_to_bytes(p, self.UNIT_SUFFIXES)
            for p in policies
            if p["resource"] == "memory"
        ]
        self.log.debug(f"{policies=}")

        # Group policies with common keys together, e.g. the same resources and rolling windows.
        grouped = defaultdict(list)
        for p in policies:
            key = (
                p["resource"],
                p["window"],
            )
            grouped[key].append(p)

        merged = []
        if len(policies) == 1:
            self.log.debug("Resolve single policy")
            merged.append(next(iter(grouped.values()))[0])
        elif len(policies) == 0:
            self.log.debug("Resolve empty policy")
            merged = self.resolve_empty()
        elif len(policies) >= 1:
            self.log.debug("Resolve multiple policies")
            for (resource, window), values in grouped.items():
                combined_value = self.resolve_intersection(
                    values, self.scope_fallback_strategy["intersection"]
                )
                merged_groups = set()
                for v in values:
                    merged_groups.update(v["scope"].get("group", []))
                    # Pass through memory units to merged policies if it exists
                    if "unit" in v.keys():
                        unit = v["unit"]
                merged.append(
                    {
                        "resource": resource,
                        "limit": combined_value,
                        "unit": unit if unit else None,
                        "window": window,
                        "scope": {"group": sorted(merged_groups)},
                    }
                )
        return merged

    def _group_on_annotation(self, metric: str) -> str:
        """
        Group Prometheus query on namespace and pod to get JupyterHub username from hub.jupyter.org/username annotation, since pod names are not the same as usernames, e.g. Kubespawner template appends the server name https://jupyterhub-kubespawner.readthedocs.io/en/latest/templates.html#templated-fields
        """
        return (
            metric
            + " * on (namespace, pod) group_left(annotation_hub_jupyter_org_username) group(kube_pod_annotations{namespace=~'.*', annotation_hub_jupyter_org_username=~'.*'}) by (pod, namespace, annotation_hub_jupyter_org_username)"
        )

    def _update_promql_labels(self, metric: str, label: str, value: str) -> str:
        """
        Update metric to match specific label values.
        """
        pattern = rf"([{{,]\s*{label}[='~]*')([\w.*]*)"
        repl = rf"\1{value}"
        return re.sub(pattern, repl, metric)

    def write_promql(self, metric: str, user_name: str, policy: dict) -> str:
        """
        Write promql to match usage metric on label values and return range vector over policy window.
        """
        if self.escape_username_scheme["pod"] == "safe":
            user_name = safe_slug(
                user_name, max_length=self.escape_username_scheme["max_length"]
            )
        else:
            user_name = escape_slug(user_name)
        pattern = r"(\{.*?)(\})"
        repl = rf"\1, namespace='{self.hub_namespace}', node!='', pod=~'jupyter-{user_name}.*'\2"
        metric = re.sub(pattern, repl, metric)
        promql = f"{metric}[{str(policy['window']) + 'd'}:]"
        return promql

    async def get_usage(self, user_name: str, policy: dict) -> list:
        """
        Get resource usage by user over a rolling time window.
        """
        usage_metric = self.prometheus_usage_metrics[policy["resource"]]
        promql = self.write_promql(usage_metric, user_name, policy)
        self.log.debug(f"{promql=}")
        response = await self.prometheus_client.query(promql)
        if not response["data"]["result"]:
            # handle case when no data is returned
            unix_timestamp = (
                datetime.datetime.now(datetime.UTC)
                - datetime.datetime(1970, 1, 1, tzinfo=datetime.UTC)
            ).total_seconds()
            data: typing.List[typing.List[typing.Any]] = [[unix_timestamp, "0"]]
        else:
            # flatten results into a list
            n_result = len(response["data"]["result"])
            data = [response["data"]["result"][i]["values"] for i in range(n_result)]
            data = [d for ds in data for d in ds]
        result = [
            [
                d[0],
                float(d[1]) * self.prometheus_scrape_interval / self.seconds_to_hours,
            ]
            for d in data
        ]
        # Sort by time
        result.sort(key=lambda d: d[0])
        return result

    def get_retry_time(self, policy: dict, data: list) -> str:
        """
        Calculate when a user can retry launching their server after exceeding their quota limit.
        """
        x, y = zip(*data)
        cumulative_sum = list(itertools.accumulate(y))
        # Calculate difference between policy limit and current usage
        delta_resource = cumulative_sum[-1] - policy["limit"]
        self.log.debug(f"{delta_resource=}")
        # Find timestamp when usage falls below delta_resource
        index_retry = min(
            i for i, v in enumerate(cumulative_sum) if v >= delta_resource
        )
        # Calculate retry_time = timestamp + rolling window
        retry_time = datetime.datetime.fromtimestamp(
            x[index_retry], tz=datetime.UTC
        ) + datetime.timedelta(days=policy["window"])
        return retry_time.strftime("%Y-%m-%dT%H:%M:%SZ")

    def aggregate_usage(self, data: list) -> float:
        """
        Helper function to aggregate usage over time.
        """
        return [sum(x) for x in zip(*data)][1]

    def get_output(self, data: list, policy: dict) -> dict:
        """
        Formats the output returned by the quota system.
        """
        output: dict = {}
        value = self.aggregate_usage(data)
        if policy["resource"] == "memory":
            policy = self.convert_memory_to_bytes(policy, self.UNIT_SUFFIXES)
        limit = policy["limit"]
        if value < limit:
            output["allow_server_launch"] = True
        else:
            output["allow_server_launch"] = False
            if policy["resource"] == "memory":
                limit = limit / self.UNIT_SUFFIXES[policy["unit"]]
            output["error"] = {
                "code": "quota-exceeded",
                "message": f"Current {policy['resource']} usage = {value:.2f} is over the quota limit of {limit} over the last {policy['window']} days.",
                "retry_time": self.get_retry_time(policy, data),
            }
        if policy["resource"] != "memory":
            policy.update({"used": value})
            output["quota"] = policy
        else:
            # Convert bytes to human-readable format for output
            value = value / self.UNIT_SUFFIXES[policy["unit"]]
            policy.update({"used": value})
            output["quota"] = self.convert_bytes_to_memory(policy)
        output["timestamp"] = datetime.datetime.now(datetime.UTC).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        return output

    async def enforce(self, user_name: str, user_groups: list) -> dict:
        """
        Enforce quota system by resolving the policy applied to the user and comparing their usage to the quota limit.
        """
        output: dict = {}
        policy = self.resolve_policy(user_name, user_groups)
        if policy:
            self.log.debug(f"Quota policies applied: {policy}")
        else:
            self.log.info(
                f"No quota policies applied to {user_name}: allow server launch"
            )
            output["allow_server_launch"] = True
            output["quota"] = "None"
            output["timestamp"] = datetime.datetime.now(datetime.UTC).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
            return output

        for p in policy:
            usage = await self.get_usage(user_name, p)
            output = self.get_output(usage, p)
            self.log.info(f"{output=}")
            if output["allow_server_launch"] is False:
                self.log.warning(f"{output['error']['code']}: {user_name}")
                break
        return output


class SpawnException(web.HTTPError):
    """Custom exception that sets attributes for error page template."""

    def __init__(
        self,
        status_code: int,
        log_message: typing.Optional[str] = None,
        html_message: typing.Optional[str] = None,
        *args: typing.Any,
        **kwargs: typing.Any,
    ) -> None:
        super().__init__(status_code, log_message, *args, **kwargs)
        self.jupyterhub_html_message = html_message
