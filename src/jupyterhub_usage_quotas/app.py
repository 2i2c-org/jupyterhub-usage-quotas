from pathlib import Path

from traitlets import Unicode
from traitlets.config import Application, Bool

from jupyterhub_usage_quotas.config import Quotas


class QuotasApp(Application):
    name = "jupyterhub_usage_quotas"
    description = "JupyterHub usage quotas enforcement library."
    examples = """
    Generate default config file:

        jupyterhub_usage_quotas --generate-config -f /etc/jupyterhub/jupyterhub_usage_quotas_config.py
    """

    # Application traits

    config_file = Unicode(
        "jupyterhub_usage_quotas_config.py", help="The config file to load"
    ).tag(config=True)
    generate_config = Bool(False, help="Generate default config file").tag(config=True)

    # Configurable traits

    classes = [Quotas]

    # Aliases

    aliases = {
        "f": "QuotasApp.config_file",
        "config": "QuotasApp.config_file",
    }

    flags = {
        "generate-config": (
            {"QuotasApp": {"generate_config": True}},
            "Generate default config file",
        )
    }

    def initialize(self, argv=None):
        super().initialize(argv)
        if self.generate_config:
            config_text = self.generate_config_file()
            if isinstance(config_text, bytes):
                config_text = config_text.decode("utf8")
            self.log.info(f"Writing default config to: {self.config_file}")
            with open(self.config_file, mode="w") as f:
                f.write(config_text)
            return
        if self.config_file:
            if Path(self.config_file).exists():
                self.load_config_file(self.config_file)
                self.quota_config = Quotas(parent=self)
                self.log.info(f"Loaded config file: {self.config_file}")
            else:
                self.log.error(f"Config file does not exist: {self.config_file}")
            return

    def start(self):
        self.log.debug(f"{self.config}")


def main():
    QuotasApp.launch_instance()


if __name__ == "__main__":
    main()
