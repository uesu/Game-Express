#!/usr/bin/env python3
"""Compatibility adapter around `.github/scripts/maintenance.py`."""

from __future__ import annotations

import argparse
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
RELEASE_DATES_URL = _m.RELEASE_DATES_URL
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


def fetch_release_dates() -> dict[str, str]:
    return _m.fetch_release_dates(RELEASE_DATES_URL)


def current_pin(root: pathlib.Path = REPO_ROOT) -> str:
    return _m.read_python_pin(root, _m.load_policy(root))


def current_version(root: pathlib.Path = REPO_ROOT) -> str:
    return current_pin(root)


def highest_stable_minor(
    manifest: list[dict[str, Any]],
    current: str | None = None,
    *,
    release_dates: dict[str, str] | list[dict[str, Any]] | None = None,
) -> tuple[str, str]:
    pin = current or current_pin()
    sel = _m.select_target_python(
        manifest, pin, _m.load_policy(REPO_ROOT), release_dates=release_dates
    )
    return sel.selected_minor, sel.selected_version


def bump_workflow_files(
    old: str, new: str, *, root: pathlib.Path = REPO_ROOT
) -> list[pathlib.Path]:
    del old
    rels = _m.write_python_pin(root, new, _m.load_policy(root))
    return [root / r for r in rels]


def rewrite_all(new_version: str, *, root: pathlib.Path = REPO_ROOT) -> list[str]:
    changed, _ruff = _m.apply_python_version(new_version, repo_root=root, policy=_m.load_policy(root))
    return changed


def ruff_understands(target: str) -> bool:
    return _m.ruff_understands(target)


def bump_ruff_toml(new_minor: str, *, root: pathlib.Path = REPO_ROOT) -> bool:
    res = _m.update_ruff_toml(root, new_minor, _m.load_policy(root))
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
        status="proposed" if old != full else "up-to-date",
        update_kind="patch" if old != full else "none",
        review_required=False,
        auto_merge_eligible=old != full,
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Apply selected runtime update")
    parser.add_argument("--dry-run", action="store_true", help="Select only; do not write files")
    parser.add_argument("--override", default="", help="Optional manual X.Y.Z override version")
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    return _m.run_bump(
        REPO_ROOT,
        manifest=fetch_manifest(),
        policy=_m.load_policy(REPO_ROOT),
        release_dates=fetch_release_dates(),
        override_version=args.override or None,
        dry_run=bool(args.dry_run and not args.apply),
    )


if __name__ == "__main__":
    raise SystemExit(main())
