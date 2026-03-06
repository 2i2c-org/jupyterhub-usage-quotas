import json
import logging
import pathlib
import secrets
from unittest.mock import AsyncMock

import pytest

logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def api_token():
    """Generate a token to use for hub api requests"""
    here = pathlib.Path(__file__).parent.parent
    token_file = here.joinpath("api_token")
    if token_file.exists():
        with token_file.open("r") as f:
            token = f.read()
    else:
        token = secrets.token_hex(16)
        with token_file.open("w") as f:
            f.write(token)


@pytest.fixture(scope="session")
async def mock_hub_client(api_token):
    """Mock JupyterHub API client"""
    mock_hub_client = AsyncMock()
    with open("tests/data/hub_api_user.json", "r") as f:
        mock_hub_client.query.return_value = json.load(f)
    yield mock_hub_client
