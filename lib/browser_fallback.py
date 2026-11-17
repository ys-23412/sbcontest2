"""
Retry a pydoll scrape with progressively different browser setups.

Used by the Port Hardy and RDN scrapers. Order of attempts:

  1. original  - the scraper's usual options (default non-headless mode), direct connection
  2. headless  - headless=True, direct connection
  3. headed    - headless=False, direct connection
  4. proxy     - headless=False through PROXY_URL, in a fresh browser session
                 (skipped when PROXY_URL is not set)

The proxy is only used as the last resort. It is a single small Squid VM shared by
several jobs (see README), and when it is busy or unhealthy every page load through it
fails with net::ERR_TIMED_OUT - which is what took down BC Bid, RDN and Port Hardy on
2026-11-17. Going direct first keeps these two scrapers off the proxy unless a site
actually blocks the runner.

Each attempt runs the whole scrape in its own browser. If every attempt fails, the last
error is re-raised so the job still fails.
"""
import asyncio
import os
from dataclasses import dataclass

from pydoll.browser.chromium import Chrome


@dataclass(frozen=True)
class Attempt:
    name: str
    headless: bool | None  # None = leave the scraper's default untouched
    use_proxy: bool

    def describe(self, proxy_url):
        mode = "default" if self.headless is None else ("headless" if self.headless else "headed")
        via = "proxy" if (self.use_proxy and proxy_url) else "direct"
        return f"{self.name} ({mode}, {via})"


def build_attempts(proxy_url):
    attempts = [
        Attempt("original", headless=None, use_proxy=False),
        Attempt("headless", headless=True, use_proxy=False),
        Attempt("headed", headless=False, use_proxy=False),
    ]
    if proxy_url:
        attempts.append(Attempt("proxy", headless=False, use_proxy=True))
    return attempts


def _write_step_summary(line):
    """Append a line to the GitHub Actions job summary when running in CI."""
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


async def run_with_fallback(scrape, make_options, label="scraper", browser_cls=Chrome, pause_seconds=5):
    """
    Run `await scrape(tab)` with each browser setup in turn until one succeeds.

    scrape:       async function taking a started pydoll tab
    make_options: function(headless=..., use_proxy=...) -> ChromiumOptions
    """
    proxy_url = os.environ.get("PROXY_URL")
    attempts = build_attempts(proxy_url)
    if not proxy_url:
        print(f"[{label}] PROXY_URL not set - the proxy attempt will be skipped.")

    failures = []
    for number, attempt in enumerate(attempts, 1):
        description = attempt.describe(proxy_url)
        print(f"[{label}] Attempt {number}/{len(attempts)}: {description}")
        try:
            options = make_options(headless=attempt.headless, use_proxy=attempt.use_proxy)
            async with browser_cls(options=options) as browser:
                print("Starting browser...")
                tab = await browser.start()
                result = await scrape(tab)
        except Exception as exc:  # noqa: BLE001 - any failure moves on to the next setup
            failures.append((description, exc))
            print(f"[{label}] Attempt {number} ({attempt.name}) failed: {type(exc).__name__}: {exc}")
            if number < len(attempts):
                await asyncio.sleep(pause_seconds)
            continue

        message = f"[{label}] Attempt {number} ({description}) succeeded."
        print(message)
        _write_step_summary(message)
        return result

    print(f"[{label}] All {len(attempts)} attempts failed:")
    for description, exc in failures:
        print(f"  - {description}: {type(exc).__name__}: {exc}")
    _write_step_summary(f"[{label}] All {len(attempts)} attempts failed.")
    raise failures[-1][1]
