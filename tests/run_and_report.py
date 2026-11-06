"""
Run the scraper test suite and post a summary to Discord.

Usage:  python -m tests.run_and_report [extra pytest args]
Env:    DISCORD_WEBHOOK_URL - where to post (skipped if unset)
Exits with pytest's exit code so the GitHub Action fails when tests fail.
"""
import os
import sys

import pytest

from lib.discord import send_discord_embed

GREEN, RED = 3066993, 15158332


class _Collector:
    def __init__(self):
        self.passed, self.failed, self.skipped = [], [], []

    def pytest_runtest_logreport(self, report):
        name = report.nodeid.split("::", 1)[-1]
        if report.failed:
            # Errors in fixtures (e.g. site down) surface in setup, so count every phase
            message = str(report.longrepr.reprcrash.message) if hasattr(report.longrepr, "reprcrash") else str(report.longrepr)
            self.failed.append((name, message.splitlines()[0][:300]))
        elif report.when == "call" and report.passed:
            self.passed.append(name)
        elif report.skipped:
            self.skipped.append(name)


def main(args):
    collector = _Collector()
    exit_code = pytest.main(["-v", *args], plugins=[collector])

    run_url = ""
    if os.getenv("GITHUB_RUN_ID"):
        run_url = f"{os.getenv('GITHUB_SERVER_URL', 'https://github.com')}/{os.getenv('GITHUB_REPOSITORY')}/actions/runs/{os.getenv('GITHUB_RUN_ID')}"

    total = len(collector.passed) + len(collector.failed)
    if exit_code == 0:
        title = "✅ Scraper tests: all tests passed"
        description = f"All {len(collector.passed)} tests passed for RDN, Port Hardy, SRD (scr) and CanadaBuys."
        fields = {}
        color = GREEN
    else:
        title = "❌ Scraper tests: failures detected"
        description = (f"{len(collector.failed)} of {total} tests failed. "
                       "A site's page structure/styling may have changed - check the matching scraper.")
        failures = "\n".join(f"• **{name}**: {msg}" for name, msg in collector.failed) or f"pytest exit code {exit_code}"
        fields = {"Failures": failures[:1000]}
        color = RED

    if collector.skipped:
        fields["Skipped"] = ", ".join(collector.skipped)[:1000]
    if run_url:
        fields["Run"] = run_url

    print(f"\n{title}\n{description}")
    send_discord_embed(os.getenv("DISCORD_WEBHOOK_URL"), title, description, fields, color=color)
    return int(exit_code)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
