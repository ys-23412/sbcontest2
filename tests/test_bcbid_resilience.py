"""Offline tests for BC Bid proxy failover and pydoll v3 stealth wiring."""
import asyncio

import pytest

from lib import bcbid_resilience as resilience
from lib import bcbid_scraper as scraper


@pytest.fixture
def clean_env(monkeypatch):
    for name in ("PROXY_URL", "BCBID_USE_OPEN_PROXIES", "BCBID_OPEN_PROXY_LIMIT"):
        monkeypatch.delenv(name, raising=False)


def test_attempts_are_squid_then_direct(monkeypatch, clean_env):
    monkeypatch.setenv("PROXY_URL", "http://user:pass@squid.example:3128")
    attempts = resilience.build_proxy_attempts()

    assert [a.name for a in attempts] == ["squid", "direct"]
    # Squid's user:pass@ is split off and answered by answer_proxy_auth (pydoll's
    # own handling of embedded credentials breaks once a fingerprint is applied).
    assert attempts[0].proxy_url == "http://squid.example:3128"
    assert (attempts[0].username, attempts[0].password) == ("user", "pass")
    assert attempts[1].uses_proxy is False
    assert not any("pass" in a.describe() for a in attempts)
    assert all(a.headless is False for a in attempts)

    # One attempt only: it has to be the proxy, not the direct line.
    assert [a.name for a in resilience.build_proxy_attempts(max_attempts=1)] == ["squid"]


def test_without_proxy_url_the_only_attempt_is_direct(monkeypatch, clean_env):
    assert [a.name for a in resilience.build_proxy_attempts()] == ["direct"]

    monkeypatch.setenv("PROXY_URL", "   ")  # an unset GitHub secret arrives empty
    assert [a.name for a in resilience.build_proxy_attempts()] == ["direct"]


def test_iproyal_is_never_used_for_bc_bid(monkeypatch, clean_env):
    """The workflows may still export the IPRoyal secrets for other scrapers."""
    monkeypatch.setenv("PROXY_URL", "http://squid.example:3128")
    monkeypatch.setenv("IPROYAL_USERNAME", "user")
    monkeypatch.setenv("IPROYAL_PASSWORD", "pass")
    monkeypatch.setenv("BCBID_IPROYAL_SESSIONS", "2")

    attempts = resilience.build_proxy_attempts()

    assert [a.name for a in attempts] == ["squid", "direct"]
    assert not any("iproyal" in str(a).lower() for a in attempts)


def test_max_attempts_caps_the_list_and_skips_open_proxy_checks(monkeypatch, clean_env):
    monkeypatch.setenv("PROXY_URL", "http://squid.example:3128")
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


def test_describe_never_shows_proxy_credentials():
    squid = resilience.ProxyAttempt("squid", proxy_url="http://user:s3cret@squid.example:3128")
    assert squid.describe() == "squid (proxy http://***@squid.example:3128)"
    assert "s3cret" not in squid.describe() and "user" not in squid.describe()
    assert resilience.ProxyAttempt("direct").describe() == "direct (direct)"
    plain = resilience.ProxyAttempt("open-proxy-1", proxy_url="http://1.2.3.4:8080")
    assert plain.describe() == "open-proxy-1 (proxy http://1.2.3.4:8080)"


def test_proxy_credentials_are_split_off_the_url():
    split = resilience.split_proxy_credentials
    assert split("http://user:p%40ss@squid.example:3128") == ("http://squid.example:3128", "user", "p%40ss")
    assert split("http://user:p@ss:word@10.0.0.1:3128") == ("http://10.0.0.1:3128", "user", "p@ss:word")
    assert split("user:pass@10.0.0.1:3128") == ("10.0.0.1:3128", "user", "pass")
    assert split("http://squid.example:3128") == ("http://squid.example:3128", None, None)
    assert split("socks5://1.2.3.4:1080") == ("socks5://1.2.3.4:1080", None, None)


def test_env_numbers_survive_empty_and_bad_values(monkeypatch):
    monkeypatch.setenv("BCBID_OPEN_PROXY_LIMIT", "")  # what GitHub Actions exports for an unset var
    assert resilience.env_int("BCBID_OPEN_PROXY_LIMIT", 2) == 2
    monkeypatch.setenv("BCBID_OPEN_PROXY_LIMIT", "abc")
    assert resilience.env_int("BCBID_OPEN_PROXY_LIMIT", 2) == 2
    monkeypatch.setenv("BCBID_OPEN_PROXY_LIMIT", " 4 ")
    assert resilience.env_int("BCBID_OPEN_PROXY_LIMIT", 2) == 4


def test_open_proxies_are_opt_in(monkeypatch, clean_env):
    assert not any(a.name.startswith("open-proxy") for a in resilience.build_proxy_attempts())

    monkeypatch.setenv("BCBID_USE_OPEN_PROXIES", "1")
    monkeypatch.setattr(resilience, "_healthy_open_proxies", lambda limit: ["http://1.2.3.4:8080"])
    attempts = resilience.build_proxy_attempts()
    assert attempts[-1].name == "open-proxy-1"
    assert attempts[-1].proxy_url == "http://1.2.3.4:8080"


@pytest.mark.parametrize("message", [
    "net::ERR_PROXY_CONNECTION_FAILED",
    "net::ERR_TUNNEL_CONNECTION_FAILED",
    "Page.navigate timed out: net::ERR_TIMED_OUT",
    "Navigation to https://bcbid.gov.bc.ca/ failed: net::ERR_TOO_MANY_RETRIES",  # proxy rejects our login
    "Navigation to https://bcbid.gov.bc.ca/ failed: net::ERR_INVALID_AUTH_CREDENTIALS",
    "FailedToStartBrowser: chrome exited",
])
def test_detects_proxy_failures(message):
    assert resilience.is_proxy_failure(RuntimeError(message))


def test_site_block_is_not_a_proxy_failure():
    assert not resilience.is_proxy_failure(scraper.BrowserCheckBlocked("wrong captcha answer"))


def test_fingerprint_uses_real_chrome_version_and_canadian_locale(monkeypatch):
    fingerprint = resilience.build_fingerprint("Chrome/140.0.7339.80")
    assert "Chrome/140." in fingerprint["user_agent"]
    assert fingerprint["timezone"] == "America/Vancouver"
    assert fingerprint["locale"]["languages"] == ["en-CA", "en"]
    assert fingerprint["screen"]["width"] == 1920
    assert "geolocation" not in fingerprint  # never contradict the proxy's real location

    monkeypatch.setenv("BCBID_FINGERPRINT_TIMEZONE", "America/Toronto")
    assert resilience.build_fingerprint()["timezone"] == "America/Toronto"

    # browser.get_version() returns a CDP dict in pydoll v3, incl. headless UA.
    version = {
        "product": "Chrome/158.0.8127.88",
        "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) HeadlessChrome/158.0.0.0",
    }
    ua = resilience.build_fingerprint(version)["user_agent"]
    assert "Chrome/158." in ua and "HeadlessChrome" not in ua


def _proxy_args(options):
    return [arg for arg in options.arguments if arg.startswith("--proxy-server")]


def test_browser_options_only_add_proxy_when_attempt_asks(monkeypatch, clean_env):
    monkeypatch.setenv("PROXY_URL", "http://squid.example:3128")

    direct = scraper.get_browser_options(headless=True)
    assert _proxy_args(direct) == []  # PROXY_URL alone must never proxy an attempt
    assert direct.headless is True

    through_proxy = scraper.get_browser_options(headless=False, proxy_url="http://squid.example:3128")
    assert _proxy_args(through_proxy) == ["--proxy-server=http://squid.example:3128"]
    assert through_proxy.headless is False


def test_each_attempt_launches_chrome_on_its_own_proxy(monkeypatch, clean_env):
    """Each attempt must reach its own proxy: not PROXY_URL for all of them, not the direct line."""
    monkeypatch.setenv("PROXY_URL", "http://squid-user:squid-pass@squid.example:3128")
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
        ["--proxy-server=http://squid.example:3128"],  # credentials never reach the command line
        [],
        ["--proxy-server=http://1.2.3.4:8080"],
    ]


class FakeAuthBrowser:
    """Records what answer_proxy_auth sends over the browser connection."""

    def __init__(self, fingerprint_handler=None):
        self._fingerprint_fetch_callback = fingerprint_handler
        self.handlers, self.continued, self.commands, self.fetch = {}, [], [], []

    async def enable_fetch_events(self, handle_auth_requests=False):
        self.fetch.append(handle_auth_requests)

    async def on(self, event, callback):
        self.handlers[event] = callback

    async def continue_request(self, request_id):
        self.continued.append(request_id)

    async def _execute_command(self, command):
        self.commands.append(command)


def test_proxy_auth_answers_only_the_proxy_and_releases_requests_once():
    from pydoll.protocol.fetch.events import FetchEvent

    async def run(browser):
        await resilience.answer_proxy_auth(browser, "user", "pass")
        await browser.handlers[FetchEvent.REQUEST_PAUSED]({"params": {"requestId": "r1"}})
        await browser.handlers[FetchEvent.AUTH_REQUIRED](
            {"params": {"requestId": "r2", "authChallenge": {"source": "Proxy"}}})
        await browser.handlers[FetchEvent.AUTH_REQUIRED](
            {"params": {"requestId": "r3", "authChallenge": {"source": "Server"}}})
        return browser

    plain = asyncio.run(run(FakeAuthBrowser()))
    assert plain.fetch == [True]
    assert plain.continued == ["r1"]
    proxy_answer, site_answer = (c["params"]["authChallengeResponse"] for c in plain.commands)
    assert proxy_answer == {"response": "ProvideCredentials", "username": "user", "password": "pass"}
    assert site_answer == {"response": "Default"}  # never hand proxy credentials to a website

    # With a fingerprint applied, pydoll already releases every paused request;
    # releasing it again fails on every request.
    fingerprinted = asyncio.run(run(FakeAuthBrowser(fingerprint_handler=7)))
    assert fingerprinted.continued == []
    assert len(fingerprinted.commands) == 2


def test_main_falls_back_to_direct_after_a_browser_check_on_squid(monkeypatch, clean_env):
    attempts = [
        resilience.ProxyAttempt("squid", "http://squid.example:3128", "user", "pass"),
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


def test_main_alerts_once_after_all_proxies_fail(monkeypatch, clean_env):
    attempts = [
        resilience.ProxyAttempt("squid", "http://user:s3cret@squid:3128"),
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
