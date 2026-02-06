from fastapi import FastAPI

from jupyterhub_usage_quotas.logs import get_logger

app = FastAPI()
logger = get_logger(__name__)


@app.get("/")
def index():
    return {"message": "Welcome to the JupyterHub Usage Quotas API"}


@app.get("/health/ready")
def ready():
    """
    Readiness probe endpoint.
    """
    return ("200: OK", 200)
