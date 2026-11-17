"""Offline tests for lib/browser_fallback.py (no real browser is started)."""
import asyncio

import pytest

from lib.browser_fallback import build_attempts, run_with_fallback
from lib.hardy.scraper import get_browser_options as hardy_options
from lib.rdn.scraper import get_browser_options as rdn_options

PROXY = "http://user:pass@proxy.example:12321"


class FakeBrowser:
    """Stands in for pydoll's Chrome; records the options of each attempt."""
    launched = []

    def __init__(self, options):
        self.options = options
        FakeBrowser.launched.append(options)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def start(self):
        return f"tab-{len(FakeBrowser.launched)}"


def _make_options(headless, use_proxy):
    return {"headless": headless, "use_proxy": use_proxy}


def _scrape_failing_until(success_on):
    calls = []

    async def scrape(tab):
        calls.append(tab)
        if len(calls) < success_on:
            raise RuntimeError("net::ERR_TIMED_OUT")
        return f"ok-{tab}"

    return scrape, calls


@pytest.fixture(autouse=True)
def _reset(monkeypatch, tmp_path):
    FakeBrowser.launched = []
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "summary.md"))


def _run(scrape):
    return asyncio.run(run_with_fallback(scrape, _make_options, label="test", browser_cls=FakeBrowser, pause_seconds=0))


def test_attempt_order_with_proxy():
    attempts = build_attempts(PROXY)
    assert [a.name for a in attempts] == ["original", "headless", "headed", "proxy"]
    assert [(a.headless, a.use_proxy) for a in attempts] == [(None, False), (True, False), (False, False), (False, True)]


def test_proxy_attempt_skipped_without_proxy_url():
    assert [a.name for a in build_attempts(None)] == ["original", "headless", "headed"]


def test_first_attempt_success_runs_once(monkeypatch, tmp_path):
    monkeypatch.setenv("PROXY_URL", PROXY)
    scrape, calls = _scrape_failing_until(1)
    assert _run(scrape) == "ok-tab-1"
    assert len(calls) == 1
    assert "Attempt 1 (original" in (tmp_path / "summary.md").read_text()


def test_falls_through_to_proxy(monkeypatch, tmp_path):
    monkeypatch.setenv("PROXY_URL", PROXY)
    scrape, calls = _scrape_failing_until(4)
    assert _run(scrape) == "ok-tab-4"
    assert FakeBrowser.launched == [
        {"headless": None, "use_proxy": False},
        {"headless": True, "use_proxy": False},
        {"headless": False, "use_proxy": False},
        {"headless": False, "use_proxy": True},
    ]
    assert "Attempt 4 (proxy (headed, proxy))" in (tmp_path / "summary.md").read_text()


def test_all_attempts_fail_reraises(monkeypatch):
    monkeypatch.delenv("PROXY_URL", raising=False)
    scrape, calls = _scrape_failing_until(99)
    with pytest.raises(RuntimeError, match="ERR_TIMED_OUT"):
        _run(scrape)
    assert len(calls) == 3


@pytest.mark.parametrize("make_options", [hardy_options, rdn_options])
def test_scraper_options_respect_headless_and_proxy(monkeypatch, make_options):
    monkeypatch.setenv("PROXY_URL", PROXY)

    original = make_options()
    assert f"--proxy-server={PROXY}" in original.arguments
    assert original.headless is False

    direct_headless = make_options(headless=True, use_proxy=False)
    assert direct_headless.headless is True
    assert not any(a.startswith("--proxy-server") for a in direct_headless.arguments)

    proxied = make_options(headless=False, use_proxy=True)
    assert proxied.headless is False
    assert f"--proxy-server={PROXY}" in proxied.arguments
