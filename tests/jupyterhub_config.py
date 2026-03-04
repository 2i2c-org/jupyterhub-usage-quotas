"""
NOTE: This JupyterHub configuration file is included in this repo for local development and testing.
"""

import os
import pathlib
import secrets

c = get_config()  # noqa

# JupyterHub

c.JupyterHub.ip = "127.0.0.1"
c.JupyterHub.port = 8000
c.JupyterHub.hub_ip = "127.0.0.1"
c.JupyterHub.authenticator_class = "dummy"

n_users = 3
c.Authenticator.allowed_users = {f"user-{i}" for i in range(n_users)}
c.JupyterHub.load_groups = {
    f"group-{i}": dict(users=[f"user-{i}"]) for i in range(n_users)
}

c.Authenticator.admin_users = {"admin"}
c.JupyterHub.authenticator_class = "dummy"
c.JupyterHub.spawner_class = "simple"

c.JupyterHub.load_roles = [
    {
        "name": "pytest",
        "scopes": [
            "read:hub",
            "users",
            "groups",
        ],
        "services": ["pytest"],
    },
    {
        "name": "usage-quotas-role",
        "scopes": [
            "users",
        ],
        "services": ["usage-quotas-service"],
    },
]

here = pathlib.Path(__file__).parent
token_file = here.joinpath("api_token")
if token_file.exists():
    with token_file.open("r") as f:
        token = f.read()
else:
    token = secrets.token_hex(16)
    with token_file.open("w") as f:
        f.write(token)

c.JupyterHub.services = [
    {
        "name": "pytest",
        "api_token": os.environ.get("TEST_PYTEST_TOKEN"),
    },
    {
        "name": "usage-quotas-service",
        "api_token": token,
    },
]
