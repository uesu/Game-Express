"""Configuration and documentation contract tests for Game-Express."""

from __future__ import annotations

import ast
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Standard GitHub Actions runner variables read by the runtime that are set by GitHub itself
RUNNER_ENV_ALLOWLIST = {
    "GITHUB_SHA",
    "GITHUB_STEP_SUMMARY",
}


def _extract_env_vars_from_package() -> set[str]:
    found: set[str] = set()
    for path in sorted((ROOT / "gamexpress").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            # os.getenv("FOO") or os.environ.get("FOO")
            if isinstance(node, ast.Call):
                func = node.func
                if (
                    isinstance(func, ast.Attribute)
                    and func.attr in {"getenv", "get"}
                    and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)
                ):
                    key = node.args[0].value
                    if key.isupper() and "_" in key:
                        found.add(key)
            # os.environ["FOO"]
            elif isinstance(node, ast.Subscript):
                val = node.value
                if (
                    isinstance(val, ast.Attribute)
                    and val.attr == "environ"
                    and isinstance(node.slice, ast.Constant)
                    and isinstance(node.slice.value, str)
                ):
                    key = node.slice.value
                    if key.isupper() and "_" in key:
                        found.add(key)
    return found


def test_every_code_env_var_is_documented_in_env_example_and_configuration_doc() -> None:
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
    code_vars = _extract_env_vars_from_package() - RUNNER_ENV_ALLOWLIST
    assert "GAMEXPRESS_CODE_SHA" in code_vars
    assert "GAMEXPRESS_RUN_REPORT" in code_vars

    missing_env_example = sorted(v for v in code_vars if v not in env_example)
    assert not missing_env_example, (
        f"Env vars read in gamexpress/ but missing from .env.example: {missing_env_example}"
    )

    profile = os.environ.get("GAMEXPRESS_CI_PROFILE", "development")
    config_doc_path = ROOT / "docs" / "CONFIGURATION.md"
    if profile == "production" and not config_doc_path.is_file():
        return
    config_doc = config_doc_path.read_text(encoding="utf-8")
    missing_config_doc = sorted(v for v in code_vars if v not in config_doc)
    assert not missing_config_doc, (
        f"Env vars read in gamexpress/ but missing from docs/CONFIGURATION.md: {missing_config_doc}"
    )


def test_maintenance_docs_and_contracts_are_present_and_linked() -> None:
    profile = os.environ.get("GAMEXPRESS_CI_PROFILE", "development")
    docs_dir = ROOT / "docs"
    if profile == "production" and not docs_dir.is_dir():
        return

    docs_index = (docs_dir / "README.md").read_text(encoding="utf-8")
    maint_doc = (docs_dir / "MAINTENANCE.md").read_text(encoding="utf-8")
    py_doc = (docs_dir / "PYTHON_VERSION.md").read_text(encoding="utf-8")
    dep_doc = (docs_dir / "DEPENDABOT.md").read_text(encoding="utf-8")

    assert "MAINTENANCE.md" in docs_index
    for token in (
        ".python-version",
        "requirements.in",
        "requirements-dev.in",
        "maintenance-ci",
        "maintenance_merge.yml",
        "render_run_summary.py",
        "GAMEXPRESS_CODE_SHA",
        "GAMEXPRESS_RUN_REPORT",
        "AUTO_MERGE_PYTHON_BUMP",
        "BUMP_PAT",
    ):
        assert token in maint_doc, f"docs/MAINTENANCE.md must document {token}"

    assert "BUMP_PAT" in py_doc
    assert "maintenance_merge.yml" in dep_doc

    zizmor_cfg = (ROOT / ".github" / "zizmor.yml").read_text(encoding="utf-8")
    assert "unpinned-uses" not in zizmor_cfg, ".github/zizmor.yml must not ignore unpinned-uses"
    assert "bot-conditions:" in zizmor_cfg and "dangerous-triggers:" in zizmor_cfg

    setup = (ROOT / "docs" / "PROD-REPO-SETUP.md").read_text(encoding="utf-8")
    new_session = setup.split("### A new session on the prod repo", 1)[1].split("Then come back", 1)[0]
    assert ".python-version" in new_session
    assert ".github/scripts/render_run_summary.py" in new_session
    assert "expect 36" not in setup, "copy acceptance must use required paths, not stale file counts"


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
