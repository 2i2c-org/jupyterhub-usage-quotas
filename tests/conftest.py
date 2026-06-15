import ast
import json
from unittest.mock import Mock

import pytest
from jupyterhub.objects import Server


class MockGroup(Mock):
    name = "test-group"

    def __init__(self, **kwargs):
        super().__init__()
        for key, value in kwargs.items():
            setattr(self, key, value)


class MockUser(Mock):
    name = "test-user"
    groups = []
    server = Server()

    def __init__(self, **kwargs):
        super().__init__()
        for key, value in kwargs.items():
            setattr(self, key, value)

    @property
    def escaped_name(self):
        return self.name

    @property
    def url(self):
        return self.server.url


@pytest.fixture
def data_response():
    """
    Mock Prometheus usage response.
    """
    with open("tests/data/response.json") as f:
        data = json.load(f)
        return data


@pytest.fixture
def data_usage():
    """
    Usage data as a list in chronological order.
    """
    data = []
    with open("tests/data/usage.txt", "r") as f:
        for line in f:
            data.append(ast.literal_eval(line.rstrip()))
    return data
