#!/usr/bin/env python3
"""Command adapter for Game-Express CI jobs and the final `maintenance-ci` gate."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import pathlib
import shutil
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def _load_maintenance():
    path = pathlib.Path(__file__).resolve().with_name("maintenance.py")
    spec = importlib.util.spec_from_file_location("_gamexpress_maintenance", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _run_cmd(cmd: list[str]) -> int:
    print(f"+ {' '.join(cmd)}", flush=True)
    res = subprocess.run(cmd, cwd=str(REPO_ROOT), check=False)
    return res.returncode


def run_compile() -> int:
    return _run_cmd(
        [sys.executable, "-m", "compileall", "-q", "gamexpress", "tests", ".github/scripts"]
    )


def run_offline_tests() -> int:
    test_files = sorted((REPO_ROOT / "tests").glob("test_*.py"))
    if not test_files:
        print("ERROR: no test files found under tests/", file=sys.stderr)
        return 1
    for tf in test_files:
        rc = _run_cmd([sys.executable, f"tests/{tf.name}"])
        if rc != 0:
            return rc
    return 0


def run_verify() -> int:
    rc = run_compile()
    if rc != 0:
        return rc
    maint = _load_maintenance()
    errors = maint.validate_workflow_python_pins(REPO_ROOT, maint.load_policy(REPO_ROOT))
    if errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1
    return run_offline_tests()


def run_lock_check() -> int:
    maint = _load_maintenance()
    ok, errors = maint.verify_lockfiles(REPO_ROOT, maint.load_policy(REPO_ROOT), recompile=True)
    if not ok:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1
    print("OK: lockfiles verified.")
    return 0


def run_ruff() -> int:
    ruff_bin = shutil.which("ruff")
    cmd = [ruff_bin, "check", "."] if ruff_bin else [sys.executable, "-m", "ruff", "check", "."]
    return _run_cmd(cmd)


def evaluate_final_gate(
    blocking_results: dict[str, str],
    advisory_results: dict[str, str] | None = None,
    required_blocking: list[str] | None = None,
) -> tuple[bool, list[str], str]:
    """Evaluate `maintenance-ci` gate results and render a Markdown summary."""
    maint = _load_maintenance()
    pol = maint.load_policy(REPO_ROOT).get("ci", {})
    expected_blocking = required_blocking or list(
        pol.get("blocking_checks", ["verify", "lock-check", "ruff", "actionlint", "zizmor"])
    )
    advisory = advisory_results or {}

    failures: list[str] = []
    rows: list[str] = [
        "### `maintenance-ci` Aggregate Gate",
        "",
        "| Check | Tier | Result |",
        "| --- | --- | --- |",
    ]
    for check in expected_blocking:
        res = str(blocking_results.get(check, "missing")).lower()
        rows.append(f"| `{check}` | blocking | `{res}` |")
        if res != "success":
            failures.append(f"Blocking check {check!r} did not succeed (result={res!r}).")

    for check, raw in sorted(blocking_results.items()):
        if check not in expected_blocking:
            res = str(raw).lower()
            rows.append(f"| `{check}` | blocking | `{res}` |")
            if res != "success":
                failures.append(f"Blocking check {check!r} did not succeed (result={res!r}).")

    for check, raw in sorted(advisory.items()):
        res = str(raw).lower()
        rows.append(f"| `{check}` | advisory | `{res}` |")

    ok = len(failures) == 0
    rows.append("")
    rows.append(
        "**Gate status:** `PASS`"
        if ok
        else f"**Gate status:** `FAIL` ({'; '.join(failures)})"
    )
    return ok, failures, "\n".join(rows) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("compile", help="Run syntax/bytecode compilation check")
    sub.add_parser("tests", help="Run all offline test suites")
    sub.add_parser("verify", help="Run compile, workflow pin check, and all offline test suites")
    sub.add_parser("lock-check", help="Verify runtime and dev lockfiles")
    sub.add_parser("ruff", help="Run Ruff lint check")

    gate_p = sub.add_parser("gate", help="Evaluate final `maintenance-ci` aggregate gate")
    gate_p.add_argument(
        "--results-json",
        required=True,
        help="JSON object mapping blocking job IDs to their `needs.<job>.result` string",
    )
    gate_p.add_argument(
        "--advisory-json",
        default="{}",
        help="JSON object mapping advisory job IDs to their `needs.<job>.result` string",
    )

    args = parser.parse_args(argv)
    cmd = args.cmd or "verify"

    if cmd == "compile":
        return run_compile()
    if cmd == "tests":
        return run_offline_tests()
    if cmd == "verify":
        return run_verify()
    if cmd == "lock-check":
        return run_lock_check()
    if cmd == "ruff":
        return run_ruff()
    if cmd == "gate":
        blocking = json.loads(args.results_json)
        advisory = json.loads(args.advisory_json or "{}")
        ok, failures, summary_md = evaluate_final_gate(blocking, advisory)
        print(summary_md)
        summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary_path:
            with open(summary_path, "a", encoding="utf-8") as fh:
                fh.write(summary_md)
        if not ok:
            for f in failures:
                print(f"ERROR: {f}", file=sys.stderr)
            return 1
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
