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
        **kwargs
    ):
        super().__init__(**kwargs)
        self.quota_manager = quota_manager
        session = orm.new_session_factory(db_url)
        self.db = session()

    def get_usernames(self) -> list:
        users = self.db.query(orm.User).all()
        usernames = [u.name for u in users]
        return usernames

    def get_usergroups(self) -> list:
        groups = self.db.query(orm.Group).all()
        usergroups = [g.name for g in groups]
        return usergroups

    def update_metrics(self):
        """
        Update usage and quota limits Prometheus metrics.
        """
        usernames = self.get_usernames()
        usergroups = self.get_usergroups()
        for user in usernames:
            policies = self.quota_manager.resolve_policy(
                user_name=user, user_groups=usergroups
            )
            print(policies)
        c.inc()

    def start(self):
        pc = PeriodicCallback(self.update_metrics, 5e3)
        pc.start()
