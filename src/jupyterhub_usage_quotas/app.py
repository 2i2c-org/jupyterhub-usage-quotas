import logging.config
import os
import signal

import uvicorn
from fastapi import FastAPI
from traitlets import Bool, Integer, Unicode
from traitlets.config import Application, Instance

from jupyterhub_usage_quotas.config import Quotas
from jupyterhub_usage_quotas.logs import LOGGING_CONFIG

logging.config.dictConfig(LOGGING_CONFIG)


class QuotasApp(Application):
    name = "jupyterhub_usage_quotas"
    description = "Start the JupyterHub usage quotas application."
    examples = """
    Generate default config file:

        jupyterhub_usage_quotas --generate-config -f /etc/jupyterhub/jupyterhub_usage_quotas_config.py
    """

    # Application traits

    server_ip = Unicode("0.0.0.0", help="IP address to bind API server.").tag(
        config=True
    )
    server_port = Integer(8000, help="Port to bind API server.").tag(config=True)
    server_log_level = Unicode("info", help="Uvicorn log level.").tag(config=True)
    config_file = Unicode(
        "jupyterhub_usage_quotas_config.py", help="The config file to load"
    ).tag(config=True)
    generate_config = Bool(False, help="Generate default config file").tag(config=True)

    # Configurable traits

    classes = [Quotas]

    quotas_config = Instance(Quotas)

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

    def initialize(self, *args, **kwargs):
        super().initialize(*args, **kwargs)
        self._format_logs()
        if self.generate_config:
            config_text = self.generate_config_file()
            if isinstance(config_text, bytes):
                config_text = config_text.decode("utf8")
            self.log.info(f"Writing default config to: {self.config_file}")
            with open(self.config_file, mode="w") as f:
                f.write(config_text)
            self.stop()

        return

    def _build_app(self) -> FastAPI:
        app = FastAPI()

        @app.get("/")
        def root():
            return {"message": "Welcome to the JupyterHub Usage Quotas API"}

        @app.get("/health/ready")
        def ready():
            """
            Readiness probe endpoint.
            """
            return ("200: OK", 200)

        return app

    def _format_logs(self):
        for h in list(self.log.handlers):
            self.log.removeHandler(h)
        self.log.propagate = True

    def start(self):
        self.initialize()
        self.app = self._build_app()
        self.load_config_file(self.config_file)
        self.log.info(f"Starting server on {self.server_ip}:{self.server_port}")

        uvicorn.run(
            self.app,
            host=self.server_ip,
            port=self.server_port,
            log_level=self.log_level,
            log_config=None,  # use LOGGING_CONFIG and not uvicorn log config
        )

    def stop(self):
        os.kill(os.getpid(), signal.SIGTERM)
        return


def main():
    QuotasApp.launch_instance()


if __name__ == "__main__":
    main()
