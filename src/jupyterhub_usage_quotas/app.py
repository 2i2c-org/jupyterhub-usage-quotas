from pathlib import Path

from traitlets import Unicode
from traitlets.config import Application

from jupyterhub_usage_quotas.config import UsageQuotas


class QuotasApp(Application):
    name = "jupyterhub_usage_quotas"
    description = "JupyterHub usage UsageQuotas enforcement library."
    examples = """
        jupyterhub_usage_quotas
    """

    # Application traits

    config_file = Unicode("jupyterhub_config.py", help="The config file to load").tag(
        config=True
    )

    # Configurable traits

    classes = [UsageQuotas]

    # Aliases

    aliases = {
        "f": "QuotasApp.config_file",
        "config": "QuotasApp.config_file",
    }

    def initialize(self, argv=None):
        super().initialize(argv)
        if self.config_file:
            if Path(self.config_file).exists():
                self.load_config_file(self.config_file)
                self.quota_config = UsageQuotas(parent=self)
                self.log.info(f"Loaded config file: {self.config_file}")
            else:
                self.log.error(f"Config file does not exist: {self.config_file}")
            return

    def start(self):
        self.log.debug(f"{self.config}")
        self.log.info(
            f"Applying usage quota policy: {self.config["UsageQuotas"]["policy"]}"
        )


def main():
    QuotasApp.launch_instance()


if __name__ == "__main__":
    main()
