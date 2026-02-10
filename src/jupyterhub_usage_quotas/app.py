import logging.config
import os
import signal

import uvicorn
from fastapi import FastAPI
from traitlets import Bool, Integer, Unicode
from traitlets.config import Application, Instance

from jupyterhub_usage_quotas.config import Quotas


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
        self.load_config_file(self.config_file)
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
        self.log.propagate = False
        # Propagate uvicorn logger into central traitlets.Application logger
        uvicorn_loggers = (
            "uvicorn",
            "uvicorn.error",
            "uvicorn.access",
        )
        for name in uvicorn_loggers:
            logger = logging.getLogger(name)
            logger.propagate = True
            logger.parent = self.log
            logger.setLevel(self.log_level)
        # Apply config to application logger
        self.log.setLevel(self.log_level)
        _formatter = logging.Formatter(fmt=self.log_format, datefmt=self.log_datefmt)
        for handler in self.log.handlers:
            if handler.formatter is None:
                handler.setFormatter(_formatter)

    def start(self):
        self.app = self._build_app()
        self.initialize()

        uvicorn.run(
            self.app,
            host=self.server_ip,
            port=self.server_port,
        )

    def stop(self):
        os.kill(os.getpid(), signal.SIGTERM)
        return


def main():
    QuotasApp.launch_instance()


if __name__ == "__main__":
    main()
