"""
Offline tests for BC Bid "Browser check" detection (no browser, no network, no real waiting).

When BC Bid serves its reCAPTCHA check page instead of the Opportunities page, the
scraper must stop without reloading, alert Discord, and raise so the job fails.
"""
import asyncio
from pathlib import Path

import pytest

import lib.discord
from lib import bcbid_scraper as scraper

CHECK_PAGE = (Path(__file__).parent / "fixtures" / "bcbid_browser_check.html").read_text(encoding="utf-8")
REJECTED_PAGE = CHECK_PAGE.replace("<h1 class=\"maintitle\">", "<div>Wrong captcha answer. Please try again.</div><h1 class=\"maintitle\">")
OPPORTUNITIES_PAGE = '<html><head><title>Opportunities: BC Bid</title></head><body><h1 class="maintitle">Opportunities</h1></body></html>'
SELECTOR = "//h1[contains(@class, 'maintitle') and contains(text(), 'Opportunities')]"


class FakeTab:
    """Serves a list of pages in order (the last one repeats); the element exists only on Opportunities."""

    def __init__(self, pages):
        self.pages = list(pages)
        self.reads = 0
        self.navigations = []
        self.screenshots = []

    def _current(self):
        return self.pages[min(self.reads, len(self.pages) - 1)]

    async def page_source(self):
        page = self._current()
        self.reads += 1
        return page

    async def query(self, selector, timeout=None, raise_exc=True):
        return object() if self._current() == OPPORTUNITIES_PAGE else None

    async def go_to(self, url, timeout=None):
        self.navigations.append(url)

    async def take_screenshot(self, path, **kwargs):
        self.screenshots.append(path)


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(scraper, "FILE_DIR", str(tmp_path))
    monkeypatch.setattr(scraper, "BROWSER_CHECK_WAIT_SECONDS", 30)
    # Keep these offline tests deterministic even when CI exports proxy secrets.
    monkeypatch.setattr(scraper, "MAX_ATTEMPTS", 1)
    monkeypatch.delenv("PROXY_URL", raising=False)
    monkeypatch.setattr(scraper, "SEND_BLOCK_ALERT", True)
    sleeps, alerts = [], []

    async def fake_sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr(scraper.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(lib.discord, "send_discord_message", lambda msg, url: alerts.append(msg))
    return tmp_path, sleeps, alerts


def test_recognises_the_check_page():
    assert scraper.looks_like_browser_check(CHECK_PAGE)
    assert not scraper.looks_like_browser_check(OPPORTUNITIES_PAGE)
    assert not scraper.looks_like_browser_check("")
    assert scraper.browser_check_rejected(REJECTED_PAGE)
    assert not scraper.browser_check_rejected(CHECK_PAGE)


def test_other_pages_are_left_to_the_normal_recovery(env):
    _, sleeps, alerts = env
    tab = FakeTab(["<html><body>Something else</body></html>"])
    assert asyncio.run(scraper.stop_if_browser_check(tab, SELECTOR, "Region Scan")) is False
    assert sleeps == [] and alerts == []


def test_continues_when_the_check_lets_the_browser_through(env):
    _, _, alerts = env
    tab = FakeTab([CHECK_PAGE, CHECK_PAGE, OPPORTUNITIES_PAGE])
    assert asyncio.run(scraper.stop_if_browser_check(tab, SELECTOR, "Region Scan")) is True
    assert alerts == [] and tab.navigations == []


def test_raises_and_alerts_when_stuck_on_the_check_page(env):
    tmp_path, sleeps, alerts = env
    tab = FakeTab([CHECK_PAGE])
    with pytest.raises(scraper.BrowserCheckBlocked, match="browser check"):
        asyncio.run(scraper.stop_if_browser_check(tab, SELECTOR, "Region Scan"))

    assert sum(sleeps) == 30                      # waited the full window
    assert tab.navigations == []                  # never reloaded
    assert len(alerts) == 1 and "Region Scan" in alerts[0]
    assert (tmp_path / "browser_check_blocked.html").exists()
    assert tab.screenshots == [f"{tmp_path}/browser_check_blocked.png"]


def test_raises_at_once_on_wrong_captcha_answer(env):
    _, sleeps, alerts = env
    tab = FakeTab([REJECTED_PAGE])
    with pytest.raises(scraper.BrowserCheckBlocked, match="wrong captcha answer"):
        asyncio.run(scraper.stop_if_browser_check(tab, SELECTOR, "Region Scan"))
    assert sleeps == [] and len(alerts) == 1


def test_main_stops_with_an_error_and_does_not_reload(env, monkeypatch):
    """Whole scraper: blocked on the first page -> raises, one navigation only, one alert."""
    _, _, alerts = env
    tab = FakeTab([CHECK_PAGE])

    class FakeBrowser:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def start(self):
            return tab

    async def no_element(tab, selector, max_attempts=2):
        return False

    monkeypatch.setattr(scraper, "Chrome", lambda options=None: FakeBrowser())
    monkeypatch.setattr(scraper, "perform_human_loop", no_element)

    with pytest.raises(scraper.BrowserCheckBlocked):
        asyncio.run(scraper.main())

    assert len(tab.navigations) == 1
    assert len(alerts) == 1


def test_dead_proxy_on_the_recovery_reload_fails_the_attempt(env, monkeypatch):
    """Page never became Opportunities and the reload dies: raise, don't 'succeed' with no data."""
    tab = FakeTab(["<html><body>Something else</body></html>"])

    async def go_to(url, timeout=None):
        tab.navigations.append(url)
        if len(tab.navigations) > 1:
            raise RuntimeError(f"Navigation to {url} failed: net::ERR_PROXY_CONNECTION_FAILED")

    tab.go_to = go_to

    class FakeBrowser:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def start(self):
            return tab

    async def no_element(tab, selector, max_attempts=2):
        return False

    monkeypatch.setattr(scraper, "Chrome", lambda options=None: FakeBrowser())
    monkeypatch.setattr(scraper, "perform_human_loop", no_element)
    monkeypatch.setattr(scraper, "_alert", lambda message: None)

    with pytest.raises(RuntimeError, match="ERR_PROXY_CONNECTION_FAILED"):
        asyncio.run(scraper.main())
    assert len(tab.navigations) == 2
