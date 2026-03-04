import asyncio
import logging
import os
import secrets
import shutil
import signal
import time
from functools import partial
from subprocess import Popen
from tempfile import TemporaryDirectory
from unittest import mock

import aiohttp
import backoff
import psutil
import pytest
from yarl import URL

logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def admin_token():
    """Generate a token to use for admin requests"""
    token = secrets.token_hex(16)
    # jupyterhub subprocess loads this from the environment
    with mock.patch.dict(os.environ, {"TEST_PYTEST_TOKEN": token}):
        yield token


@pytest.fixture(scope="session")
def hub_url():
    # hardcoded for now, but might want to override
    return "http://127.0.0.1:8000"


@pytest.fixture(scope="session")
async def hub(hub_url, request, admin_token):
    """Start JupyterHub, set up to use admin and service tokens"""
    jupyterhub_config = os.path.dirname(__file__) + "/jupyterhub_config.py"
    with TemporaryDirectory() as td:
        shutil.copy(jupyterhub_config, td + "/jupyterhub_config.py")
        hub = Popen(["jupyterhub", "--debug"], cwd=td)

        def cleanup():
            if hub.poll() is None:
                try:
                    kill_proc_tree(hub.pid)
                except psutil.ProcessLookupError:
                    pass
            logger.info("terminating hub")
            hub.terminate()

        request.addfinalizer(cleanup)

        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            resp = await api_request(
                hub_url=hub_url, path="hub/api/info", token=admin_token
            )
            if resp:
                logger.info(f"{resp}")
                logger.info("hub started")
                break
            else:
                logger.info(f"{resp}")
                logger.info("waiting for hub to start")
                await asyncio.sleep(1)
                continue

        yield hub


@backoff.on_exception(backoff.expo, aiohttp.ClientError, max_tries=8, logger=logger)
async def api_request(
    hub_url: str, path: str, token: str = None, parse_json: bool = True
):
    """Make an API request to the Hub, parsing JSON responses"""
    headers = {"Authorization": f"token {token}"}
    hub_url = URL(hub_url)
    url = hub_url.with_path(f"{path}")
    logger.info(f"Making request to {url}")
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            if resp.status == 200:
                try:
                    if parse_json:
                        return await resp.json()
                    else:
                        return await resp.text()
                except:
                    logger.error("Failed to decode response.")
                    raise
            else:
                raise aiohttp.ClientError(f"Bad response: {resp.status}")


@pytest.fixture(scope="session")
def admin_request(hub, hub_url, admin_token):
    """make an API request to a path with an admin token"""
    return partial(api_request, hub_url, token=admin_token)


def kill_proc_tree(
    pid, sig=signal.SIGKILL, include_parent=True, timeout=None, on_terminate=None
):
    """Kill a process tree (including grandchildren) with signal
    "sig" and return a (gone, still_alive) tuple.
    "on_terminate", if specified, is a callback function which is
    called as soon as a child terminates.
    """
    assert pid != os.getpid(), "won't kill myself"
    parent = psutil.Process(pid)
    children = parent.children(recursive=True)
    if include_parent:
        children.append(parent)
    for p in children:
        try:
            p.send_signal(sig)
            logger.info(f"terminating {p}")
        except psutil.NoSuchProcess:
            pass
    gone, alive = psutil.wait_procs(children, timeout=timeout, callback=on_terminate)
    logger.info(f"{len(gone)} processes killed, {len(alive)} still alive.")
