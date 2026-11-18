"""
Offline tests for the Bonfire upload retry logic (no API, no real waiting).

A region whose upload fails is retried after 5 minutes, then after 2 more
minutes using "victoria" as the city/region.
"""
import pandas as pd
import pytest

import upload_tenders


# ------------------------------------------------------------------ upload

@pytest.fixture
def upload_env(tmp_path, monkeypatch):
    """One Bonfire CSV with a fresh tender, a fake API window, and a recorder for sleeps."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("BASE_DIR", str(tmp_path))
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)

    pd.DataFrame([{
        "Status": "Open", "Ref": "RFP-1", "Project": "Road Paving Works", "Type": "RFP",
        "Link": "https://example.com/1", "Project Description": "Paving",
        "Open Date": "Nov 18th 2026, 10:00 AM MST", "Close Date": "Dec 1st 2026, 2:00 PM MST",
        "Days Left": "13", "Contact Information": "",
    }]).to_csv(tmp_path / "bonfire_central_saanich_with_links.csv", index=False)

    window_start = pd.Timestamp("2026-11-17 21:44:35", tz="America/Vancouver").to_pydatetime()
    monkeypatch.setattr(upload_tenders, "get_execution_window", lambda now: (window_start, now))

    sleeps = []
    monkeypatch.setattr(upload_tenders.time, "sleep", lambda s: sleeps.append(s))
    monkeypatch.setattr(upload_tenders, "RETRY_DELAYS_SECONDS", [300, 120])

    embeds = []
    monkeypatch.setattr(upload_tenders, "send_discord_embed", lambda **kw: embeds.append(kw))
    return sleeps, embeds


def _fake_map_data(monkeypatch, outcomes):
    """outcomes: list of 'fail' / 'ok', consumed one per map_data call. Records each call's params."""
    calls = []

    def fake(params):
        calls.append(params)
        outcome = outcomes[len(calls) - 1]
        if outcome == "fail":
            raise ValueError("Expecting value: line 1 column 1 (char 0)")
        return {"inserted_entries": len(params["data"]), "failed_entries": 0, "status": "success"}

    monkeypatch.setattr(upload_tenders, "map_data", fake)
    return calls


def test_upload_succeeds_first_time_without_waiting(upload_env, monkeypatch):
    sleeps, embeds = upload_env
    calls = _fake_map_data(monkeypatch, ["ok"])

    upload_tenders.main()

    assert len(calls) == 1 and sleeps == []
    assert calls[0]["region_name"] == "central saanich"
    summary = embeds[-1]["fields"]
    assert "Failed Regions" not in " ".join(summary)
    assert "1 sent" in summary["🚀 Processed Regions"]


def test_upload_retries_after_5_minutes(upload_env, monkeypatch):
    sleeps, embeds = upload_env
    calls = _fake_map_data(monkeypatch, ["fail", "ok"])

    upload_tenders.main()

    assert sleeps == [300]
    assert [c["region_name"] for c in calls] == ["central saanich", "central saanich"]
    assert "(attempt 2)" in embeds[-1]["fields"]["🚀 Processed Regions"]


def test_upload_falls_back_to_victoria_after_two_failures(upload_env, monkeypatch):
    sleeps, embeds = upload_env
    calls = _fake_map_data(monkeypatch, ["fail", "fail", "ok"])

    upload_tenders.main()

    assert sleeps == [300, 120]
    assert [c["region_name"] for c in calls] == ["central saanich", "central saanich", "victoria"]
    assert all(e["city_name"] == "victoria" for e in calls[2]["data"])
    # earlier attempts must not have been altered by the fallback
    assert all(e["city_name"] == "central saanich" for e in calls[0]["data"])
    assert "as victoria" in embeds[-1]["fields"]["🚀 Processed Regions"]


def test_upload_reports_region_lost_after_three_failures(upload_env, monkeypatch):
    sleeps, embeds = upload_env
    calls = _fake_map_data(monkeypatch, ["fail", "fail", "fail"])

    upload_tenders.main()

    assert len(calls) == 3 and sleeps == [300, 120]
    failed = embeds[-1]["fields"]["🚨 Failed Regions"]
    assert "Central Saanich - Purchasing" in failed and "after 3 attempts" in failed
    assert "**Total Failed:** 1" in embeds[-1]["fields"]["📊 Run Summary"]


def test_upload_api_error_after_insert_is_not_retried(upload_env, monkeypatch):
    """An insert-stage problem comes back as status api_error (not raised): no retry, no duplicates."""
    sleeps, _ = upload_env
    calls = []

    def fake(params):
        calls.append(params)
        return {"inserted_entries": 0, "failed_entries": 0, "status": "api_error"}

    monkeypatch.setattr(upload_tenders, "map_data", fake)
    upload_tenders.main()
    assert len(calls) == 1 and sleeps == []
