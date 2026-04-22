import logging

from jupyterhub import orm
from prometheus_client import REGISTRY, Gauge
from tornado.ioloop import PeriodicCallback
from traitlets.config import Application

from jupyterhub_usage_quotas.manager import UsageQuotaManager


class MetricsExporter(Application):
    def __init__(
        self,
        quota_manager: UsageQuotaManager,
        db_url: str = "sqlite:///jupyterhub.sqlite",
        **kwargs,
    ):
        super().__init__(**kwargs)
        parent_log = logging.getLogger("JupyterHub")
        self.log = logging.getLogger(__name__)
        self.log.parent = parent_log
        self.log.info("Starting metrics exporter for usage quotas system.")
        session = orm.new_session_factory(db_url)
        self.db = session()
        self.quota_manager = quota_manager
        self.hub_namespace = self.quota_manager.hub_namespace
        self.prometheus_namespace = self.quota_manager.prometheus_emit_namespace
        self.convert_unit = {"GiB-hours": "gibibyte_hours"}
        self.metrics = {}

    def get_usernames_and_usergroups(self) -> list[tuple]:
        """
        Get list of usernames and their respective usergroup memberships from the hub database.
        """
        users = self.db.query(orm.User).all()
        users_and_groups = [(u.name, [g.name for g in u.groups]) for u in users]
        return users_and_groups

    def get_metrics(self, resource: str, unit: str) -> dict:
        """
        Define Prometheus metric depending on policy resource, e.g. memory or cpu.
        """
        output = {}
        metric_unit = self.convert_unit[unit]
        for key in ["limit", "usage"]:
            metric_name = f"{resource}_{key}_{metric_unit}"
            if metric_name not in self.metrics:
                self.log.info(f"Registering metric {metric_name}")
                self.metrics[metric_name] = Gauge(
                    metric_name,
                    f"Resource {key} for {resource} from usage quota system.",
                    ["namespace", "usergroup", "username", "window"],
                    namespace=self.prometheus_namespace,
                    registry=REGISTRY,
                )
            output[key] = self.metrics[metric_name]
        return output

    def emit_metrics(self, user_name: str, user_groups: str, policies: list[dict]):
        """
        Emit usage and quota limits as Prometheus Gauge metrics.
        """
        for p in policies:
            # Determine unique scope group for the policy applied to the user
            if p.get("scope", None) is None:
                user_group = "none"  # meta-group for backup policies that apply to users with no group memberships
            else:
                user_group = set(user_groups) & set(p["scope"]["group"])
                if len(user_group) != 1:
                    self.log.warning(
                        f"More than one group identified with a single policy for user {user_name}"
                    )
                else:
                    user_group = user_group.pop()
            # Dynamically define metrics based on policy values and set them
            metric = self.get_metrics(resource=p["resource"], unit=p["limit"]["unit"])
            # usage = await self.quota_manager.get_usage(user_name, p)
            # self.log.debug(f"{user_name=}, policy={p}, {usage=}")
            metric["usage"].labels(
                username=user_name,
                usergroup=user_group,
                window=str(p["window"]),
                namespace=self.hub_namespace,
            ).set(
                1
            )  # TODO: set to usage after prom auth is fixed
            metric["limit"].labels(
                username=user_name,
                usergroup=user_group,
                window=str(p["window"]),
                namespace=self.hub_namespace,
            ).set(p["limit"]["value"])

    def update_metrics(self):
        """
        Update Prometheus metrics for usage and quota limits.
        """
        users_and_groups = self.get_usernames_and_usergroups()
        for u in users_and_groups:
            policies = self.quota_manager.resolve_policy(
                user_name=u[0], user_groups=u[1]
            )
            self.emit_metrics(user_name=u[0], user_groups=u[1], policies=policies)
        self.log.info("Usage quota metrics updated.")

    def start(self):
        pc = PeriodicCallback(
            self.update_metrics, self.quota_manager.prometheus_emit_interval * 1e3
        )
        pc.start()
