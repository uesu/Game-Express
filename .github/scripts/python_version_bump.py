#!/usr/bin/env python3
"""Compatibility adapter around `.github/scripts/maintenance.py`."""

from __future__ import annotations

import importlib.util
import pathlib
import sys
from typing import Any

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def _load_maintenance_module():
    local_candidate = pathlib.Path(__file__).resolve().with_name("maintenance.py")
    if not local_candidate.is_file():
        for base in sys.path:
            alt = pathlib.Path(base) / ".github" / "scripts" / "maintenance.py"
            if alt.is_file():
                local_candidate = alt
                break
    spec = importlib.util.spec_from_file_location("_gamexpress_maintenance", local_candidate)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load maintenance module from {local_candidate}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


_m = _load_maintenance_module()

MANIFEST_URL = _m.MANIFEST_URL
PIN_RE = _m.PIN_RE
RUFF_TARGET_RE = _m.RUFF_TARGET_RE

PYTHON_VERSION_FILE = REPO_ROOT / ".python-version"
WORKFLOW_FILES = [
    REPO_ROOT / ".github" / "workflows" / "ci.yml",
    REPO_ROOT / ".github" / "workflows" / "monitor.yml",
    REPO_ROOT / ".github" / "workflows" / "python_version_bump.yml",
]
RUFF_TOML = REPO_ROOT / "ruff.toml"
ALLOWED_WRITES: list[pathlib.Path] = [PYTHON_VERSION_FILE, *WORKFLOW_FILES, RUFF_TOML]


def _present(paths: list[pathlib.Path]) -> list[pathlib.Path]:
    return [p for p in paths if p.is_file()]


def fetch_manifest() -> list[dict[str, Any]]:
    return _m.fetch_manifest(MANIFEST_URL)


def current_pin() -> str:
    return _m.read_python_pin(REPO_ROOT, _m.load_policy(REPO_ROOT))


def highest_stable_minor(
    manifest: list[dict[str, Any]],
    current: str | None = None,
) -> tuple[str, str]:
    pin = current or current_pin()
    sel = _m.select_target_python(manifest, pin, _m.load_policy(REPO_ROOT))
    return sel.selected_minor, sel.selected_version


def bump_workflow_files(old: str, new: str) -> list[pathlib.Path]:
    del old
    rels = _m.write_python_pin(REPO_ROOT, new, _m.load_policy(REPO_ROOT))
    return [REPO_ROOT / r for r in rels]


def ruff_understands(target: str) -> bool:
    return _m.ruff_understands(target)


def bump_ruff_toml(new_minor: str) -> bool:
    res = _m.update_ruff_toml(REPO_ROOT, new_minor, _m.load_policy(REPO_ROOT))
    return res.changed


def write_body(
    old: str,
    new: str,
    full: str,
    ruff_bumped: bool,
    touched: list[pathlib.Path],
) -> pathlib.Path:
    del new
    pol = _m.load_policy(REPO_ROOT)
    sel = _m.SelectionResult(
        current_version=old,
        selected_version=full,
        selected_minor=".".join(full.split(".")[:2]),
        changed=old != full,
        highest_upstream_version=full,
        clamped_by_policy=False,
        reason=f"Selected stable release {full}.",
    )
    target, clamped, reason = _m.resolve_ruff_target(sel.selected_minor, pol)
    ruff_res = _m.RuffTargetResult(
        target_version=target,
        clamped=clamped,
        changed=ruff_bumped,
        reason=reason,
    )
    rel_paths = [str(p.relative_to(REPO_ROOT)) for p in touched]
    path = pathlib.Path(_m.os.environ.get("PR_BODY_PATH", "/tmp/python-bump-body.md"))
    path.write_text(_m.render_bump_pr_body(sel, ruff_res, rel_paths, pol), encoding="utf-8")
    return path


def _out(values: dict[str, str]) -> None:
    _m.write_github_outputs(values)


def main(argv: list[str] | None = None) -> int:
    del argv
    return _m.run_bump(REPO_ROOT, manifest=fetch_manifest(), policy=_m.load_policy(REPO_ROOT))


if __name__ == "__main__":
    raise SystemExit(main())
