#!/usr/bin/env python3
"""Unified validation command registry and `maintenance-ci` gate for Game-Express."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import pathlib
import shutil
import subprocess
import sys
from typing import Any

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def _load_maintenance_common():
    path = pathlib.Path(__file__).resolve().with_name("maintenance_common.py")
    if not path.is_file():
        path = REPO_ROOT / ".github" / "scripts" / "maintenance_common.py"
    spec = importlib.util.spec_from_file_location("_gamexpress_maintenance_common", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_maintenance():
    path = pathlib.Path(__file__).resolve().with_name("maintenance.py")
    spec = importlib.util.spec_from_file_location("_gamexpress_maintenance", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def detect_profile(repo_root: pathlib.Path = REPO_ROOT, requested: str = "auto") -> str:
    """Resolve `development` or `production` validation profile."""
    req = (requested or "auto").strip().lower()
    if req in ("development", "production"):
        return req
    has_docs = (repo_root / "docs").is_dir() and (repo_root / "README.md").is_file()
    return "development" if has_docs else "production"


def _run_cmd(
    cmd: list[str],
    *,
    cwd: pathlib.Path = REPO_ROOT,
    env: dict[str, str] | None = None,
) -> int:
    print(f"+ {' '.join(cmd)}", flush=True)
    res = subprocess.run(cmd, cwd=str(cwd), env=env, check=False)
    return res.returncode


def run_compile(repo_root: pathlib.Path = REPO_ROOT) -> int:
    targets = [
        t
        for t in ("gamexpress", "tests", ".github/scripts")
        if (repo_root / t).exists()
    ]
    return _run_cmd([sys.executable, "-m", "compileall", "-q", *targets], cwd=repo_root)


def run_workflow_check(
    repo_root: pathlib.Path = REPO_ROOT,
    profile: str = "development",
) -> int:
    maint = _load_maintenance()
    policy = maint.load_policy(repo_root)
    errors = maint.validate_workflow_python_pins(
        repo_root,
        policy,
        require_all_workflows=(profile == "development"),
    )
    if errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1
    return 0


def run_validate_cli(repo_root: pathlib.Path = REPO_ROOT) -> int:
    if not (repo_root / "gamexpress").is_dir():
        return 0
    return _run_cmd([sys.executable, "-m", "gamexpress", "validate"], cwd=repo_root)


def run_offline_tests(
    repo_root: pathlib.Path = REPO_ROOT,
    profile: str = "development",
) -> int:
    maint = _load_maintenance()
    policy = maint.load_policy(repo_root)
    registered = list(policy.get("ci", {}).get("registered_tests") or [])
    discovered = sorted(f"tests/{p.name}" for p in (repo_root / "tests").glob("test_*.py"))
    if not discovered:
        print("ERROR: no test files found under tests/", file=sys.stderr)
        return 1

    if registered:
        missing_from_registry = sorted(set(discovered) - set(registered))
        if missing_from_registry:
            print(
                f"ERROR: test file(s) under tests/ are not registered in .github/maintenance.json: "
                f"{', '.join(missing_from_registry)}",
                file=sys.stderr,
            )
            return 1
        missing_on_disk = [r for r in registered if not (repo_root / r).is_file()]
        if missing_on_disk and profile == "development":
            print(
                f"ERROR: registered test file(s) missing on disk: {', '.join(missing_on_disk)}",
                file=sys.stderr,
            )
            return 1
        ordered_tests = [r for r in registered if (repo_root / r).is_file()]
    else:
        ordered_tests = discovered

    env = os.environ.copy()
    env["GAMEXPRESS_CI_PROFILE"] = profile
    for rel_test in ordered_tests:
        rc = _run_cmd([sys.executable, rel_test], cwd=repo_root, env=env)
        if rc != 0:
            return rc
    return 0


def run_verify(
    repo_root: pathlib.Path = REPO_ROOT,
    profile: str = "development",
) -> int:
    rc = run_compile(repo_root)
    if rc != 0:
        return rc
    rc = run_workflow_check(repo_root, profile=profile)
    if rc != 0:
        return rc
    rc = run_validate_cli(repo_root)
    if rc != 0:
        return rc
    return run_offline_tests(repo_root, profile=profile)


def _compiler_pin_failures(repo_root: pathlib.Path, profile: dict[str, Any] | None = None) -> list[str]:
    """Require the pinned compiler to appear in requirements-dev.txt and match maintenance_common pins."""
    mc = _load_maintenance_common()
    pol = profile if isinstance(profile, dict) else {}
    pinned_pip, pinned_tools = mc.compiler_pins(pol)
    problems: list[str] = []
    if pinned_pip != mc.PINNED_PIP or pinned_tools != mc.PINNED_PIP_TOOLS:
        problems.append(
            f"profile compiler pip=={pinned_pip} pip-tools=={pinned_tools} "
            f"does not match helper pins pip=={mc.PINNED_PIP} pip-tools=={mc.PINNED_PIP_TOOLS}"
        )
    dev = repo_root / "requirements-dev.txt"
    if not dev.is_file():
        problems.append("missing requirements-dev.txt (compiler pins live there)")
        return problems
    text = dev.read_text(encoding="utf-8")
    if f"pip=={pinned_pip}" not in text:
        problems.append(f"requirements-dev.txt must contain pip=={pinned_pip}")
    if f"pip-tools=={pinned_tools}" not in text:
        problems.append(f"requirements-dev.txt must contain pip-tools=={pinned_tools}")
    return problems


def run_lock_check(
    repo_root: pathlib.Path = REPO_ROOT,
    *,
    require_exact_python: bool = False,
    expected_python: str | None = None,
) -> int:
    maint = _load_maintenance()
    policy = maint.load_policy(repo_root)
    pin_problems = _compiler_pin_failures(repo_root, policy)
    if pin_problems:
        for err in pin_problems:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1
    ok, errors = maint.verify_lockfiles(
        repo_root,
        policy,
        recompile=True,
        require_exact_python=require_exact_python,
        expected_python_override=expected_python,
    )
    if not ok:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1
    print("OK: lockfiles verified.")
    return 0


def run_ruff(repo_root: pathlib.Path = REPO_ROOT) -> int:
    ruff_bin = shutil.which("ruff")
    if ruff_bin:
        cmd = [ruff_bin, "check", "."]
    else:
        # Fail closed if python -m ruff is not installed either
        cmd = [sys.executable, "-m", "ruff", "check", "."]
    return _run_cmd(cmd, cwd=repo_root)


def _parse_external_security_results(
    results_json: str = "",
    result_items: list[str] | None = None,
) -> dict[str, str]:
    parsed: dict[str, str] = {}
    if results_json and results_json.strip():
        raw_obj = json.loads(results_json)
        if isinstance(raw_obj, dict):
            for k, v in raw_obj.items():
                parsed[str(k).strip().lower()] = str(v).strip().lower()
    for item in result_items or []:
        if "=" in item:
            k, v = item.split("=", 1)
            parsed[k.strip().lower()] = v.strip().lower()
    return parsed


def run_security_audit(
    repo_root: pathlib.Path = REPO_ROOT,
    *,
    require_tools: bool = True,
    require_actionlint: bool = True,
    external_results: dict[str, str] | None = None,
) -> int:
    norm_external: dict[str, str] = {
        str(k).strip().lower(): str(v).strip().lower()
        for k, v in (external_results or {}).items()
    }
    tool_specs: list[tuple[str, bool, list[str]]] = [
        ("actionlint", require_actionlint, []),
        ("zizmor", require_tools, [".github/workflows"]),
        (
            "pip-audit",
            require_tools,
            ["-r", "requirements.txt", "--require-hashes", "--strict", "--desc"],
        ),
    ]
    missing_or_failed = False
    for tool_name, is_required, args in tool_specs:
        has_ext = tool_name in norm_external
        ext_res = norm_external.get(tool_name, "")
        if has_ext and ext_res != "success":
            print(
                f"ERROR: external Action check '{tool_name}' did not succeed (result={ext_res!r}).",
                file=sys.stderr,
            )
            missing_or_failed = True
            continue

        tool_bin = shutil.which(tool_name)
        if tool_bin:
            rc = _run_cmd([tool_bin, *args], cwd=repo_root)
            if rc != 0:
                return rc
            if has_ext:
                print(
                    f"EXTERNAL ACTION RESULT: {tool_name}={ext_res} (and verified by local binary)",
                    flush=True,
                )
        elif has_ext and ext_res == "success":
            print(
                f"EXTERNAL ACTION RESULT: {tool_name}=success (verified by workflow Action step)",
                flush=True,
            )
        elif is_required:
            label = "workflow linter" if tool_name == "actionlint" else "security tool"
            print(
                f"ERROR: required {label} '{tool_name}' is not installed.",
                file=sys.stderr,
            )
            missing_or_failed = True
        else:
            print(
                f"SKIPPED (optional local mode): '{tool_name}' is not installed.",
                flush=True,
            )

    return 1 if missing_or_failed else 0


def run_all_registry(
    repo_root: pathlib.Path = REPO_ROOT,
    *,
    profile: str = "development",
    phase: str = "ci",
    expected_python: str | None = None,
    require_exact_python: bool = False,
    with_security: bool = False,
    require_security_tools: bool = True,
    require_actionlint: bool = True,
    external_security_results: dict[str, str] | None = None,
) -> int:
    """Execute the complete unified validation registry across `ci`, `pre-rewrite`, or `post-rewrite` phases."""
    maint = _load_maintenance()
    norm_phase = (phase or "ci").strip().lower()
    if expected_python:
        try:
            maint.assert_target_interpreter(
                repo_root,
                expected_version=expected_python,
                allow_same_minor=False,
            )
        except RuntimeError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
    if norm_phase == "post-rewrite" or (norm_phase == "ci" and require_exact_python):
        try:
            maint.assert_target_interpreter(
                repo_root,
                expected_version=None,
                allow_same_minor=False,
            )
        except RuntimeError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1

    enforce_exact_lock = bool(require_exact_python and norm_phase != "pre-rewrite")
    for step_fn in (
        lambda: run_verify(repo_root, profile=profile),
        lambda: run_lock_check(
            repo_root,
            require_exact_python=enforce_exact_lock,
            expected_python=expected_python,
        ),
        lambda: run_ruff(repo_root),
    ):
        rc = step_fn()
        if rc != 0:
            return rc
    if with_security:
        return run_security_audit(
            repo_root,
            require_tools=require_security_tools,
            require_actionlint=require_actionlint,
            external_results=external_security_results,
        )
    return 0


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
    # Normalize alias "test" -> "verify" if caller used "--result test=success"
    normalized_blocking = dict(blocking_results)
    if "test" in normalized_blocking and "verify" not in normalized_blocking:
        normalized_blocking["verify"] = normalized_blocking.pop("test")
    if "audit" in normalized_blocking and "actionlint" not in normalized_blocking:
        normalized_blocking["actionlint"] = normalized_blocking.pop("audit")

    advisory = advisory_results or {}

    failures: list[str] = []
    rows: list[str] = [
        "### `maintenance-ci` Aggregate Gate",
        "",
        "| Check | Tier | Result |",
        "| --- | --- | --- |",
    ]
    for check in expected_blocking:
        res = str(normalized_blocking.get(check, "missing")).lower()
        rows.append(f"| `{check}` | blocking | `{res}` |")
        if res != "success":
            failures.append(f"Blocking check {check!r} did not succeed (result={res!r}).")

    for check, raw in sorted(normalized_blocking.items()):
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
    parser.add_argument(
        "--profile",
        choices=("auto", "development", "production"),
        default=os.environ.get("GAMEXPRESS_CI_PROFILE", "auto"),
        help="Validation profile (development requires docs; production allows docless clone)",
    )
    sub = parser.add_subparsers(dest="cmd")

    for name, help_text in (
        ("compile", "Run syntax/bytecode compilation check"),
        ("workflow-check", "Validate workflow YAML, SHA pins, setup-python, and expression rules"),
        ("tests", "Run all registered offline test suites"),
        ("verify", "Run compile, workflow pin check, config validate, and all offline test suites"),
    ):
        p = sub.add_parser(name, help=help_text)
        p.add_argument(
            "--profile",
            choices=("auto", "development", "production"),
            default=None,
            help="Override validation profile",
        )

    lc_p = sub.add_parser("lock-check", help="Verify runtime and dev lockfiles")
    lc_p.add_argument("--require-exact-python", action="store_true")
    lc_p.add_argument("--expected-python", default="", help="Expected X.Y.Z running interpreter")

    sub.add_parser("ruff", help="Run Ruff lint check")

    sec_p = sub.add_parser("security-audit", help="Run actionlint, zizmor, and pip-audit checks (fails closed by default)")
    sec_p.add_argument("--require-tools", action="store_true", default=False)
    sec_p.add_argument("--require-actionlint", action="store_true", default=False)
    sec_p.add_argument(
        "--allow-missing-security-tools",
        action="store_true",
        help="Explicit optional local mode allowing missing security tools to be logged as skipped",
    )
    sec_p.add_argument("--external-security-results-json", default="")
    sec_p.add_argument("--external-security-result", action="append", default=[])

    all_p = sub.add_parser("run-all", help="Run verify, lock-check, ruff, and optional security checks from one registry")
    all_p.add_argument(
        "--profile",
        choices=("auto", "development", "production"),
        default=None,
    )
    all_p.add_argument(
        "--phase",
        choices=("ci", "pre-rewrite", "post-rewrite"),
        default="ci",
        help="Validation phase (`pre-rewrite` validates candidate interpreter before .python-version is updated)",
    )
    all_p.add_argument("--expected-python", default="", help="Expected X.Y.Z candidate interpreter")
    all_p.add_argument("--require-exact-python", action="store_true")
    all_p.add_argument("--with-security", action="store_true")
    all_p.add_argument("--require-security-tools", action="store_true", default=False)
    all_p.add_argument("--require-actionlint", action="store_true", default=False)
    all_p.add_argument(
        "--allow-missing-security-tools",
        action="store_true",
        help="Explicit optional local mode allowing missing security tools to be logged as skipped",
    )
    all_p.add_argument("--external-security-results-json", default="")
    all_p.add_argument("--external-security-result", action="append", default=[])

    gate_p = sub.add_parser("gate", help="Evaluate final `maintenance-ci` aggregate gate")
    gate_p.add_argument(
        "--results-json",
        default="",
        help="JSON object mapping blocking job IDs to their `needs.<job>.result` string",
    )
    gate_p.add_argument(
        "--advisory-json",
        default="{}",
        help="JSON object mapping advisory job IDs to their `needs.<job>.result` string",
    )
    gate_p.add_argument(
        "--result",
        action="append",
        default=[],
        help="Individual blocking check result in KEY=VALUE form",
    )

    args = parser.parse_args(argv)
    cmd = args.cmd or "verify"
    sub_profile = getattr(args, "profile", None)
    profile = detect_profile(REPO_ROOT, sub_profile or parser.get_default("profile"))

    if cmd == "compile":
        return run_compile(REPO_ROOT)
    if cmd == "workflow-check":
        return run_workflow_check(REPO_ROOT, profile=profile)
    if cmd == "tests":
        return run_offline_tests(REPO_ROOT, profile=profile)
    if cmd == "verify":
        return run_verify(REPO_ROOT, profile=profile)
    if cmd == "lock-check":
        return run_lock_check(
            REPO_ROOT,
            require_exact_python=bool(getattr(args, "require_exact_python", False)),
            expected_python=getattr(args, "expected_python", "") or None,
        )
    if cmd == "ruff":
        return run_ruff(REPO_ROOT)
    if cmd == "security-audit":
        allow_missing = bool(getattr(args, "allow_missing_security_tools", False))
        req_tools = (not allow_missing) or bool(getattr(args, "require_tools", False))
        req_actionlint = (not allow_missing) or bool(getattr(args, "require_actionlint", False))
        ext_res = _parse_external_security_results(
            getattr(args, "external_security_results_json", "") or "",
            list(getattr(args, "external_security_result", []) or []),
        )
        return run_security_audit(
            REPO_ROOT,
            require_tools=req_tools,
            require_actionlint=req_actionlint,
            external_results=ext_res,
        )
    if cmd == "run-all":
        allow_missing = bool(getattr(args, "allow_missing_security_tools", False))
        req_sec_tools = (not allow_missing) or bool(getattr(args, "require_security_tools", False))
        req_actionlint = (not allow_missing) or bool(getattr(args, "require_actionlint", False))
        ext_res = _parse_external_security_results(
            getattr(args, "external_security_results_json", "") or "",
            list(getattr(args, "external_security_result", []) or []),
        )
        return run_all_registry(
            REPO_ROOT,
            profile=profile,
            phase=str(getattr(args, "phase", "ci") or "ci"),
            expected_python=getattr(args, "expected_python", "") or None,
            require_exact_python=bool(getattr(args, "require_exact_python", False)),
            with_security=bool(getattr(args, "with_security", False)),
            require_security_tools=req_sec_tools,
            require_actionlint=req_actionlint,
            external_security_results=ext_res,
        )
    if cmd == "gate":
        blocking: dict[str, str] = {}
        if args.results_json:
            blocking.update(json.loads(args.results_json))
        for item in args.result or []:
            if "=" in item:
                k, v = item.split("=", 1)
                blocking[k.strip()] = v.strip()
        advisory = json.loads(args.advisory_json or "{}")
        req_list = (
            list(blocking.keys())
            if args.result and not args.results_json
            else None
        )
        ok, failures, summary_md = evaluate_final_gate(
            blocking, advisory, required_blocking=req_list
        )
        sys.stdout.write(summary_md)
        step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if step_summary:
            with open(step_summary, "a", encoding="utf-8") as fh:
                fh.write(summary_md)
        if not ok:
            for f in failures:
                print(f"ERROR: {f}", file=sys.stderr)
            return 1
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
