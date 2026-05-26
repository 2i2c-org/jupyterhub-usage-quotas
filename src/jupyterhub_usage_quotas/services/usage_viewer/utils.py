"""Utility functions for the usage viewer service."""

import logging
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from jupyterhub.services.auth import HubOAuth

log = logging.getLogger(__name__)


async def get_displayable_services(
    settings: dict[str, Any], hub_auth: HubOAuth
) -> list[dict[str, str]]:
    """Fetch displayable services from the Hub API, with a 60s in-process cache.

    Falls back to an empty list on any error (e.g. missing list:services scope).

    Args:
        settings: Tornado application settings dict (used for caching).
        hub_auth: HubOAuth instance for making Hub API requests.

    Returns:
        List of dicts with 'name' and 'href' keys for each displayable service.
    """
    cache = settings.get("_hub_services_cache")
    if cache and time.monotonic() < cache["expires"]:
        return cache["services"]

    services = []
    try:
        data = await hub_auth._api_request(
            "GET", hub_auth.api_url + "/services", allow_403=True
        )
        if data:
            services = [
                {"name": s["name"], "href": s.get("prefix", f"/services/{s['name']}")}
                for s in data.values()
                if s.get("display", True)
            ]
    except Exception as e:
        log.warning("Failed to fetch Hub services: %s", e)

    settings["_hub_services_cache"] = {
        "services": services,
        "expires": time.monotonic() + 60,
    }
    return services
