import ast
import json

import pytest


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
