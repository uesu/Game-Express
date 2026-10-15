"""Offline tests for truthful source telemetry, redaction, code SHA, and persistence summary."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import gamexpress  # noqa: E402
from gamexpress import runner  # noqa: E402
from gamexpress.config import load_settings  # noqa: E402
from gamexpress.discord import SendResult, WebhookClient  # noqa: E402
from gamexpress.http import (  # noqa: E402
    Fetcher,
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


def test_build_id_prefers_gamexpress_code_sha() -> None:
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


def test_redaction_strips_tokens_pats_and_encoded_webhooks() -> None:
    raw_url = "https://nitter.miningtcup.me/GenshinImpact/rss?token=supersecret123&foo=bar"
    redacted_url = redact_url(raw_url)
    assert "supersecret123" not in redacted_url
    assert "token=<redacted>" in redacted_url

    raw_text = (
        "Webhook https://discord.com/api/webhooks/123456789/abcdefGHIJK_secret "
        "and encoded https%3A%2F%2Fdiscord.com%2Fapi%2Fwebhooks%2F9999%2Fsecret_encoded_tok "
        "and Authorization: Bearer secret_bearer_tok "
        "and PAT ghp_1234567890abcdefghij1234567890 "
        "and https://example.com/feed?api_key=my_secret_key"
    )
    cleaned = redact_text(raw_text)
    assert "abcdefGHIJK_secret" not in cleaned
    assert "secret_encoded_tok" not in cleaned
    assert "secret_bearer_tok" not in cleaned
    assert "ghp_1234567890abcdefghij1234567890" not in cleaned
    assert "my_secret_key" not in cleaned
    assert "https://discord.com/api/webhooks/<redacted>" in cleaned


def test_fetcher_summary_reports_request_level_http_counts() -> None:
    f = Fetcher(session=None)  # type: ignore[arg-type]
    f._mark("nitter", True)
    f._mark("nitter", False, "HTTP 403")
    f._record_event(
        source="nitter",
        url="https://nitter.example/GenshinImpact/rss",
        transport_status="http_ok",
        status_code=200,
    )
    summary = f.summary()
    assert "1 http_200 / 1 transport_fail [1 host(s)]" in summary
    assert "1 ok" not in summary


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


def test_xclient_probe_records_semantic_statuses_truthfully() -> None:
    class StubFetcher:
        def __init__(self) -> None:
            self.events: list[dict] = []

        def last_event_for(self, url_prefix: str, source: str = ""):
            for ev in reversed(self.events):
                if ev["url"].startswith(url_prefix):
                    return ev
            return None

        async def get_text(self, url: str, **_kwargs):
            if "empty.example" in url:
                return "<?xml version='1.0'?><rss><channel><title>ok</title></channel></rss>"
            if "challenge.example" in url:
                return "<html><body>Just a moment... Cloudflare challenge</body></html>"
            if "ratelimit.example" in url:
                self.events.append(
                    {"url": url, "transport_status": "rate_limited", "status_code": 429, "reason": "HTTP 429"}
                )
                return None
            if "timeout.example" in url:
                self.events.append(
                    {"url": url, "transport_status": "timeout", "status_code": None, "reason": "TimeoutError"}
                )
                return None
            if "good1" in url:
                await asyncio.sleep(0.02)
            if "slow.example" in url:
                await asyncio.sleep(5.0)
            if "good" in url:
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
        assert await client._probe("https://empty.example", "GenshinImpact") is None
        assert await client._probe("https://challenge.example", "GenshinImpact") is None
        assert await client._probe("https://ratelimit.example", "GenshinImpact") is None
        assert await client._probe("https://timeout.example", "GenshinImpact") is None

        # Probe batch where good2 and good3 finish first, then higher-ranked good1 finishes within grace
        # -> good1 & good2 are selected, good3 is usable_not_selected, and slow.example is cancelled_after_selection
        res_batch = await client._probe_batch(
            ["https://good1.example", "https://good2.example", "https://good3.example", "https://slow.example"],
            "GenshinImpact",
            2,
        )
        assert len(res_batch) == 2

        by_src = {o["source"]: o for o in client.probe_outcomes}
        assert by_src["nitter:https://empty.example"]["status"] == "transport_ok_zero_items"
        assert by_src["nitter:https://challenge.example"]["status"] == "challenge_or_non_feed"
        assert by_src["nitter:https://ratelimit.example"]["status"] == "rate_limited"
        assert by_src["nitter:https://timeout.example"]["status"] == "timed_out"
        assert by_src["nitter:https://good1.example"]["status"] == "selected"
        assert by_src["nitter:https://good2.example"]["status"] == "selected"
        assert by_src["nitter:https://good3.example"]["status"] == "usable_not_selected"
        assert by_src["nitter:https://slow.example"]["status"] == "cancelled_after_selection"

    asyncio.run(_run())


def test_webhook_instrumentation_preserves_return_values_and_reraises_exceptions() -> None:
    async def _run() -> None:
        wh = WebhookClient(session=None, dry_run=True)  # type: ignore[arg-type]

        calls: list[str] = []

        async def _mock_send(url: str, payload: dict):
            calls.append(url)
            if "fail-bool" in url:
                return False
            if "ok-bool" in url:
                return True
            if "raise-err" in url:
                raise RuntimeError("boom secret https://discord.com/api/webhooks/111/222_tok")
            return SendResult(ok=True, status=200, message_id="m123")

        wh.send = _mock_send  # type: ignore[method-assign]
        runner._instrument_webhook(wh)

        r1 = await wh.send("https://discord.com/api/webhooks/1/ok-bool", {})
        assert r1 is True
        r2 = await wh.send("https://discord.com/api/webhooks/1/fail-bool", {})
        assert r2 is False
        r3 = await wh.send("https://discord.com/api/webhooks/1/deliv-res", {})
        assert isinstance(r3, SendResult) and r3.ok is True

        try:
            await wh.send("https://discord.com/api/webhooks/1/raise-err", {})
        except RuntimeError as exc:
            assert "boom secret" in str(exc)
        else:
            raise AssertionError("Expected RuntimeError to be re-raised unchanged")

        deliveries = getattr(wh, "deliveries", [])
        assert len(deliveries) == 4
        assert [d["ok"] for d in deliveries] == [True, False, True, False]
        assert "222_tok" not in deliveries[3]["error"]
        assert "<redacted>" in deliveries[3]["error"]

    asyncio.run(_run())


def test_run_once_observational_invariants_on_normal_exception_and_save_failure() -> None:
    async def _run() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            state_path = tmp_dir / "state.json"
            report_path = tmp_dir / "run-report.json"
            old_rep = os.environ.get("GAMEXPRESS_RUN_REPORT")
            os.environ["GAMEXPRESS_RUN_REPORT"] = str(report_path)
            try:
                # 1. Passive no-activity run
                settings = load_settings(
                    {
                        "ENABLED_FEATURES": "none",
                        "STATE_PATH": str(state_path),
                        "DRY_RUN": "1",
                    }
                )
                ctx = await runner.run_once(settings, games_all={}, overrides={})
                assert ctx.execution_result == "success"
                assert report_path.is_file()
                rep1 = json.loads(report_path.read_text(encoding="utf-8"))
                assert rep1["execution_result"] == "success"
                assert len(rep1["runs"]) == 1

                # 2. Early unhandled exception inside run_once -> emits single failed report and re-raises
                report_path.unlink()
                settings_live = load_settings(
                    {
                        "ENABLED_FEATURES": "codes",
                        "STATE_PATH": str(state_path),
                        "DRY_RUN": "0",
                    }
                )
                with mock.patch.object(
                    runner, "failover_check", side_effect=ValueError("simulated early crash")
                ):
                    try:
                        await runner.run_once(settings_live, games_all={}, overrides={})
                    except ValueError as exc:
                        assert "simulated early crash" in str(exc)
                    else:
                        raise AssertionError("Expected ValueError to be re-raised")
                assert report_path.is_file()
                rep2 = json.loads(report_path.read_text(encoding="utf-8"))
                assert rep2["execution_result"] == "failed"
                assert rep2["state"]["local_save_outcome"] == "not_reached"
                assert any("simulated early crash" in e for e in rep2["errors"])
                assert len(rep2["runs"]) == 1

                # 3. Local state save failure -> records failed_local, emits report, and re-raises OSError
                report_path.unlink()
                with mock.patch("gamexpress.state.State.save", side_effect=OSError("disk full")):
                    try:
                        await runner.run_once(settings_live, games_all={}, overrides={})
                    except OSError as exc:
                        assert "disk full" in str(exc)
                    else:
                        raise AssertionError("Expected OSError to be re-raised")
                rep3 = json.loads(report_path.read_text(encoding="utf-8"))
                assert rep3["execution_result"] == "failed"
                assert rep3["state"]["local_save_outcome"] == "failed_local"

                # 4. G3: Early initialization failure BEFORE ctx exists (e.g. State.load raising) ->
                # writes failed report with load_status="not_reached", cards="not_reached", targets.attempted="not_reached"
                report_path.unlink()
                with mock.patch("gamexpress.state.State.load", side_effect=RuntimeError("corrupt state init")):
                    try:
                        await runner.run_once(settings_live, games_all={}, overrides={})
                    except RuntimeError as exc:
                        assert "corrupt state init" in str(exc)
                    else:
                        raise AssertionError("Expected RuntimeError to be re-raised")
                rep4 = json.loads(report_path.read_text(encoding="utf-8"))
                assert rep4["execution_result"] == "failed"
                assert rep4["state"]["load_status"] == "not_reached"
                assert rep4["state"]["local_save_outcome"] == "not_reached"
                assert rep4["cards"]["posted"] == "not_reached"
                assert rep4["targets"]["attempted"] == "not_reached"
                assert rep4["sources_summary"] == "not_reached"

                # 5. G3: Report-write error (GAMEXPRESS_RUN_REPORT points to a directory) and malformed
                # GAMEXPRESS_SETUP_DURATION_S must never break run_once or fabricate 0.0s
                bad_dir_report = tmp_dir / "report_is_a_dir"
                bad_dir_report.mkdir(exist_ok=True)
                os.environ["GAMEXPRESS_RUN_REPORT"] = str(bad_dir_report)
                old_setup = os.environ.get("GAMEXPRESS_SETUP_DURATION_S")
                os.environ["GAMEXPRESS_SETUP_DURATION_S"] = "not-a-float"
                try:
                    ctx_ok = await runner.run_once(settings, games_all={}, overrides={})
                    assert ctx_ok.execution_result == "success"
                    built = runner.build_run_report(ctx_ok)
                    assert built["setup_duration_s"] == "unavailable"
                finally:
                    if old_setup is None:
                        os.environ.pop("GAMEXPRESS_SETUP_DURATION_S", None)
                    else:
                        os.environ["GAMEXPRESS_SETUP_DURATION_S"] = old_setup
            finally:
                if old_rep is None:
                    os.environ.pop("GAMEXPRESS_RUN_REPORT", None)
                else:
                    os.environ["GAMEXPRESS_RUN_REPORT"] = old_rep

    asyncio.run(_run())


def test_g3_render_summary_missing_optional_counters_and_not_reached_states() -> None:
    # 1. Early failure report where cards/targets were not reached -> renders `not_reached`, never `posted=0`
    early_report = {
        "schema_version": 1,
        "code_sha": "68529e8",
        "python_version": "3.14.8",
        "runner_image": "ubuntu-24.04",
        "lock_sha256": "abcdef123456",
        "setup_duration_s": "unavailable",
        "mode": "live",
        "only": "all",
        "game": "all",
        "execution_result": "failed",
        "started_at": 1760000000,
        "finished_at": 1760000001,
        "duration_s": 0.5,
        "state": {
            "load_status": "not_reached",
            "save_status": "not_reached",
            "local_save_outcome": "not_reached",
        },
        "cards": {
            "posted": "not_reached",
            "patched": "not_reached",
            "failed": "not_reached",
        },
        "targets": {
            "configured": 2,
            "attempted": "not_reached",
            "usable": "not_reached",
        },
        "errors": ["RuntimeError: corrupt state init"],
    }
    md_early = render_run_summary.render_summary_markdown(
        early_report,
        mode="live",
        run_outcome="failure",
    )
    assert "`posted=not_reached` `patched=not_reached` `failed=not_reached`" in md_early
    assert "posted=0" not in md_early
    assert "`setup=unavailable`" in md_early
    assert "setup=0.0s" not in md_early
    assert "`configured=2` `attempted=not_reached` `usable=not_reached`" in md_early
    assert "| State load status | `not_reached` |" in md_early
    assert "| Local state save | `not_reached` |" in md_early

    # 2. Report missing optional `cards`, `targets`, `state`, and `execution_result` -> explicit `unavailable`
    sparse_report = {
        "schema_version": 1,
        "code_sha": "68529e8",
        "mode": "live",
    }
    md_sparse = render_run_summary.render_summary_markdown(
        sparse_report,
        mode="live",
        run_outcome="success",
    )
    assert "`execution_result=unavailable`" in md_sparse
    assert "`execution_result=success`" not in md_sparse
    assert "| Cards | `unavailable` (card counters missing) |" in md_sparse
    assert "| Targets | `unavailable` |" in md_sparse
    assert "| State load status | `unavailable` |" in md_sparse
    assert "| Local state save | `unavailable` |" in md_sparse


def test_g3_baseline_payload_state_parity_and_measured_overhead() -> None:
    import time

    from gamexpress import cards
    from gamexpress.config import Ping, load_games, load_settings
    from gamexpress.state import stable_hash

    settings = load_settings({})
    games = load_games()
    g = games["genshin"]

    # Verify deterministic schedule & code card payload parity and state hashing
    sched_card = cards.schedule_payload(
        g,
        {
            "version": "5.3",
            "title_url": "https://www.hoyolab.com/article/12345",
            "program_ts": 1735300800,
            "maint_start_ts": 1735682400,
            "maint_end_ts": 1735700400,
            "banners": {},
        },
        settings,
        Ping("<@&123>", {"roles": ["123"]}),
    )
    assert cards.validate_payload(sched_card) == []
    assert stable_hash(sched_card) == stable_hash(json.loads(json.dumps(sched_card)))

    code_card = cards.codes_card(
        g,
        [{"code": "GENSHIN53", "rewards": "Primogem ×100", "verified": True}],
        settings,
        Ping("", {"parse": []}),
        detected_ts=1735300800,
    )
    assert cards.validate_payload(code_card) == []
    assert "GENSHIN53" in json.dumps(code_card)
    assert stable_hash(code_card) == stable_hash(json.loads(json.dumps(code_card)))

    # Measure reporting + summary rendering overhead over 20 iterations (< 50 ms per cycle)
    sample_report = json.loads((FIXTURES / "run_report_sample.json").read_text(encoding="utf-8"))
    t0 = time.perf_counter()
    for _ in range(20):
        md = render_run_summary.render_summary_markdown(
            sample_report,
            mode="live",
            run_outcome="success",
            persist_outcome="no_changes",
        )
        assert "### Game-Express" in md
    avg_ms = ((time.perf_counter() - t0) * 1000.0) / 20.0
    assert avg_ms < 50.0, f"Expected < 50 ms per summary render, got {avg_ms:.2f} ms"


def test_render_run_summary_persistence_outcomes_and_missing_report_truthfulness() -> None:
    report = json.loads((FIXTURES / "run_report_sample.json").read_text(encoding="utf-8"))

    # 1. saved_and_pushed with persistence JSON
    out_saved = render_run_summary.render_summary_markdown(
        report,
        persistence={
            "persist_outcome": "saved_and_pushed",
            "commit_outcome": "committed",
            "push_outcome": "pushed",
            "state_commit_sha": "9999999",
            "persist_duration_s": 2,
        },
        mode="live",
        run_outcome="success",
        persist_outcome="saved_and_pushed",
        code_sha="68529e83fdc2bede720529c35a6fd377b345710a",
        state_commit_sha="9999999888888877777776666666555555544444",
    )
    assert "| Final persistence outcome | **`saved_and_pushed`** |" in out_saved
    assert "| Local state save | `saved_local` |" in out_saved
    assert "| Git commit | `committed` |" in out_saved
    assert "| Remote git push | `pushed` |" in out_saved
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
    assert "| Git commit | `unchanged` |" in out_no_changes
    assert "| Remote git push | `unchanged` |" in out_no_changes

    # 3. commit_failed vs push_failed vs local_save_failed
    out_commit_failed = render_run_summary.render_summary_markdown(
        report,
        persistence={"persist_outcome": "commit_failed", "commit_outcome": "failed", "push_outcome": "not-run"},
        mode="live",
        run_outcome="success",
        persist_outcome="commit_failed",
    )
    assert "| Final persistence outcome | **`commit_failed`** |" in out_commit_failed
    assert "| Git commit | `failed` |" in out_commit_failed
    assert "| Remote git push | `not-run` |" in out_commit_failed

    out_push_failed = render_run_summary.render_summary_markdown(
        report,
        persistence={"persist_outcome": "push_failed", "commit_outcome": "committed", "push_outcome": "failed"},
        mode="live",
        run_outcome="success",
        persist_outcome="push_failed",
        state_commit_sha="9999999",
    )
    assert "| Final persistence outcome | **`push_failed`** |" in out_push_failed
    assert "| Git commit | `committed` |" in out_push_failed
    assert "| Remote git push | `failed` |" in out_push_failed

    # 4. Missing or corrupt report file -> renders `unavailable` instead of fake zero counts (G5)
    out_missing_report = render_run_summary.render_summary_markdown(
        None,
        report_error="missing report file (gamexpress-run-report.json)",
        mode="live",
        run_outcome="failure",
        persist_outcome="",
        code_sha="68529e83fdc2bede720529c35a6fd377b345710a",
        state_commit_sha="",
    )
    assert "| Report status | `unavailable` (missing report file (gamexpress-run-report.json)) |" in out_missing_report
    assert "| Cards | `unavailable` (missing report file (gamexpress-run-report.json)) |" in out_missing_report
    assert "posted=0" not in out_missing_report
    assert "| Final persistence outcome | **`skipped_after_run_failure`** |" in out_missing_report


def test_render_run_summary_cli_writes_step_summary() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        summary_file = Path(tmp) / "step_summary.md"
        persist_file = Path(tmp) / "persistence.json"
        persist_file.write_text(
            json.dumps(
                {
                    "persist_outcome": "saved_and_pushed",
                    "commit_outcome": "committed",
                    "push_outcome": "pushed",
                    "state_commit_sha": "1111111",
                    "persist_duration_s": 3,
                }
            ),
            encoding="utf-8",
        )
        rc = render_run_summary.main(
            [
                "--report",
                str(FIXTURES / "run_report_sample.json"),
                "--persistence",
                str(persist_file),
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
