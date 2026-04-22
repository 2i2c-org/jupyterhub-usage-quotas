from jupyterhub import orm
from prometheus_client import REGISTRY, Gauge
from tornado.ioloop import PeriodicCallback
from traitlets.config import Application

from jupyterhub_usage_quotas.manager import UsageQuotaManager

gauge_memory_usage = Gauge(
    "memory_usage_gibibyte_hours",
    "Usage of memory compute resources.",
    ["namespace", "usergroup", "username", "window"],
    namespace="jupyterhub",
    registry=REGISTRY,
)

gauge_cpu_usage = Gauge(
    "cpu_usage_core_hours",
    "Usage of CPU compute resources.",
    ["namespace", "usergroup", "username", "window"],
    namespace="jupyterhub",
    registry=REGISTRY,
)

gauge_memory_limit = Gauge(
    "memory_limit_gibibyte_hours",
    "Quota limit for memory compute resources.",
    ["namespace", "usergroup", "username", "window"],
    namespace="jupyterhub",
    registry=REGISTRY,
)

gauge_cpu_limit = Gauge(
    "cpu_limit_core_hours",
    "Quota limit for CPU compute resources.",
    ["namespace", "usergroup", "username", "window"],
    namespace="jupyterhub",
    registry=REGISTRY,
)


class MetricsExporter(Application):
    def __init__(
        self,
        quota_manager: UsageQuotaManager,
        db_url: str = "sqlite:///jupyterhub.sqlite",
        **kwargs,
    ):
        super().__init__(**kwargs)
        session = orm.new_session_factory(db_url)
        self.db = session()
        self.quota_manager = quota_manager
        self.namespace = self.quota_manager.hub_namespace

    def get_usernames_and_usergroups(self) -> list[tuple]:
        """
        Get list of usernames and their respective usergroup memberships from the hub database.
        """
        users = self.db.query(orm.User).all()
        users_and_groups = [(u.name, [g.name for g in u.groups]) for u in users]
        return users_and_groups

    def emit_metrics(self, user_name: str, user_groups: str, policies: list[dict]):
        """
        Emit usage and quota limits as Prometheus Gauge metrics.
        """
        for p in policies:
            if p["resource"] == "memory":
                if p.get("scope", None) is None:
                    user_group = "none"  # meta-group for backup policies that apply to users with no group memberships
                else:
                    user_group = set(user_groups) & set(p["scope"]["group"])
                    if len(user_group) != 1:
                        print(
                            f"WARNING: more than one group identified with a single policy for user {user_name}"
                        )
                    else:
                        user_group = user_group.pop()
                # usage = await self.quota_manager.get_usage(user_name, p)
                # print(f"{usage=}")
                gauge_memory_usage.labels(
                    username=user_name,
                    usergroup=user_group,
                    window=str(p["window"]),
                    namespace=self.namespace,
                ).set(
                    1
                )  # TODO: set to usage after prom auth is fixed
                gauge_memory_limit.labels(
                    username=user_name,
                    usergroup=user_group,
                    window=str(p["window"]),
                    namespace=self.namespace,
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
            print(f"user={u[0]}")
            print(f"{policies=}")
            self.emit_metrics(user_name=u[0], user_groups=u[1], policies=policies)

    def start(self):
        pc = PeriodicCallback(
            self.update_metrics, self.quota_manager.prometheus_emit_interval * 1e3
        )
        pc.start()
