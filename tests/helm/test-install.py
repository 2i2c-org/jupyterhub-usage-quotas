#!/usr/bin/env python3
"""Check an installed jupyterhub-usage-quotas chart through the z2jh proxy.

It expects z2jh to be installed with tests/helm/z2jh-values.yaml, and the
proxy to be reachable at the URL given as the first argument, e.g. with:

    kubectl port-forward service/proxy-public 8080:80
    tests/helm/test-install.py http://localhost:8080
"""

import http.cookiejar
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

SERVICE_PREFIX = "/services/usage-quota/"
USERNAME = "test-user"
PASSWORD = "test-password"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def request(opener, url, data=None):
    """Return (status, final URL, headers, body) without raising on HTTP errors."""
    if data is not None:
        data = urllib.parse.urlencode(data).encode()
    try:
        with opener.open(url, data=data, timeout=30) as r:
            return r.status, r.url, r.headers, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.url, e.headers, e.read().decode()


def check(description, ok, details=""):
    print(f"{'ok:  ' if ok else 'FAIL:'} {description}")
    if not ok:
        print(f"      {details}")
        sys.exit(1)


def main(base_url):
    base_url = base_url.rstrip("/")
    cookies = http.cookiejar.CookieJar()
    browser = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies))
    no_redirect = urllib.request.build_opener(NoRedirect)

    # The proxy routes to the service, and the health endpoint needs no login.
    # Retry for a short time after the install: the hub looks up the service
    # host name at startup, possibly before the Service exists, and the DNS
    # server can cache that negative answer for up to 30 seconds.
    deadline = time.monotonic() + 90
    while True:
        status, _, _, body = request(browser, f"{base_url}{SERVICE_PREFIX}health")
        if status == 200 or time.monotonic() > deadline:
            break
        time.sleep(3)
    check("health endpoint through the proxy", status == 200, f"{status} {body[:500]}")

    # A user that is not logged in is sent to the hub OAuth authorize URL.
    status, _, headers, _ = request(no_redirect, f"{base_url}{SERVICE_PREFIX}")
    location = headers.get("Location", "")
    check(
        "dashboard redirects to the hub OAuth authorize URL",
        status == 302
        and "/hub/api/oauth2/authorize" in location
        and "client_id=service-usage-quota" in location,
        f"{status} {location}",
    )

    # Log in to the hub. The login form needs the _xsrf cookie value. Go to the
    # hub home page after the login, because the default (/hub/spawn) starts a
    # user server.
    request(browser, f"{base_url}/hub/login")
    xsrf = next((c.value for c in cookies if c.name == "_xsrf"), "")
    status, url, _, body = request(
        browser,
        f"{base_url}/hub/login?next=/hub/home",
        {"username": USERNAME, "password": PASSWORD, "_xsrf": xsrf},
    )
    check(
        "log in to the hub",
        status == 200 and urllib.parse.urlparse(url).path == "/hub/home",
        f"{status} {url}",
    )

    # The full OAuth round trip: authorize, then the callback, in which the
    # service gets a token from the hub API, and then the dashboard. There is
    # no Prometheus in the test, so the dashboard shows an error with 424.
    status, url, _, body = request(browser, f"{base_url}{SERVICE_PREFIX}")
    check(
        "dashboard renders after the OAuth round trip",
        status in (200, 424)
        and urllib.parse.urlparse(url).path == SERVICE_PREFIX
        and "<h1>Usage</h1>" in body,
        f"{status} {url}\n{body[:2000]}",
    )
    check(
        "dashboard uses the hub page template with the user name",
        USERNAME in body and "/hub/logout" in body,
        body[:2000],
    )

    print("All checks passed")


if __name__ == "__main__":
    main(sys.argv[1])
