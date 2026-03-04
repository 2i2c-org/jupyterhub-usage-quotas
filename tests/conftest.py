import json
import logging
from unittest.mock import AsyncMock

import pytest

logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
async def mock_hub_client():
    """Start JupyterHub, set up to use admin and service tokens"""
    mock_hub_client = AsyncMock()
    with open("tests/data/hub_api_user.json", "r") as f:
        mock_hub_client.query.return_value = json.load(f)
    yield mock_hub_client
