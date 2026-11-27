"""
Resilience helpers for the BC Bid scraper.

Two separate problems are handled here:

1. Proxies fail.  BC Bid used to put ``--proxy-server=PROXY_URL`` on every
   browser unconditionally, so a dead/shared Squid VM took the whole run down
   with net::ERR_TIMED_OUT.  We now build an ordered list of connection attempts
   (the Squid proxy first, then a direct connection, then -- opt in only --
   health-checked free proxies) and use a new browser for each one, so a dead
   proxy costs one attempt instead of the run.  The proxy comes from the
   PROXY_URL environment variable (a GitHub Actions secret).  IPRoyal is
   deliberately not used for BC Bid.

2. BC Bid's "Browser check" is an invisible reCAPTCHA v3.  The page itself calls
   ``window.ivCaptcha.solve()`` -> ``grecaptcha.execute(...)`` -> fills
   ``#captcha_response`` -> submits ``mainForm``.  There is no puzzle to click and
   no pydoll "solve" method (pydoll's captcha helper is Cloudflare Turnstile
   only).  What makes v3 pass is pydoll's stealth layer plus IP reputation, so
   this module builds a coherent fingerprint for ``tab.apply_fingerprint()`` and
   the scraper runs pydoll's humanized mouse/scroll actions while the check runs.

Pydoll's own docs: "It does not handle reCAPTCHA or hCaptcha. Those are not
supported by this feature."  See https://pydoll.tech/docs/stealth/captcha-bypass/
"""
import os
from dataclasses import dataclass

from pydoll.commands import FetchCommands
from pydoll.exceptions import CommandFailed
from pydoll.protocol.fetch.events import FetchEvent
from pydoll.protocol.fetch.types import AuthChallengeResponseType


# Free proxies are mostly dead; never spend more than this many 5s health checks.
OPEN_PROXY_MAX_CHECKS = 20


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


def split_proxy_credentials(proxy_url):
    """
    ``http://user:pass@host:port`` -> (``http://host:port``, ``user``, ``pass``).

    Chrome ignores credentials in --proxy-server, and pydoll's built-in handling
    of them stops working once apply_fingerprint() re-enables Fetch without auth
    handling (every navigation then fails with ERR_INVALID_AUTH_CREDENTIALS).
    The credentials are therefore split off here and answered by
    answer_proxy_auth() for the whole session.  They are passed on as written
    (not URL-decoded), which is what pydoll did with them before.
    """
    scheme, separator, rest = proxy_url.rpartition("://")
    credentials, at, server = rest.rpartition("@")
    if not at or ":" not in credentials:
        return proxy_url, None, None
    username, password = credentials.split(":", 1)
    return f"{scheme}{separator}{server}", username, password


# Chrome network errors that mean "the proxy is down", not "the site blocked us".
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
    "failed to start browser",
    "failedtostartbrowser",
)


@dataclass(frozen=True)
class ProxyAttempt:
    """One complete scrape attempt with its own browser and egress IP."""

    name: str
    proxy_url: str | None = None
    username: str | None = None
    password: str | None = None
    headless: bool = False  # headful clears reCAPTCHA v3 more often than headless

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
    They are opt-in (BCBID_USE_OPEN_PROXIES=1): public proxies have poor IP
    reputation, so reCAPTCHA v3 is much less likely to accept them.
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
    the earlier attempts already fill it.  IPROYAL_* variables are ignored here
    even when they are exported: BC Bid never goes through IPRoyal.

    Environment:
      PROXY_URL                 the shared Squid proxy, set by the GitHub Actions
                                workflow (user:pass@ is split off)
      BCBID_USE_OPEN_PROXIES    set to 1 to add health-checked free proxies
      BCBID_OPEN_PROXY_LIMIT    how many free proxies to try (default 2)
    """
    attempts = []

    squid = (os.getenv("PROXY_URL") or "").strip()
    if squid:
        squid_url, squid_user, squid_password = split_proxy_credentials(squid)
        attempts.append(ProxyAttempt(
            "squid", proxy_url=squid_url, username=squid_user, password=squid_password,
        ))

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
    """True when an exception looks like a dead proxy rather than a site block."""
    text = f"{type(exc).__name__}: {exc}".lower()
    return any(marker in text for marker in PROXY_ERROR_MARKERS)


async def answer_proxy_auth(browser, username, password):
    """
    Answer the Squid proxy's login prompt for the whole browser session.

    Credentials embedded in --proxy-server only release the first paused request,
    which leaves later page loads hanging.  Copied from the Bonfire scraper's
    proven approach (fetch_tenders_all.enable_proxy_auth).

    Call this *after* tab.apply_fingerprint(): the fingerprint also enables Fetch
    on the browser connection (without auth handling), and whichever Fetch.enable
    runs last wins.
    """
    await browser.enable_fetch_events(handle_auth_requests=True)

    async def release(event):
        # apply_fingerprint() registers its own requestPaused handler on this
        # connection and it releases every paused request. Releasing it a second
        # time fails with "Invalid state for continueInterceptedRequest" on every
        # single request, so leave the request to that handler when it exists.
        if getattr(browser, "_fingerprint_fetch_callback", None) is not None:
            return
        try:
            await browser.continue_request(event["params"]["requestId"])
        except CommandFailed:
            pass  # already released by another handler
        except Exception as exc:
            print(f"[bcbid] could not release paused request: {exc}")

    async def answer_login(event):
        params = event["params"]
        from_proxy = params.get("authChallenge", {}).get("source") == "Proxy"
        try:
            await browser._execute_command(FetchCommands.continue_request_with_auth(
                params["requestId"],
                auth_challenge_response=(
                    AuthChallengeResponseType.PROVIDE_CREDENTIALS if from_proxy
                    else AuthChallengeResponseType.DEFAULT
                ),
                proxy_username=username if from_proxy else None,
                proxy_password=password if from_proxy else None,
            ))
        except Exception as exc:
            print(f"[bcbid] could not answer proxy auth challenge: {exc}")

    await browser.on(FetchEvent.REQUEST_PAUSED, release)
    await browser.on(FetchEvent.AUTH_REQUIRED, answer_login)


def build_fingerprint(chrome_version=None):
    """
    Coherent pydoll v3 fingerprint for BC Bid's invisible reCAPTCHA v3.

    Pydoll does not ship profiles; this one deliberately only overrides fields
    that can be kept consistent with the Canadian egress IP.  Unspecified fields
    keep the real browser's values.  The Chrome version comes from the running
    browser so the UA cannot contradict the real binary.
    """
    # pydoll's browser.get_version() returns a CDP dict; prefer its real UA so
    # the injected identity can never contradict the actual Chrome binary.
    user_agent = ""
    if isinstance(chrome_version, dict):
        user_agent = str(
            chrome_version.get("userAgent")
            or chrome_version.get("User-Agent")
            or ""
        )
        if "HeadlessChrome" in user_agent:
            user_agent = ""
        version = str(
            chrome_version.get("product")
            or chrome_version.get("Browser")
            or ""
        )
    else:
        version = str(chrome_version or "")

    if not user_agent.startswith("Mozilla/"):
        major_source = version or str(os.getenv("BCBID_CHROME_VERSION") or "131")
        major = "".join(
            ch for ch in major_source.split("/")[-1].split(".")[0] if ch.isdigit()
        ) or "131"
        user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            f"(KHTML, like Gecko) Chrome/{major}.0.0.0 Safari/537.36"
        )
    return {
        "user_agent": user_agent,
        "timezone": os.getenv("BCBID_FINGERPRINT_TIMEZONE", "America/Vancouver"),
        "locale": {"languages": ["en-CA", "en"]},
        "screen": {
            "width": 1920,
            "height": 1080,
            "avail_width": 1920,
            "avail_height": 1040,
            "avail_top": 0,
            "outer_width": 1920,
            "outer_height": 1040,
            "color_depth": 24,
            "pixel_depth": 24,
            "device_pixel_ratio": 1.0,
            "orientation_type": "landscape-primary",
            "orientation_angle": 0,
        },
        "hardware": {
            "hardware_concurrency": 8,
            "device_memory": 8,
            "max_touch_points": 0,
        },
    }
