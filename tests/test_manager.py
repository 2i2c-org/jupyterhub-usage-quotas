import logging

logger = logging.getLogger(__name__)


async def test_hub_alive(admin_request):
    """Test that the hub is alive and responding to requests."""
    try:
        response = await admin_request(path="hub/api/info")
    except Exception:
        raise RuntimeError("Hub is not alive")
    assert response["version"] is not None
