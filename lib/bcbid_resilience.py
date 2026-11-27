"""
Connection fallback for the BC Bid scraper.

BC Bid used to put ``--proxy-server=PROXY_URL`` on every browser and stop at the
first "Browser check" refusal, so a dead Squid VM or one refusal failed the run.
The scraper now works through an ordered list of attempts, each one in a fresh
browser:

1. ``squid``         the proxy in the ``PROXY_URL`` environment variable (the
                     ``PROXY_URL_WITH_PASS`` secret in GitHub Actions).  Skipped
                     when ``PROXY_URL`` is not set.
2. ``direct``        no proxy.
3. ``open-proxy-N``  free public proxies, only with ``BCBID_USE_OPEN_PROXIES=1``.

What this module deliberately does not do:

- No proxy login code.  The credentials stay in the URL
  (``http://user:pass@host:port``); pydoll takes them off the Chrome command
  line and answers the proxy's login itself
  (https://pydoll.tech/docs/guides/proxies/).
- No fingerprint profile.  ``tab.apply_fingerprint()`` is optional, pydoll ships
  no profiles, and its docs say a profile that does not describe the real
  machine and exit IP is worse than an untouched browser
  (https://pydoll.tech/docs/stealth/fingerprint-injection/).  Applying one also
  switches off the proxy login above: every navigation through the Squid proxy
  then fails with ERR_INVALID_AUTH_CREDENTIALS.
- No saved browser profile.  pydoll starts every browser in a temporary one.
- No IPRoyal.  ``IPROYAL_*`` variables are ignored even when they are exported.
"""
import os
from dataclasses import dataclass


# Free proxies are mostly dead; never spend more than this many 5s health checks.
OPEN_PROXY_MAX_CHECKS = 20

# Chrome network errors that mean "could not get through", not "the site blocked us".
PROXY_ERROR_MARKERS = (
    "err_proxy_connection_failed",
    "err_tunnel_connection_failed",
    "err_proxy_unsupported_auth_scheme",
    "err_proxy_auth_failed",
    # The proxy rejected our credentials (or nobody answered its login prompt).
    "err_too_many_retries",
    "err_invalid_auth_credentials",
    "err_name_not_resolved",
    "err_connection_refused",
    "err_timed_out",
    "err_connection_reset",
)


def env_int(name, default):
    """int(os.getenv(name)) that survives unset *and* empty values.

    GitHub Actions exports an unset ``${{ vars.X }}`` as an empty string, which
    would otherwise crash the scraper at import time.
    """
    raw = (os.getenv(name) or "").strip()
    try:
        return int(raw) if raw else default
    except ValueError:
        print(f"[bcbid] ignoring {name}={raw!r}; using {default}")
        return default


def redact_proxy_url(proxy_url):
    """Hide ``user:pass@`` so proxy credentials never reach logs or Discord."""
    scheme, separator, rest = proxy_url.rpartition("://")
    if "@" in rest:
        rest = "***@" + rest.rsplit("@", 1)[1]
    return f"{scheme}{separator}{rest}"


@dataclass(frozen=True)
class ProxyAttempt:
    """One complete scrape attempt in its own browser."""

    name: str
    proxy_url: str | None = None  # may carry user:pass@; never print it, use describe()

    @property
    def uses_proxy(self):
        return bool(self.proxy_url)

    def describe(self):
        if not self.uses_proxy:
            return f"{self.name} (direct)"
        return f"{self.name} (proxy {redact_proxy_url(self.proxy_url)})"


def _healthy_open_proxies(limit):
    """
    Free proxies already used elsewhere in this repo (web_requests.get_proxy_list).
    They are opt-in (BCBID_USE_OPEN_PROXIES=1) and last: public proxies are slow,
    short-lived and widely blocked.
    """
    import requests

    try:
        from web_requests import get_proxy_list
        candidates = get_proxy_list()
    except Exception as exc:  # pragma: no cover - depends on third-party sites
        print(f"[bcbid] could not fetch open proxies: {exc}")
        return []

    healthy = []
    for proxy in candidates[:OPEN_PROXY_MAX_CHECKS]:
        if len(healthy) >= limit:
            break
        url = proxy if "://" in proxy else f"http://{proxy}"
        try:
            response = requests.get(
                "https://bcbid.gov.bc.ca/",
                proxies={"http": url, "https": url},
                timeout=5,
            )
            if response.status_code < 500:
                healthy.append(url)
        except Exception:
            continue
    print(f"[bcbid] {len(healthy)} open proxy/proxies passed the health check")
    return healthy


def build_proxy_attempts(max_attempts=None):
    """
    Ordered attempts: Squid -> direct -> (opt-in) open proxies.

    Without PROXY_URL there is no Squid attempt and the list starts at direct.
    max_attempts caps the list, and skips the slow open-proxy health checks when
    the earlier attempts already fill it.

    Environment:
      PROXY_URL                 the shared Squid proxy, set by the GitHub Actions
                                workflow; may be http://user:pass@host:port
      BCBID_USE_OPEN_PROXIES    set to 1 to add health-checked free proxies
      BCBID_OPEN_PROXY_LIMIT    how many free proxies to try (default 2)
    """
    attempts = []

    squid = (os.getenv("PROXY_URL") or "").strip()
    if squid:
        attempts.append(ProxyAttempt("squid", proxy_url=squid))

    # Direct is the fallback for a dead or blocked Squid VM (and the only attempt
    # when PROXY_URL is not set).
    attempts.append(ProxyAttempt("direct"))

    room = None if max_attempts is None else max_attempts - len(attempts)
    if os.getenv("BCBID_USE_OPEN_PROXIES") == "1" and (room is None or room > 0):
        limit = max(0, env_int("BCBID_OPEN_PROXY_LIMIT", 2))
        if room is not None:
            limit = min(limit, room)
        for number, proxy in enumerate(_healthy_open_proxies(limit), 1):
            attempts.append(ProxyAttempt(f"open-proxy-{number}", proxy_url=proxy))

    return attempts if max_attempts is None else attempts[:max_attempts]


def is_proxy_failure(exc):
    """True when an exception is a connection failure rather than a site block."""
    text = f"{type(exc).__name__}: {exc}".lower()
    return any(marker in text for marker in PROXY_ERROR_MARKERS)
