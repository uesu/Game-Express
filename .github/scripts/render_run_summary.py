#!/usr/bin/env python3
"""Render GitHub Actions `GITHUB_STEP_SUMMARY` and final persistence footer for monitor runs."""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import platform
import sys
from typing import Any

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gamexpress.http import redact_text, redact_url, redact_value  # noqa: E402

PERSISTENCE_OUTCOMES = frozenset(
    {
        "saved_and_pushed",
        "no_changes",
        "skipped_test_mode",
        "skipped_after_run_failure",
        "local_save_failed",
        "commit_failed",
        "push_failed",
        "push_skipped",
    }
)


def resolve_persistence_outcome(
    *,
    mode: str = "live",
    run_outcome: str = "success",
    persist_outcome: str = "",
    state_save_status: str = "unchanged_local",
    state_commit_sha: str = "",
    commit_outcome: str = "",
    push_outcome: str = "",
) -> str:
    """Compute the canonical final persistence status for a monitor workflow run."""
    norm_mode = (mode or "live").strip().lower()
    norm_run = (run_outcome or "success").strip().lower()
    norm_persist = (persist_outcome or "").strip().lower()
    norm_save = (state_save_status or "unchanged_local").strip().lower()
    norm_commit = (commit_outcome or "").strip().lower()
    norm_push = (push_outcome or "").strip().lower()
    has_commit = bool((state_commit_sha or "").strip())

    if norm_mode in ("test", "dry_run"):
        return "skipped_test_mode"
    if norm_save == "failed_local":
        return "local_save_failed"
    if norm_commit == "failed" or norm_persist == "commit_failed":
        return "commit_failed"
    if norm_push == "failed" or norm_persist == "push_failed":
        return "push_failed"
    if norm_run in ("failure", "cancelled", "timed_out", "error") and norm_persist in ("", "skipped"):
        return "skipped_after_run_failure"
    if norm_persist in PERSISTENCE_OUTCOMES:
        return norm_persist
    if norm_persist in ("failure", "cancelled", "timed_out", "error"):
        return "push_failed"
    if norm_persist == "skipped":
        return "push_skipped"
    if (has_commit or norm_save == "saved_local") and norm_persist in ("", "success"):
        return "saved_and_pushed" if has_commit else "no_changes"
    return "no_changes"


def render_summary_markdown(
    report: dict[str, Any] | None,
    *,
    report_error: str = "",
    persistence: dict[str, Any] | None = None,
    mode: str = "live",
    only: str = "all",
    game: str = "",
    repost: str = "",
    test_suite: str = "all",
    no_ping: str = "0",
    code_sha: str = "",
    state_commit_sha: str = "",
    run_outcome: str = "success",
    persist_outcome: str = "",
) -> str:
    """Render the complete Markdown run summary and persistence footer."""
    has_report = isinstance(report, dict) and bool(report) and not report_error
    safe_report: dict[str, Any] = redact_value(report or {}) if has_report else {}
    safe_persist: dict[str, Any] = redact_value(persistence or {}) if isinstance(persistence, dict) else {}

    runs: list[dict[str, Any]] = (
        list(safe_report.get("runs", []))
        if isinstance(safe_report.get("runs"), list) and safe_report.get("runs")
        else ([safe_report] if safe_report else [])
    )

    eff_mode = str(
        mode if mode and mode != "live" else (safe_report.get("mode") or mode or "live")
    )
    eff_only = str(safe_report.get("only") or only or "all")
    eff_game = str(safe_report.get("game") or game or "all")
    eff_repost = str(safe_report.get("repost") if "repost" in safe_report else repost)
    eff_test = str(test_suite or ("all" if eff_mode == "test" else "n/a"))
    eff_no_ping = str(
        "1"
        if safe_report.get("no_ping") is True
        else ("0" if safe_report.get("no_ping") is False else no_ping)
    )
    eff_code_sha = (
        str(code_sha or safe_report.get("code_sha") or os.environ.get("GAMEXPRESS_CODE_SHA") or "")
        .strip()[:7]
        or "local"
    )
    eff_state_sha = str(
        state_commit_sha or safe_persist.get("state_commit_sha") or ""
    ).strip()[:7]
    py_ver = str(safe_report.get("python_version") or platform.python_version())
    runner_img = str(
        safe_report.get("runner_image")
        or os.environ.get("GAMEXPRESS_RUNNER_IMAGE")
        or platform.platform()
    )
    lock_sha = str(
        safe_report.get("lock_sha256")
        or os.environ.get("GAMEXPRESS_LOCK_SHA256")
        or "n/a"
    )
    if len(lock_sha) > 12:
        lock_sha = lock_sha[:12]

    state_block = safe_report.get("state") if isinstance(safe_report.get("state"), dict) else {}
    load_status = str(state_block.get("load_status") or ("loaded_local" if has_report else "unavailable"))
    save_status = str(
        state_block.get("local_save_outcome")
        or state_block.get("save_status")
        or ("unchanged_local" if has_report else "unavailable")
    )

    eff_persist_outcome = str(persist_outcome or safe_persist.get("persist_outcome") or "")
    commit_outcome = str(safe_persist.get("commit_outcome") or "")
    push_outcome = str(safe_persist.get("push_outcome") or "")
    if not commit_outcome:
        if eff_mode in ("test", "dry_run"):
            commit_outcome = "not-run (test/dry_run)"
        elif eff_persist_outcome == "commit_failed":
            commit_outcome = "failed"
        elif eff_state_sha or eff_persist_outcome in ("saved_and_pushed", "push_failed"):
            commit_outcome = f"committed ({eff_state_sha})" if eff_state_sha else "committed"
        elif eff_persist_outcome == "no_changes":
            commit_outcome = "unchanged"
        else:
            commit_outcome = "not-run"
    if not push_outcome:
        if eff_mode in ("test", "dry_run"):
            push_outcome = "not-run (test/dry_run)"
        elif eff_persist_outcome == "saved_and_pushed":
            push_outcome = f"pushed ({eff_state_sha})" if eff_state_sha else "pushed"
        elif eff_persist_outcome == "push_failed":
            push_outcome = "failed"
        elif eff_persist_outcome == "no_changes":
            push_outcome = "unchanged"
        else:
            push_outcome = "not-run"

    final_persistence = resolve_persistence_outcome(
        mode=eff_mode,
        run_outcome=run_outcome,
        persist_outcome=eff_persist_outcome,
        state_save_status=save_status if has_report else "unchanged_local",
        state_commit_sha=eff_state_sha,
        commit_outcome=commit_outcome,
        push_outcome=push_outcome,
    )

    started_at = safe_report.get("started_at", "unavailable" if not has_report else "n/a")
    finished_at = safe_report.get("finished_at", "unavailable" if not has_report else "n/a")
    setup_dur = float(safe_report.get("setup_duration_s") or os.environ.get("GAMEXPRESS_SETUP_DURATION_S") or 0.0)
    persist_dur = float(safe_persist.get("persist_duration_s") or 0.0)
    total_duration = round(
        sum(float(r.get("duration_s") or 0.0) for r in runs)
        or float(safe_report.get("duration_s") or 0.0),
        2,
    )

    if has_report:
        total_posted = sum(int((r.get("cards") or {}).get("posted", 0)) for r in runs)
        total_patched = sum(int((r.get("cards") or {}).get("patched", 0)) for r in runs)
        total_failed_cards = sum(int((r.get("cards") or {}).get("failed", 0)) for r in runs)
        cards_cell = f"`posted={total_posted}` `patched={total_patched}` `failed={total_failed_cards}`"
        report_status_str = f"`available` (`execution_result={safe_report.get('execution_result', 'success')}`)"
    else:
        reason_tag = redact_text(report_error or "report file missing or unreadable")
        cards_cell = f"`unavailable` ({reason_tag})"
        report_status_str = f"`unavailable` ({reason_tag})"

    lines: list[str] = [
        f"### Game-Express `{eff_code_sha}` — Run Summary",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Mode | `{redact_text(eff_mode)}` |",
        f"| `only` | `{redact_text(eff_only)}` |",
        f"| `game` | `{redact_text(eff_game)}` |",
        f"| `repost` | `{redact_text(eff_repost) or 'none'}` |",
        f"| `test` | `{redact_text(eff_test)}` |",
        f"| `no_ping` | `{redact_text(eff_no_ping)}` |",
        f"| `code_sha` | `{eff_code_sha}` |",
        f"| `state_commit_sha` | `{eff_state_sha or 'none'}` |",
        f"| Python / Runner | `{redact_text(py_ver)}` on `{redact_text(runner_img)}` |",
        f"| Lockfile SHA-256 | `{redact_text(lock_sha)}` |",
        f"| Report status | {report_status_str} |",
        f"| Window / Timing | `start={started_at}` `end={finished_at}` `setup={setup_dur:.1f}s` `run={total_duration}s` `persist={persist_dur:.1f}s` |",
        f"| Cards | {cards_cell} |",
        "",
    ]

    report_bullets: list[str] = []
    warnings: list[str] = []
    errors: list[str] = []
    outcomes: list[dict[str, Any]] = []
    deliveries: list[dict[str, Any]] = []

    for r in runs:
        report_bullets.extend(str(x) for x in (r.get("report_lines") or []))
        warnings.extend(str(x) for x in (r.get("warnings") or []))
        errors.extend(str(x) for x in (r.get("errors") or []))
        outcomes.extend(
            x for x in (r.get("source_outcomes") or []) if isinstance(x, dict)
        )
        deliveries.extend(
            x for x in (r.get("webhook_deliveries") or []) if isinstance(x, dict)
        )

    lines.append("#### Run Activity")
    if not has_report:
        lines.append(f"- ⚠️ Run report unavailable: {redact_text(report_error or 'missing report file')}")
    elif report_bullets:
        for item in report_bullets:
            lines.append(f"- {redact_text(item)}")
    else:
        lines.append("- nothing new (no matching announcements / codes)")
    for w in warnings:
        lines.append(f"- ⚠️ {redact_text(w)}")
    for e in errors:
        lines.append(f"- ❌ {redact_text(e)}")
    lines.append("")

    lines.append("#### Source & Feed Outcomes")
    if outcomes:
        lines.append(
            "| Source | Lane | Game | Transport | Parsed | Usable | Selected | Fallback | Status | Reason |"
        )
        lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
        for o in outcomes[:60]:
            src = redact_text(str(o.get("source") or "?"))
            lane = redact_text(str(o.get("lane") or "—"))
            gm = redact_text(str(o.get("game") or "—"))
            tr = redact_text(str(o.get("transport_status") or "—"))
            parsed = int(o.get("parsed_count") or 0)
            usable = int(o.get("usable_count") or 0)
            selected = int(o.get("selected_count") or 0)
            fb = "yes" if o.get("fallback_used") else "no"
            st = redact_text(str(o.get("status") or "—"))
            rsn = redact_text(str(o.get("reason") or "—"))
            lines.append(
                f"| `{src}` | `{lane}` | `{gm}` | `{tr}` | {parsed} | {usable} | {selected} | `{fb}` | `{st}` | {rsn} |"
            )
    else:
        lines.append(
            "_Source outcomes unavailable (report missing)._"
            if not has_report
            else "_No source outcome records captured for this run._"
        )
    lines.append("")

    lines.append("#### Webhook Deliveries")
    if deliveries:
        lines.append("| Method | Redacted Target | Fingerprint | HTTP Status | Outcome |")
        lines.append("| --- | --- | --- | --- | --- |")
        for d in deliveries[:50]:
            method = redact_text(str(d.get("method") or "POST"))
            target = redact_url(str(d.get("target") or ""))
            fp = redact_text(str(d.get("fingerprint") or "—"))
            status_code = int(d.get("status") or 0)
            ok_str = "ok" if d.get("ok") else f"failed ({redact_text(str(d.get('error') or 'error'))})"
            lines.append(f"| `{method}` | `{target}` | `{fp}` | `{status_code}` | {ok_str} |")
    else:
        lines.append(
            "_Webhook delivery telemetry unavailable (report missing)._"
            if not has_report
            else "_No webhook deliveries in this run._"
        )
    lines.append("")

    lines.extend(
        [
            "#### State & Persistence Footer",
            "",
            "| Stage | Status |",
            "| --- | --- |",
            f"| Monitor step outcome | `{redact_text(run_outcome)}` |",
            f"| State load status | `{redact_text(load_status)}` |",
            f"| Local state save | `{redact_text(save_status)}` |",
            f"| Git commit | `{redact_text(commit_outcome)}` |",
            f"| Remote git push | `{redact_text(push_outcome)}` |",
            f"| Final persistence outcome | **`{final_persistence}`** |",
            f"| Checked-out `code_sha` | `{eff_code_sha}` |",
            f"| Committed `state_commit_sha` | `{eff_state_sha or 'none'}` |",
            "",
        ]
    )

    return redact_text("\n".join(lines)) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", default="", help="Path to gamexpress-run-report.json")
    parser.add_argument("--persistence", default="", help="Optional path to gamexpress-persistence.json")
    parser.add_argument("--output", default="", help="Optional output Markdown path")
    parser.add_argument("--mode", default=os.environ.get("MONITOR_MODE", "live"))
    parser.add_argument("--only", default=os.environ.get("ONLY", "all"))
    parser.add_argument("--game", default=os.environ.get("ONLY_GAMES", ""))
    parser.add_argument("--repost", default=os.environ.get("FORCE_REPOST", ""))
    parser.add_argument("--test-suite", default=os.environ.get("MONITOR_TEST", "all"))
    parser.add_argument("--no-ping", default=os.environ.get("NO_PING", "0"))
    parser.add_argument("--code-sha", default=os.environ.get("GAMEXPRESS_CODE_SHA", ""))
    parser.add_argument("--state-commit-sha", default=os.environ.get("STATE_COMMIT_SHA", ""))
    parser.add_argument("--run-outcome", default=os.environ.get("MONITOR_RUN_OUTCOME", "success"))
    parser.add_argument(
        "--persist-outcome", default=os.environ.get("STATE_PERSIST_OUTCOME", "")
    )
    args = parser.parse_args(argv)

    report_path_str = args.report or os.environ.get("GAMEXPRESS_RUN_REPORT", "")
    report_data: dict[str, Any] | None = None
    report_err = ""
    if report_path_str:
        rp = pathlib.Path(report_path_str)
        if rp.is_file():
            try:
                loaded = json.loads(rp.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    report_data = loaded
                else:
                    report_err = "report JSON root is not an object"
            except (OSError, json.JSONDecodeError) as exc:
                report_err = f"corrupt report JSON ({type(exc).__name__})"
        else:
            report_err = f"missing report file ({rp.name})"
    else:
        report_err = "no report path configured"

    persist_path_str = args.persistence or os.environ.get("GAMEXPRESS_PERSISTENCE_PATH", "")
    persist_data: dict[str, Any] | None = None
    if persist_path_str:
        pp = pathlib.Path(persist_path_str)
        if pp.is_file():
            try:
                loaded_p = json.loads(pp.read_text(encoding="utf-8"))
                if isinstance(loaded_p, dict):
                    persist_data = loaded_p
            except (OSError, json.JSONDecodeError):
                persist_data = None

    md = render_summary_markdown(
        report_data,
        report_error=report_err,
        persistence=persist_data,
        mode=args.mode,
        only=args.only,
        game=args.game,
        repost=args.repost,
        test_suite=args.test_suite,
        no_ping=args.no_ping,
        code_sha=args.code_sha,
        state_commit_sha=args.state_commit_sha,
        run_outcome=args.run_outcome,
        persist_outcome=args.persist_outcome,
    )

    out_path = args.output or os.environ.get("GITHUB_STEP_SUMMARY", "")
    if out_path:
        pathlib.Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "a", encoding="utf-8") as fh:
            fh.write(md)
    else:
        sys.stdout.write(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
