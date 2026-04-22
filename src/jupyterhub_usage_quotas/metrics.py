from jupyterhub import orm
from prometheus_client import REGISTRY, Counter
from tornado.ioloop import PeriodicCallback
from traitlets.config import Application

from jupyterhub_usage_quotas.manager import UsageQuotaManager

c = Counter(
    "my_counter_total", "Example counter", namespace="jupyterhub", registry=REGISTRY
)


class MetricsExporter(Application):
    def __init__(
        self,
        quota_manager: UsageQuotaManager,
        db_url: str = "sqlite:///jupyterhub.sqlite",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.quota_manager = quota_manager
        session = orm.new_session_factory(db_url)
        self.db = session()

    def get_usernames_and_usergroups(self) -> list[tuple]:
        """
        Get list of usernames and their respective usergroup memberships from the hub database.
        """
        users = self.db.query(orm.User).all()
        users_and_groups = [(u.name, [g.name for g in u.groups]) for u in users]
        return users_and_groups

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
        c.inc()

    def start(self):
        pc = PeriodicCallback(self.update_metrics, 5e3)
        pc.start()
