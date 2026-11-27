"""Offline tests for the BC Bid connection fallback (Squid first, then direct)."""
import asyncio

import pytest

from lib import bcbid_resilience as resilience
from lib import bcbid_scraper as scraper

SQUID = "http://squid-user:s3cret@squid.example:3128"


@pytest.fixture
def clean_env(monkeypatch):
    for name in ("PROXY_URL", "BCBID_USE_OPEN_PROXIES", "BCBID_OPEN_PROXY_LIMIT", "NODRIVER_HEADLESS"):
        monkeypatch.delenv(name, raising=False)


def _proxy_args(options):
    return [arg for arg in options.arguments if arg.startswith("--proxy-server")]


# --- the attempt list -------------------------------------------------------

def test_attempts_are_squid_then_direct(monkeypatch, clean_env):
    monkeypatch.setenv("PROXY_URL", SQUID)
    attempts = resilience.build_proxy_attempts()

    assert [a.name for a in attempts] == ["squid", "direct"]
    assert attempts[0].proxy_url == SQUID  # handed to pydoll as it is, login included
    assert attempts[1].uses_proxy is False

    # One attempt only: it has to be the proxy, not the direct line.
    assert [a.name for a in resilience.build_proxy_attempts(max_attempts=1)] == ["squid"]


def test_without_proxy_url_the_only_attempt_is_direct(monkeypatch, clean_env):
    assert [a.name for a in resilience.build_proxy_attempts()] == ["direct"]

    monkeypatch.setenv("PROXY_URL", "   ")  # an unset GitHub secret arrives empty
    assert [a.name for a in resilience.build_proxy_attempts()] == ["direct"]


def test_iproyal_is_never_used_for_bc_bid(monkeypatch, clean_env):
    """Other scrapers' workflows may still export the IPRoyal secrets."""
    monkeypatch.setenv("PROXY_URL", SQUID)
    monkeypatch.setenv("IPROYAL_USERNAME", "user")
    monkeypatch.setenv("IPROYAL_PASSWORD", "pass")

    attempts = resilience.build_proxy_attempts()

    assert [a.name for a in attempts] == ["squid", "direct"]
    assert not any("iproyal" in str(a).lower() for a in attempts)


def test_open_proxies_are_opt_in(monkeypatch, clean_env):
    assert not any(a.name.startswith("open-proxy") for a in resilience.build_proxy_attempts())

    monkeypatch.setenv("BCBID_USE_OPEN_PROXIES", "1")
    monkeypatch.setattr(resilience, "_healthy_open_proxies", lambda limit: ["http://1.2.3.4:8080"])
    attempts = resilience.build_proxy_attempts()
    assert attempts[-1].name == "open-proxy-1"
    assert attempts[-1].proxy_url == "http://1.2.3.4:8080"


def test_max_attempts_caps_the_list_and_skips_open_proxy_checks(monkeypatch, clean_env):
    monkeypatch.setenv("PROXY_URL", SQUID)
    monkeypatch.setenv("BCBID_USE_OPEN_PROXIES", "1")

    def must_not_run(limit):
        raise AssertionError("health-checked free proxies although the list was already full")

    monkeypatch.setattr(resilience, "_healthy_open_proxies", must_not_run)
    attempts = resilience.build_proxy_attempts(max_attempts=2)
    assert [a.name for a in attempts] == ["squid", "direct"]

    seen = []
    monkeypatch.setattr(resilience, "_healthy_open_proxies",
                        lambda limit: seen.append(limit) or ["http://1.2.3.4:8080"])
    attempts = resilience.build_proxy_attempts(max_attempts=3)
    assert seen == [1]  # only as many as there is room for
    assert [a.name for a in attempts] == ["squid", "direct", "open-proxy-1"]


def test_open_proxy_health_check_is_bounded(monkeypatch, clean_env):
    import requests
    import web_requests

    monkeypatch.setattr(web_requests, "get_proxy_list", lambda: [f"10.0.0.{n}:80" for n in range(200)])
    calls = []

    def dead(url, **kwargs):
        calls.append(kwargs["proxies"]["https"])
        raise requests.ConnectionError("dead")

    monkeypatch.setattr(requests, "get", dead)
    assert resilience._healthy_open_proxies(2) == []
    assert len(calls) == resilience.OPEN_PROXY_MAX_CHECKS


# --- credentials ------------------------------------------------------------

def test_describe_never_shows_proxy_credentials():
    squid = resilience.ProxyAttempt("squid", proxy_url=SQUID)
    assert squid.describe() == "squid (proxy http://***@squid.example:3128)"
    assert "s3cret" not in squid.describe() and "squid-user" not in squid.describe()
    assert resilience.ProxyAttempt("direct").describe() == "direct (direct)"
    plain = resilience.ProxyAttempt("open-proxy-1", proxy_url="http://1.2.3.4:8080")
    assert plain.describe() == "open-proxy-1 (proxy http://1.2.3.4:8080)"
    assert resilience.redact_proxy_url("user:p@ss@10.0.0.1:3128") == "***@10.0.0.1:3128"


def test_pydoll_takes_the_proxy_login_off_the_command_line(clean_env):
    """What we rely on instead of our own proxy login code."""
    from pydoll.browser.managers.proxy_manager import ProxyManager

    options = scraper.get_browser_options(proxy_url=SQUID)
    assert _proxy_args(options) == [f"--proxy-server={SQUID}"]

    has_login, (username, password) = ProxyManager(options).get_proxy_credentials()

    assert has_login is True
    assert (username, password) == ("squid-user", "s3cret")
    assert _proxy_args(options) == ["--proxy-server=http://squid.example:3128"]


# --- failure detection ------------------------------------------------------

@pytest.mark.parametrize("message", [
    "net::ERR_PROXY_CONNECTION_FAILED",
    "net::ERR_TUNNEL_CONNECTION_FAILED",
    "Page.navigate timed out: net::ERR_TIMED_OUT",
    "Navigation to https://bcbid.gov.bc.ca/ failed: net::ERR_TOO_MANY_RETRIES",  # proxy rejects our login
    "Navigation to https://bcbid.gov.bc.ca/ failed: net::ERR_INVALID_AUTH_CREDENTIALS",
])
def test_detects_proxy_failures(message):
    assert resilience.is_proxy_failure(RuntimeError(message))


def test_site_block_and_browser_start_are_not_proxy_failures():
    assert not resilience.is_proxy_failure(scraper.BrowserCheckBlocked("wrong captcha answer"))
    assert not resilience.is_proxy_failure(scraper.FailedToStartBrowser("chrome exited"))


def test_env_numbers_survive_empty_and_bad_values(monkeypatch):
    monkeypatch.setenv("BCBID_OPEN_PROXY_LIMIT", "")  # what GitHub Actions exports for an unset var
    assert resilience.env_int("BCBID_OPEN_PROXY_LIMIT", 2) == 2
    monkeypatch.setenv("BCBID_OPEN_PROXY_LIMIT", "abc")
    assert resilience.env_int("BCBID_OPEN_PROXY_LIMIT", 2) == 2
    monkeypatch.setenv("BCBID_OPEN_PROXY_LIMIT", " 4 ")
    assert resilience.env_int("BCBID_OPEN_PROXY_LIMIT", 2) == 4


# --- the browser each attempt gets ------------------------------------------

def test_browser_options_only_add_proxy_when_attempt_asks(monkeypatch, clean_env):
    monkeypatch.setenv("PROXY_URL", "http://squid.example:3128")

    direct = scraper.get_browser_options(headless=True)
    assert _proxy_args(direct) == []  # PROXY_URL alone must never proxy an attempt
    assert direct.headless is True

    through_proxy = scraper.get_browser_options(proxy_url="http://squid.example:3128")
    assert _proxy_args(through_proxy) == ["--proxy-server=http://squid.example:3128"]
    assert through_proxy.headless is False


def test_browser_identity_is_left_alone(clean_env):
    """No profile: nothing overrides the User-Agent or the browser's languages."""
    options = scraper.get_browser_options(proxy_url=SQUID)
    assert not any(arg.startswith(("--user-agent", "--accept-lang", "--lang")) for arg in options.arguments)
    assert "intl" not in options.browser_preferences
    assert not hasattr(resilience, "build_fingerprint")


def test_each_attempt_launches_chrome_on_its_own_proxy(monkeypatch, clean_env):
    """Each attempt must reach its own proxy: not PROXY_URL for all of them, not the direct line."""
    monkeypatch.setenv("PROXY_URL", SQUID)
    monkeypatch.setenv("BCBID_USE_OPEN_PROXIES", "1")
    monkeypatch.setattr(resilience, "_healthy_open_proxies", lambda limit: ["http://1.2.3.4:8080"])
    launched = []

    class Stop(Exception):
        pass

    def fake_chrome(options=None):
        launched.append(_proxy_args(options))
        raise Stop

    monkeypatch.setattr(scraper, "Chrome", fake_chrome)
    for attempt in resilience.build_proxy_attempts(max_attempts=3):
        with pytest.raises(Stop):
            asyncio.run(scraper.scrape_attempt(attempt))

    assert launched == [
        [f"--proxy-server={SQUID}"],
        [],
        ["--proxy-server=http://1.2.3.4:8080"],
    ]


def test_an_attempt_never_applies_a_fingerprint_profile(monkeypatch, clean_env):
    """apply_fingerprint() would switch off pydoll's proxy login (ERR_INVALID_AUTH_CREDENTIALS)."""
    calls = []

    class Stop(Exception):
        pass

    class Tab:
        async def apply_fingerprint(self, *args, **kwargs):
            calls.append("apply_fingerprint")

        async def go_to(self, url, timeout=None):
            calls.append("go_to")
            raise Stop

    class Browser:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def start(self):
            return Tab()

        async def enable_fetch_events(self, *args, **kwargs):
            calls.append("enable_fetch_events")

    monkeypatch.setattr(scraper, "Chrome", lambda options=None: Browser())
    monkeypatch.setattr(scraper, "FILE_DIR", "screenshots")
    with pytest.raises(Stop):
        asyncio.run(scraper.scrape_attempt(resilience.ProxyAttempt("squid", proxy_url=SQUID)))

    assert calls == ["go_to"]


# --- the runner -------------------------------------------------------------

def test_main_falls_back_to_direct_after_a_browser_check_on_squid(monkeypatch, clean_env):
    attempts = [
        resilience.ProxyAttempt("squid", SQUID),
        resilience.ProxyAttempt("direct"),
    ]
    monkeypatch.setattr(scraper, "build_proxy_attempts", lambda max_attempts=None: attempts)
    monkeypatch.setattr(scraper, "MAX_ATTEMPTS", 2)
    monkeypatch.setattr(scraper.asyncio, "sleep", _no_sleep)
    monkeypatch.setattr(scraper, "_alert", lambda message: alerts.append(message))

    seen, alert_flags = [], []
    calls = 0

    async def fake_scrape(attempt):
        nonlocal calls
        calls += 1
        seen.append(attempt)
        alert_flags.append(scraper.SEND_BLOCK_ALERT)
        if calls == 1:
            error = scraper.BrowserCheckBlocked("browser check: wrong captcha answer")
            error.alerted = False  # alert suppressed on a retry
            raise error

    monkeypatch.setattr(scraper, "scrape_attempt", fake_scrape)
    alerts = []
    asyncio.run(scraper.main())

    assert seen == attempts
    assert alert_flags == [False, True]
    assert alerts == []  # first attempt was a retry, second one succeeded


def test_main_alerts_once_after_all_attempts_fail(monkeypatch, clean_env):
    attempts = [
        resilience.ProxyAttempt("squid", SQUID),
        resilience.ProxyAttempt("direct"),
    ]
    monkeypatch.setattr(scraper, "build_proxy_attempts", lambda max_attempts=None: attempts)
    monkeypatch.setattr(scraper, "MAX_ATTEMPTS", 2)
    monkeypatch.setattr(scraper.asyncio, "sleep", _no_sleep)
    monkeypatch.setattr(scraper, "scrape_attempt", _dead_proxy)
    alerts = []
    monkeypatch.setattr(scraper, "_alert", lambda message: alerts.append(message))

    with pytest.raises(RuntimeError, match="ERR_TIMED_OUT"):
        asyncio.run(scraper.main())

    assert len(alerts) == 1
    assert "2 attempt" in alerts[0]
    assert "s3cret" not in alerts[0]  # the Squid password must not be posted to Discord
    assert scraper.SEND_BLOCK_ALERT is True  # restored for later tests


async def _no_sleep(_seconds):
    return None


async def _dead_proxy(_attempt):
    raise RuntimeError("Page.navigate: net::ERR_TIMED_OUT")
