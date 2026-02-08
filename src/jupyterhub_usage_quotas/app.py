import uvicorn
from fastapi import FastAPI
from traitlets import Integer, Unicode
from traitlets.config import Application, Instance

from jupyterhub_usage_quotas.config import QuotasConfig


class Quotas(Application):
    name = "jupyterhub-usage-quotas"

    server_ip = Unicode("0.0.0.0", help="IP address to bind API server.").tag(
        config=True
    )
    server_port = Integer(8000, help="Port to bind API server.").tag(config=True)
    server_log_level = Unicode("info", help="Uvicorn log level.").tag(config=True)
    config_file = Unicode("usage_quotas_config.py", help="Config file to load.").tag(
        config=True
    )

    quotas_config = Instance(QuotasConfig, allow_none=True)

    def initialize(self, argv=None):
        super().initialize(argv)

        if self.config_file:
            self.log.info(f"Loading config file: {self.config_file}")
            self.load_config_file(self.config_file)

        self.quotas_config = QuotasConfig(parent=self)
        self.app = self._build_app()

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

    def start(self):

        self.log.info(f"Starting server on {self.server_ip}:{self.server_port}")

        self.log.info(f"{self.quotas_config.prometheus_usage_metrics}")

        uvicorn.run(
            self.app,
            host=self.server_ip,
            port=self.server_port,
            log_level=self.log_level,
            reload=False,
            workers=1,
        )


if __name__ == "__main__":
    Quotas.launch_instance()
