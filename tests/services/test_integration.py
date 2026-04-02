"""Integration tests for end-to-end user flows"""

import re


class TestEndToEndUserFlow:
    """Test complete user flows from start to finish"""

    def test_complete_unauthenticated_to_viewing_usage(
        self, client, app, mock_env_vars, mock_prometheus_client
    ):
        """Test: unauthenticated → OAuth → view usage"""
        with client:
            response = client.get("/services/usage-quota", follow_redirects=False)
            # Unauthenticated users get JS redirect (not HTTP 307)
            assert response.status_code == 200
            assert "window.top.location.href" in response.text
            assert "oauth2/authorize" in response.text

            # Extract state from JS redirect
            match = re.search(r'state=([^"&]+)', response.text)
            state = match.group(1)

            response = client.get(
                f"/services/usage-quota/oauth_callback?code=auth123&state={state}",
                follow_redirects=False,
            )
            assert response.status_code == 307
            # Redirects to /hub/usage (embedded view with JupyterHub nav bar)
            assert response.headers["Location"] == "http://test-hub:8000/hub/usage"

            response = client.get("/services/usage-quota", follow_redirects=False)
            assert response.status_code == 200
            assert "Home storage" in response.text
            assert "50.0%" in response.text
            assert "5.0 GiB used" in response.text
