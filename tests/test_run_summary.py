"""Offline tests for truthful source telemetry, redaction, code SHA, and persistence summary."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import gamexpress  # noqa: E402
from gamexpress.config import load_settings  # noqa: E402
from gamexpress.http import (  # noqa: E402
     classify_transport_status,
    redact_text,
    redact_url,
    summarize_source_outcome,
)
from gamexpress.sources.twitter import XClient  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "maintenance"


def _load_renderer():
    path = ROOT / ".github" / "scripts" / "render_run_summary.py"
    spec = importlib.util.spec_from_file_location("render_run_summary", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


render_run_summary = _load_renderer()


def test_build_id_prefers_gamexpress_code_sha(monkeypatch=None) -> None:
    import os

    old_code = os.environ.get("GAMEXPRESS_CODE_SHA")
    old_gh = os.environ.get("GITHUB_SHA")
    try:
        os.environ["GAMEXPRESS_CODE_SHA"] = "68529e83fdc2bede720529c35a6fd377b345710a"
        os.environ["GITHUB_SHA"] = "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
        assert gamexpress.build_id() == "68529e8"

        os.environ.pop("GAMEXPRESS_CODE_SHA", None)
        assert gamexpress.build_id() == "deadbee"
    finally:
        if old_code is None:
            os.environ.pop("GAMEXPRESS_CODE_SHA", None)
        else:
            os.environ["GAMEXPRESS_CODE_SHA"] = old_code
        if old_gh is None:
            os.environ.pop("GITHUB_SHA", None)
        else:
            os.environ["GITHUB_SHA"] = old_gh


def test_redaction_strips_tokens_and_webhooks() -> None:
    raw_url = "https://nitter.miningtcup.me/GenshinImpact/rss?token=supersecret123&foo=bar"
    redacted_url = redact_url(raw_url)
    assert "supersecret123" not in redacted_url
    assert "token=<redacted>" in redacted_url

    raw_text = (
        "Webhook https://discord.com/api/webhooks/123456789/abcdefGHIJK_secret "
        "and Authorization: Bearer secret_bearer_tok "
        "and https://example.com/feed?api_key=my_secret_key"
    )
    cleaned = redact_text(raw_text)
    assert "abcdefGHIJK_secret" not in cleaned
    assert "secret_bearer_tok" not in cleaned
    assert "my_secret_key" not in cleaned
    assert "https://discord.com/api/webhooks/<redacted>" in cleaned


def test_source_outcome_distinguishes_transport_and_parsed_items() -> None:
    # 1. HTTP 200 with valid non-empty items and selected > 0
    o1 = summarize_source_outcome(
        source="hoyolab:getNewsList",
        lane="schedule",
        game="genshin",
        transport_status="http_ok",
        parsed_count=15,
        usable_count=12,
        selected_count=2,
    )
    assert o1["transport_status"] == "http_ok"
    assert o1["status"] == "selected"
    assert (o1["parsed_count"], o1["usable_count"], o1["selected_count"]) == (15, 12, 2)

    # 2. HTTP 200 with 0 parsed items -> transport_ok_zero_items
    o2 = summarize_source_outcome(
        source="nitter:https://tw.eir-nya.gay",
        lane="x_timeline",
        game="GenshinImpact",
        transport_status="http_ok",
        parsed_count=0,
        usable_count=0,
        selected_count=0,
        reason="http_200_zero_entries",
    )
    assert o2["transport_status"] == "http_ok"
    assert o2["status"] == "transport_ok_zero_items"

    # 3. HTTP 200 with parse_empty -> parse_empty
    o3 = summarize_source_outcome(
        source="broken:xml",
        lane="schedule",
        game="zzz",
        transport_status="http_ok",
        parsed_count=0,
        parse_empty=True,
    )
    assert o3["transport_status"] == "http_ok"
    assert o3["status"] == "parse_empty"

    # 4. HTTP 403 / 429 / timeout -> source_failed
    assert classify_transport_status(status_code=200) == "http_ok"
    assert classify_transport_status(status_code=304) == "not_modified"
    assert classify_transport_status(status_code=429) == "rate_limited"
    assert classify_transport_status(status_code=403) == "http_status"
    assert classify_transport_status(error="TimeoutError: timed out") == "timeout"

    o4 = summarize_source_outcome(
        source="nitter:https://xcopy.uk",
        lane="x_timeline",
        game="GenshinImpact",
        transport_status=classify_transport_status(status_code=403),
        reason="HTTP 403",
    )
    assert o4["transport_status"] == "http_status"
    assert o4["status"] == "source_failed"


def test_xclient_probe_records_zero_entry_rss_truthfully() -> None:
    class StubFetcher:
        async def get_text(self, url: str, **_kwargs):
            if "empty.example" in url:
                return "<?xml version='1.0'?><rss><channel><title>ok</title></channel></rss>"
            if "good.example" in url:
                return (
                    "<?xml version='1.0'?><rss><channel>"
                    "<item><title>Post 1</title><link>https://x.com/a/status/1234567890</link>"
                    "<pubDate>Wed, 15 Oct 2026 10:00:00 GMT</pubDate></item>"
                    "</channel></rss>"
                )
            return None

    async def _run() -> None:
        settings = load_settings({})
        client = XClient(StubFetcher(), settings)
        entries_empty = await client._probe("https://empty.example", "GenshinImpact")
        entries_good = await client._probe("https://good.example", "GenshinImpact")
        assert entries_empty is None
        assert entries_good is not None and len(entries_good) == 1
        by_src = {o["source"]: o for o in client.probe_outcomes}
        assert by_src["nitter:https://empty.example"]["status"] == "transport_ok_zero_items"
        assert by_src["nitter:https://empty.example"]["parsed_count"] == 0
        assert by_src["nitter:https://good.example"]["status"] == "selected"
        assert by_src["nitter:https://good.example"]["parsed_count"] == 1

    asyncio.run(_run())


def test_render_run_summary_all_six_persistence_outcomes() -> None:
    report = json.loads((FIXTURES / "run_report_sample.json").read_text(encoding="utf-8"))

    # 1. saved_and_pushed
    out_saved = render_run_summary.render_summary_markdown(
        report,
        mode="live",
        run_outcome="success",
        persist_outcome="saved_and_pushed",
        code_sha="68529e83fdc2bede720529c35a6fd377b345710a",
        state_commit_sha="9999999888888877777776666666555555544444",
    )
    assert "| Final persistence outcome | **`saved_and_pushed`** |" in out_saved
    assert "| Checked-out `code_sha` | `68529e8` |" in out_saved
    assert "| Committed `state_commit_sha` | `9999999` |" in out_saved
    assert "transport_ok_zero_items" in out_saved
    assert "secret_token_xyz" not in out_saved

    # 2. no_changes
    out_no_changes = render_run_summary.render_summary_markdown(
        report,
        mode="live",
        run_outcome="success",
        persist_outcome="no_changes",
        code_sha="68529e83fdc2bede720529c35a6fd377b345710a",
        state_commit_sha="",
    )
    assert "| Final persistence outcome | **`no_changes`** |" in out_no_changes
    assert "| Committed `state_commit_sha` | `none` |" in out_no_changes

    # 3. skipped_test_mode
    out_test = render_run_summary.render_summary_markdown(
        report,
        mode="test",
        run_outcome="success",
        persist_outcome="",
        code_sha="68529e83fdc2bede720529c35a6fd377b345710a",
        state_commit_sha="",
    )
    assert "| Final persistence outcome | **`skipped_test_mode`** |" in out_test

    # 4. skipped_after_run_failure
    out_failed_run = render_run_summary.render_summary_markdown(
        None,
        mode="live",
        run_outcome="failure",
        persist_outcome="",
        code_sha="68529e83fdc2bede720529c35a6fd377b345710a",
        state_commit_sha="",
    )
    assert "| Final persistence outcome | **`skipped_after_run_failure`** |" in out_failed_run

    # 5. push_failed
    out_push_failed = render_run_summary.render_summary_markdown(
        report,
        mode="live",
        run_outcome="success",
        persist_outcome="push_failed",
        code_sha="68529e83fdc2bede720529c35a6fd377b345710a",
        state_commit_sha="9999999888888877777776666666555555544444",
    )
    assert "| Final persistence outcome | **`push_failed`** |" in out_push_failed

    # 6. push_skipped
    out_push_skipped = render_run_summary.render_summary_markdown(
        report,
        mode="live",
        run_outcome="success",
        persist_outcome="push_skipped",
        code_sha="68529e83fdc2bede720529c35a6fd377b345710a",
        state_commit_sha="",
    )
    assert "| Final persistence outcome | **`push_skipped`** |" in out_push_skipped


def test_render_run_summary_cli_writes_step_summary() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        summary_file = Path(tmp) / "step_summary.md"
        rc = render_run_summary.main(
            [
                "--report",
                str(FIXTURES / "run_report_sample.json"),
                "--output",
                str(summary_file),
                "--mode",
                "live",
                "--run-outcome",
                "success",
                "--persist-outcome",
                "saved_and_pushed",
                "--code-sha",
                "68529e83fdc2bede720529c35a6fd377b345710a",
                "--state-commit-sha",
                "1111111222222233333334444444555555566666",
            ]
        )
        assert rc == 0
        written = summary_file.read_text(encoding="utf-8")
        assert "#### State & Persistence Footer" in written
        assert "| Final persistence outcome | **`saved_and_pushed`** |" in written


if __name__ == "__main__":
    tests = [
        v for k, v in list(globals().items()) if k.startswith("test_") and callable(v)
    ]
    failed = 0
    for fn in tests:
        try:
            fn()
        except Exception as exc:
            failed += 1
            print(f"FAIL {fn.__name__}: {exc}", file=sys.stderr)
    print(f"{len(tests) - failed}/{len(tests)} passed, {failed} failed")
    sys.exit(1 if failed else 0)
