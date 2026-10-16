#!/usr/bin/env python3
"""Unified maintenance policy, Python pin selection, lock verification, and auto-merge gate."""

from __future__ import annotations

import argparse
import datetime
import fnmatch
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import pathlib
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Any

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def _load_maintenance_common():
    local_candidate = pathlib.Path(__file__).resolve().with_name("maintenance_common.py")
    if not local_candidate.is_file():
        alt = REPO_ROOT / ".github" / "scripts" / "maintenance_common.py"
        if alt.is_file():
            local_candidate = alt
        else:
            for base in sys.path:
                cand = pathlib.Path(base) / ".github" / "scripts" / "maintenance_common.py"
                if cand.is_file():
                    local_candidate = cand
                    break
    spec = importlib.util.spec_from_file_location("_gamexpress_maintenance_common", local_candidate)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load maintenance_common from {local_candidate}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


maintenance_common = _load_maintenance_common()
POLICY_PATH = REPO_ROOT / ".github" / "maintenance.json"
MANIFEST_URL = (
    "https://raw.githubusercontent.com/actions/python-versions/main/versions-manifest.json"
)
RELEASE_DATES_URL = "https://endoflife.date/api/v1/products/python/"
RELEASE_DATES_FALLBACK_URL = "https://endoflife.date/api/python.json"

EXACT_VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
MINOR_VERSION_RE = re.compile(r"^(\d+)\.(\d+)$")
PEP440_SIMPLE_RE = re.compile(
    r"^v?(\d+)\.(\d+)(?:\.(\d+))?(?:\.(\d+))?([a-zA-Z0-9._+-]*)$"
)
PIN_RE = re.compile(r'^(\s*python-version:\s*["\'])(\d+\.\d+(?:\.\d+)?)(["\'].*)$', re.MULTILINE)
PIN_FILE_RE = re.compile(
    r"^\s*python-version-file:\s*['\"]?\.python-version['\"]?\s*$", re.MULTILINE
)
CHECK_LATEST_FALSE_RE = re.compile(r"^\s*check-latest:\s*false\s*$", re.MULTILINE)
RUFF_TARGET_RE = re.compile(r'^(\s*target-version\s*=\s*")py(\d+)(".*)$', re.MULTILINE)
USES_LINE_RE = re.compile(
    r"^\s*(?:-\s+)?uses:\s*([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)?)@([0-9a-f]{40})"
    r"\s+#\s*v?(\d+(?:\.\d+){0,2})\b"
)
DEP_BUMP_TITLE_RE = re.compile(
    r"\bbump\s+([A-Za-z0-9_./-]+)\s+from\s+v?([^\s]+)\s+to\s+v?([^\s]+)",
    re.IGNORECASE,
)
PY_BUMP_TITLE_RE = re.compile(
    r"^chore\(python\):\s*bump\s+(?:pinned\s+)?python\s+(?:from\s+(\d+\.\d+\.\d+)\s+)?to\s+(\d+\.\d+\.\d+)\b",
    re.IGNORECASE,
)
REQ_PIN_LINE_RE = re.compile(r"^([A-Za-z0-9_.-]+)==([A-Za-z0-9_.+-]+)$")
IN_REQ_LINE_RE = re.compile(r"^([A-Za-z0-9_.-]+)\s*(==|>=)\s*([A-Za-z0-9_.+-]+)$")
HASH_LINE_RE = re.compile(r"^--hash=sha256:([0-9a-f]{64})$")
ADVISORY_ID_RE = re.compile(
    r"\b(?:GHSA-[A-Za-z0-9]{4}-[A-Za-z0-9]{4}-[A-Za-z0-9]{4}|PYSEC-\d{4}-\d+|CVE-\d{4}-\d{4,})\b"
)
VULN_COUNT_RE = re.compile(r"found\s+(\d+)\s+known\s+vulnerabilit", re.IGNORECASE)

DEFAULT_POLICY: dict[str, Any] = {
    "schema_version": 2,
    "project": "Game-Express",
    "python": {
        "version_file": ".python-version",
        "ruff_config": "ruff.toml",
        "manifest_url": MANIFEST_URL,
        "release_dates_url": RELEASE_DATES_URL,
        "release_dates_fallback_url": RELEASE_DATES_FALLBACK_URL,
        "supported_major": 3,
        "min_minor": 11,
        "max_validated_minor": 14,
        "allow_minor_upgrades": False,
        "max_minor_jump": 1,
        "minor_soak_days": 30,
        "runner_os": "linux",
        "runner_arch": "x64",
        "runner_platform_version": "24.04",
        "known_ruff_targets": ["py311", "py312", "py313", "py314"],
        "workflow_files": [
            ".github/workflows/ci.yml",
            ".github/workflows/monitor.yml",
            ".github/workflows/python_version_bump.yml",
        ],
        "allowed_bump_files": [
            ".python-version",
            "ruff.toml",
            "requirements.txt",
            "requirements-dev.txt",
        ],
        "doc_files": [
            "README.md",
            "AGENTS.md",
            "docs/MAINTENANCE.md",
            "docs/PYTHON_VERSION.md",
            "docs/CONFIGURATION.md",
            "docs/DEPENDABOT.md",
            "docs/PROD-REPO-SETUP.md",
            "docs/ROLLOUT.md",
            "docs/SCHEDULER.md",
            "docs/SECURITY.md",
            "docs/TESTING.md",
            "docs/TROUBLESHOOTING.md",
            "docs/changelog/CHANGELOG.md",
        ],
    },
    "locks": {
        "compiler": {"pip": "26.1.1", "pip_tools": "7.5.3"},
        "targets": [
            {
                "name": "runtime",
                "input_file": "requirements.in",
                "output_file": "requirements.txt",
                "compile_command": (
                    "python -m piptools compile --generate-hashes --allow-unsafe "
                    "--resolver=backtracking --strip-extras "
                    "--output-file=requirements.txt requirements.in"
                ),
            },
            {
                "name": "dev",
                "input_file": "requirements-dev.in",
                "output_file": "requirements-dev.txt",
                "compile_command": (
                    "python -m piptools compile --generate-hashes --allow-unsafe "
                    "--resolver=backtracking --strip-extras "
                    "--output-file=requirements-dev.txt requirements-dev.in"
                ),
            },
        ],
    },
    "ci": {
        "workflow_name": "CI",
        "workflow_path": ".github/workflows/ci.yml",
        "final_gate_name": "maintenance-ci",
        "blocking_checks": ["verify", "lock-check", "ruff", "actionlint", "zizmor"],
        "blocking_check_run_names": [
            "Verify (syntax, workflow contract & offline tests)",
            "Dependency lockfile consistency",
            "Ruff lint",
            "Workflow lint (actionlint)",
            "Workflow security audit (zizmor)",
            "maintenance-ci",
        ],
        "advisory_checks": ["pip-audit"],
        "advisory_check_run_names": ["Dependency CVE audit (pip-audit, advisory)"],
        "mandatory_check_groups": {
            "verify": ["Verify (syntax, workflow contract & offline tests)", "verify"],
            "lock-check": ["Dependency lockfile consistency", "lock-check"],
            "ruff": ["Ruff lint", "ruff"],
            "actionlint": ["Workflow lint (actionlint)", "actionlint"],
            "zizmor": ["Workflow security audit (zizmor)", "zizmor"],
            "pip-audit": ["Dependency CVE audit (pip-audit, advisory)", "pip-audit"],
            "maintenance-ci": ["maintenance-ci"],
        },
        "registered_tests": [
            "tests/test_configuration_contract.py",
            "tests/test_gachawiki_placeholder.py",
            "tests/test_maintenance.py",
            "tests/test_run_summary.py",
            "tests/test_schedule_epithet_and_settled.py",
            "tests/test_smoke.py",
        ],
        "optional_dev_docs": ["README.md", "AGENTS.md", "docs"],
    },
    "automerge": {
        "target_branch": "main",
        "merge_method": "SQUASH",
        "fallback_merge_methods": ["MERGE", "REBASE"],
        "trusted_check_apps": ["github-actions"],
        "trusted_ci_workflow_paths": [".github/workflows/ci.yml"],
        "trusted_ci_workflow_names": ["CI", "CI — compile + offline tests"],
        "trusted_proposer_workflow_paths": [".github/workflows/python_version_bump.yml"],
        "trusted_proposer_workflow_names": ["Python Version Bump"],
        "require_complete_check_set": True,
        "require_security_scan_evidence": True,
        "require_provenance": True,
        "required_checks": [
            "Verify (syntax, workflow contract & offline tests)",
            "Dependency lockfile consistency",
            "Ruff lint",
            "Workflow lint (actionlint)",
            "Workflow security audit (zizmor)",
            "Dependency CVE audit (pip-audit, advisory)",
            "maintenance-ci",
        ],
        "blocking_checks": ["verify", "lock-check", "ruff", "actionlint", "zizmor"],
        "security_checks": ["pip-audit", "Dependency CVE audit (pip-audit, advisory)"],
        "hold_labels": [
            "hold",
            "do-not-merge",
            "do not merge",
            "dont-merge",
            "blocked",
            "needs-review",
            "review-required",
            "human-review",
            "manual-review",
            "security-review",
            "wip",
        ],
        "waivers": [],
        "lanes": {
            "dependabot_pip": {
                "authors": ["dependabot[bot]", "app/dependabot"],
                "opt_in_var": "AUTO_MERGE_DEPENDABOT",
                "opt_in_value": "yes",
                "branch_prefixes": ["dependabot/pip/"],
                "allowed_files": [
                    "requirements.in",
                    "requirements.txt",
                    "requirements-dev.in",
                    "requirements-dev.txt",
                ],
                "allowed_update_types": ["patch", "minor"],
            },
            "dependabot_actions": {
                "authors": ["dependabot[bot]", "app/dependabot"],
                "opt_in_var": "AUTO_MERGE_DEPENDABOT",
                "opt_in_value": "yes",
                "branch_prefixes": [
                    "dependabot/github_actions/",
                    "dependabot/github-actions/",
                ],
                "allowed_files": [".github/workflows/*.yml"],
                "allowed_update_types": ["patch", "minor"],
            },
            "python_bump": {
                "authors": ["github-actions[bot]", "app/github-actions", "uesu"],
                "opt_in_var": "AUTO_MERGE_PYTHON_BUMP",
                "opt_in_value": "yes",
                "branch_names": ["chore/python-bump", "chore/python-version-bump"],
                "allowed_files": [
                    ".python-version",
                    "ruff.toml",
                    "requirements.txt",
                    "requirements-dev.txt",
                ],
                "allowed_update_types": ["patch"],
            },
        },
    },
}


@dataclass(frozen=True)
class SelectionResult:
    current_version: str
    selected_version: str
    selected_minor: str
    changed: bool
    status: str  # "up-to-date" | "deferred" | "proposed" | "review-required" | "failed"
    update_kind: str  # "none" | "patch" | "minor" | "override"
    review_required: bool
    auto_merge_eligible: bool
    highest_upstream_version: str | None
    clamped_by_policy: bool
    reason: str
    deferred_candidate: str | None = None
    soak_days_elapsed: float | None = None
    manual_override: bool = False


@dataclass(frozen=True)
class RuffTargetResult:
    target_version: str
    clamped: bool
    changed: bool
    reason: str


@dataclass(frozen=True)
class AutoMergeDecision:
    eligible: bool
    lane: str | None
    reason: str
    merge_method: str = "SQUASH"
    classification: str = "rejected"  # "auto-eligible" | "review-required" | "deferred" | "rejected"
    validated_head_sha: str = ""
    updates: list[dict[str, Any]] = field(default_factory=list)


def load_policy(repo_root: pathlib.Path = REPO_ROOT) -> dict[str, Any]:
    """Load `.github/maintenance.json` or fall back to DEFAULT_POLICY."""
    policy_file = repo_root / ".github" / "maintenance.json"
    if policy_file.is_file():
        return json.loads(policy_file.read_text(encoding="utf-8"))
    return json.loads(json.dumps(DEFAULT_POLICY))


def fetch_manifest(url: str = MANIFEST_URL) -> list[dict[str, Any]]:
    """Fetch the GitHub Actions Python versions manifest JSON with a bounded timeout."""
    req = urllib.request.Request(url, headers={"User-Agent": "gamexpress-maintenance/2.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def fetch_release_dates(
    primary_url: str = RELEASE_DATES_URL,
    fallback_url: str = RELEASE_DATES_FALLBACK_URL,
) -> dict[str, str]:
    """Fetch upstream CPython release dates (version -> ISO date string) with bounded timeouts.

    Consults `maintenance_common.fetch_release_dates` (python.org downloads API v2) first when using
    default URLs, then merges endoflife.date cycle/release dates as fallback coverage.
    """
    dates: dict[str, str] = {}
    if primary_url == RELEASE_DATES_URL:
        try:
            py_org_dates, state, _detail = maintenance_common.fetch_release_dates()
            if state in ("ok", "cache") and isinstance(py_org_dates, dict):
                dates.update(py_org_dates)
        except Exception:
            pass
    for url in (primary_url, fallback_url):
        if not url:
            continue
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "gamexpress-maintenance/2.0",
                    "Accept": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
                payload = json.loads(resp.read().decode("utf-8"))
            for k, v in _extract_release_dates_from_payload(payload).items():
                dates.setdefault(k, v)
            if dates:
                break
        except Exception:
            continue
    return dates


def _extract_release_dates_from_payload(payload: Any) -> dict[str, str]:
    """Normalize endoflife.date v1 / legacy payloads or flat mapping dicts into {version: date}."""
    out: dict[str, str] = {}
    if isinstance(payload, dict):
        # Direct {"3.15.0": "2026-10-01", ...} mapping
        for k, v in payload.items():
            if isinstance(v, str) and (EXACT_VERSION_RE.match(str(k)) or MINOR_VERSION_RE.match(str(k))):
                out[str(k)] = v
        # endoflife.date v1: {"result": {"releases": [...]}}
        result = payload.get("result")
        if isinstance(result, dict):
            releases = result.get("releases")
            if isinstance(releases, list):
                for item in releases:
                    if not isinstance(item, dict):
                        continue
                    cycle = str(item.get("name") or item.get("cycle") or "")
                    rel_date = str(item.get("releaseDate") or item.get("date") or "")
                    latest = item.get("latest")
                    if isinstance(latest, dict):
                        lat_name = str(latest.get("name") or "")
                        lat_date = str(latest.get("date") or rel_date)
                        if lat_name and lat_date:
                            out[lat_name] = lat_date
                    elif isinstance(latest, str) and latest:
                        lat_date = str(item.get("latestReleaseDate") or rel_date)
                        if lat_date:
                            out[latest] = lat_date
                    if cycle and rel_date:
                        out.setdefault(cycle, rel_date)
                        out.setdefault(f"{cycle}.0", rel_date)
    elif isinstance(payload, list):
        for item in payload:
            if not isinstance(item, dict):
                continue
            ver = str(item.get("version") or item.get("latest") or "")
            cycle = str(item.get("cycle") or "")
            rel_date = str(
                item.get("releaseDate")
                or item.get("latestReleaseDate")
                or item.get("date")
                or item.get("published_at")
                or ""
            )
            if ver and rel_date:
                out[ver] = rel_date
            if cycle and rel_date:
                out.setdefault(cycle, rel_date)
                out.setdefault(f"{cycle}.0", rel_date)
    return out


def parse_iso_timestamp(raw: str) -> datetime.datetime | None:
    """Parse an ISO-8601 date or timestamp into an aware UTC datetime."""
    cleaned = (raw or "").strip()
    if not cleaned:
        return None
    try:
        if cleaned.endswith("Z"):
            cleaned = cleaned[:-1] + "+00:00"
        dt = datetime.datetime.fromisoformat(cleaned)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt.astimezone(datetime.timezone.utc)
    except ValueError:
        try:
            d = datetime.date.fromisoformat(cleaned[:10])
            return datetime.datetime(d.year, d.month, d.day, tzinfo=datetime.timezone.utc)
        except ValueError:
            return None


def parse_exact_version(raw: str) -> tuple[int, int, int] | None:
    """Parse an exact numeric `MAJOR.MINOR.PATCH` version string; return None for prereleases/invalid."""
    m = EXACT_VERSION_RE.match((raw or "").strip())
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def parse_pin_version(raw: str) -> tuple[int, int, int]:
    """Parse either `MAJOR.MINOR.PATCH` or legacy `MAJOR.MINOR` into a 3-tuple."""
    cleaned = (raw or "").strip()
    exact = parse_exact_version(cleaned)
    if exact is not None:
        return exact
    m = MINOR_VERSION_RE.match(cleaned)
    if m:
        return int(m.group(1)), int(m.group(2)), 0
    raise ValueError(f"Invalid Python version pin: {raw!r}")


def has_usable_archive(
    entry: dict[str, Any],
    *,
    runner_os: str = "linux",
    runner_arch: str = "x64",
    runner_platform_version: str = "24.04",
) -> bool:
    """Return True iff a manifest entry has a usable archive for the exact target OS and architecture."""
    if entry.get("yanked") or entry.get("missing_archive"):
        return False
    files = entry.get("files")
    if not isinstance(files, list) or not files:
        return False

    accepted_archs = {runner_arch}
    if runner_arch == "x64":
        accepted_archs.add("x86_64")

    matching_os_arch: list[dict[str, Any]] = []
    for f in files:
        if not isinstance(f, dict):
            continue
        if f.get("platform") != runner_os:
            continue
        arch = str(f.get("arch") or "").strip()
        # Require an explicit matching architecture so arm64-only or arch-less entries never pass
        if arch not in accepted_archs:
            continue
        if "download_url" in f and not str(f.get("download_url") or "").strip():
            continue
        if "filename" in f and not str(f.get("filename") or "").strip():
            continue
        matching_os_arch.append(f)

    if not matching_os_arch:
        return False

    if runner_platform_version:
        versioned = [f for f in matching_os_arch if f.get("platform_version")]
        if versioned and not any(
            str(f.get("platform_version")) == runner_platform_version for f in versioned
        ):
            return False

    return True


def _lookup_release_date(
    version_str: str,
    entry: dict[str, Any] | None,
    release_dates: dict[str, str] | list[dict[str, Any]] | None,
) -> datetime.datetime | None:
    """Look up a release timestamp for `version_str` from `release_dates` or manifest entry."""
    norm_map = _extract_release_dates_from_payload(release_dates) if release_dates else {}
    minor_str = ".".join(version_str.split(".")[:2])
    for candidate_key in (version_str, f"{minor_str}.0", minor_str):
        if candidate_key in norm_map:
            dt = parse_iso_timestamp(norm_map[candidate_key])
            if dt is not None:
                return dt
    if isinstance(entry, dict):
        for field_name in ("release_date", "published_at", "releaseDate", "date"):
            raw = entry.get(field_name)
            if isinstance(raw, str) and raw.strip():
                dt = parse_iso_timestamp(raw)
                if dt is not None:
                    return dt
    return None


def select_target_python(
    manifest: list[dict[str, Any]],
    current_version: str,
    policy: dict[str, Any] | None = None,
    *,
    release_dates: dict[str, str] | list[dict[str, Any]] | None = None,
    now: datetime.datetime | str | None = None,
    override_version: str | None = None,
) -> SelectionResult:
    """Select the highest policy-compliant stable CPython release from the manifest.

    Implements the master specification's runtime proposer algorithm:
    1. Validate exact numeric `X.Y.Z` pin; compare versions numerically (`(maj, min, patch)`).
    2. Require stable release + exact runner OS/architecture (`linux`/`x64`/`24.04`).
    3. Prefer newest patch in the current `X.Y` series (`proposed`, auto-merge eligible).
    4. If no current-series patch exists, consider at most `X.(Y+1)` after `minor_soak_days` (30d).
       Missing release dates return `deferred: release-date-unavailable` (never `up-to-date`).
    5. Manual overrides validate syntax, no-downgrade, no-skipped-series, and runner availability,
       and always require human review (`review-required`).
    """
    pol = (policy or DEFAULT_POLICY).get("python", DEFAULT_POLICY["python"])
    supported_major = int(pol.get("supported_major", 3))
    min_minor = int(pol.get("min_minor", 11))
    max_minor_jump = int(pol.get("max_minor_jump", 1))
    minor_soak_days = float(pol.get("minor_soak_days", 30))
    # Support legacy policy dictionaries that explicitly set max_validated_minor / allow_minor_upgrades
    legacy_max_minor = pol.get("max_validated_minor")
    legacy_allow_minor = pol.get("allow_minor_upgrades")
    runner_os = str(pol.get("runner_os", "linux"))
    runner_arch = str(pol.get("runner_arch", "x64"))
    runner_platform_version = str(pol.get("runner_platform_version", "24.04"))

    cur_tuple = parse_pin_version(current_version)
    cur_major, cur_minor, cur_patch = cur_tuple
    cur_minor_str = f"{cur_major}.{cur_minor}"

    if isinstance(now, str):
        now_dt = parse_iso_timestamp(now) or datetime.datetime.now(datetime.timezone.utc)
    elif isinstance(now, datetime.datetime):
        now_dt = (
            now.replace(tzinfo=datetime.timezone.utc)
            if now.tzinfo is None
            else now.astimezone(datetime.timezone.utc)
        )
    else:
        now_dt = datetime.datetime.now(datetime.timezone.utc)

    valid_entries: dict[tuple[int, int, int], dict[str, Any]] = {}
    for entry in manifest:
        if not isinstance(entry, dict) or entry.get("stable") is not True:
            continue
        parsed = parse_exact_version(str(entry.get("version", "")))
        if parsed is None:
            continue
        if not has_usable_archive(
            entry,
            runner_os=runner_os,
            runner_arch=runner_arch,
            runner_platform_version=runner_platform_version,
        ):
            continue
        if parsed[0] != supported_major or parsed[1] < min_minor:
            continue
        valid_entries[parsed] = entry

    all_upstream_tuples = sorted(valid_entries)
    highest_upstream = (
        f"{all_upstream_tuples[-1][0]}.{all_upstream_tuples[-1][1]}.{all_upstream_tuples[-1][2]}"
        if all_upstream_tuples
        else None
    )

    # Handle manual override first
    if override_version is not None and str(override_version).strip():
        raw_ov = str(override_version).strip()
        ov_tuple = parse_exact_version(raw_ov)
        if ov_tuple is None:
            return SelectionResult(
                current_version=current_version.strip(),
                selected_version=current_version.strip(),
                selected_minor=cur_minor_str,
                changed=False,
                status="failed",
                update_kind="override",
                review_required=True,
                auto_merge_eligible=False,
                highest_upstream_version=highest_upstream,
                clamped_by_policy=False,
                reason=f"rejected: invalid-override-version ({raw_ov!r})",
                manual_override=True,
            )
        ov_maj, ov_min, _ov_patch = ov_tuple
        if ov_maj != supported_major or ov_min < min_minor:
            return SelectionResult(
                current_version=current_version.strip(),
                selected_version=current_version.strip(),
                selected_minor=cur_minor_str,
                changed=False,
                status="failed",
                update_kind="override",
                review_required=True,
                auto_merge_eligible=False,
                highest_upstream_version=highest_upstream,
                clamped_by_policy=False,
                reason=f"rejected: unsupported-major-or-minor ({raw_ov})",
                manual_override=True,
            )
        if ov_tuple < cur_tuple:
            return SelectionResult(
                current_version=current_version.strip(),
                selected_version=current_version.strip(),
                selected_minor=cur_minor_str,
                changed=False,
                status="failed",
                update_kind="override",
                review_required=True,
                auto_merge_eligible=False,
                highest_upstream_version=highest_upstream,
                clamped_by_policy=False,
                reason=f"rejected: downgrade-not-allowed ({raw_ov} < {current_version.strip()})",
                manual_override=True,
            )
        if ov_min > cur_minor + max_minor_jump:
            return SelectionResult(
                current_version=current_version.strip(),
                selected_version=current_version.strip(),
                selected_minor=cur_minor_str,
                changed=False,
                status="failed",
                update_kind="override",
                review_required=True,
                auto_merge_eligible=False,
                highest_upstream_version=highest_upstream,
                clamped_by_policy=True,
                reason=f"rejected: skipped-minor-series ({raw_ov} from {current_version.strip()})",
                manual_override=True,
            )
        if ov_tuple not in valid_entries:
            return SelectionResult(
                current_version=current_version.strip(),
                selected_version=current_version.strip(),
                selected_minor=cur_minor_str,
                changed=False,
                status="failed",
                update_kind="override",
                review_required=True,
                auto_merge_eligible=False,
                highest_upstream_version=highest_upstream,
                clamped_by_policy=False,
                reason=f"rejected: candidate-not-available-for-runner ({raw_ov})",
                manual_override=True,
            )
        if ov_tuple == cur_tuple:
            return SelectionResult(
                current_version=current_version.strip(),
                selected_version=current_version.strip(),
                selected_minor=cur_minor_str,
                changed=False,
                status="up-to-date",
                update_kind="none",
                review_required=False,
                auto_merge_eligible=False,
                highest_upstream_version=highest_upstream,
                clamped_by_policy=False,
                reason=f"up-to-date: manual override {raw_ov} matches current pin",
                manual_override=True,
            )
        return SelectionResult(
            current_version=current_version.strip(),
            selected_version=raw_ov,
            selected_minor=f"{ov_maj}.{ov_min}",
            changed=True,
            status="review-required",
            update_kind="override",
            review_required=True,
            auto_merge_eligible=False,
            highest_upstream_version=highest_upstream,
            clamped_by_policy=False,
            reason=f"review-required: manual override to {raw_ov} requires human review",
            manual_override=True,
        )

    if not valid_entries:
        raise RuntimeError(
            f"No eligible stable CPython {supported_major}.x release for {runner_os}/{runner_arch} "
            f"found in manifest."
        )

    # 1. Newest patch in the current minor series always comes first
    same_series = [
        t for t in all_upstream_tuples if t[0] == cur_major and t[1] == cur_minor and t[2] > cur_patch
    ]
    if same_series:
        best = max(same_series)
        best_str = f"{best[0]}.{best[1]}.{best[2]}"
        clamped = bool(all_upstream_tuples and max(all_upstream_tuples) > best)
        return SelectionResult(
            current_version=current_version.strip(),
            selected_version=best_str,
            selected_minor=cur_minor_str,
            changed=True,
            status="proposed",
            update_kind="patch",
            review_required=False,
            auto_merge_eligible=True,
            highest_upstream_version=highest_upstream,
            clamped_by_policy=clamped,
            reason=f"proposed: newest stable current-series patch {best_str} (from {current_version.strip()}).",
        )

    # 2. If no current-series patch exists, check if next minor is permitted and soaked
    if legacy_allow_minor is False:
        clamped = any(t > cur_tuple for t in all_upstream_tuples)
        return SelectionResult(
            current_version=current_version.strip(),
            selected_version=current_version.strip(),
            selected_minor=cur_minor_str,
            changed=False,
            status="up-to-date" if not clamped else "deferred",
            update_kind="none",
            review_required=False,
            auto_merge_eligible=False,
            highest_upstream_version=highest_upstream,
            clamped_by_policy=clamped,
            reason=(
                f"Already at highest current-series patch ({current_version.strip()})."
                if not clamped
                else f"deferred: minor upgrades disabled by policy (upstream {highest_upstream})."
            ),
        )

    max_allowed_minor = cur_minor + max_minor_jump
    if legacy_max_minor is not None:
        max_allowed_minor = min(max_allowed_minor, int(legacy_max_minor))

    next_series = [
        t
        for t in all_upstream_tuples
        if t[0] == cur_major and cur_minor < t[1] <= max_allowed_minor
    ]
    skipped_series = [
        t for t in all_upstream_tuples if t[0] == cur_major and t[1] > max_allowed_minor
    ]

    if next_series:
        best_next = max(next_series)
        best_next_str = f"{best_next[0]}.{best_next[1]}.{best_next[2]}"
        best_next_minor = f"{best_next[0]}.{best_next[1]}"
        entry = valid_entries[best_next]
        # Only enforce soak when minor_soak_days > 0 and legacy policy didn't explicitly bypass soak
        enforce_soak = minor_soak_days > 0 and (
            release_dates is not None
            or any(
                k in entry
                for k in ("release_date", "published_at", "releaseDate", "date")
            )
            or "minor_soak_days" in pol
        )
        if enforce_soak:
            rel_dt = _lookup_release_date(best_next_str, entry, release_dates)
            if rel_dt is None:
                return SelectionResult(
                    current_version=current_version.strip(),
                    selected_version=current_version.strip(),
                    selected_minor=cur_minor_str,
                    changed=False,
                    status="deferred",
                    update_kind="none",
                    review_required=False,
                    auto_merge_eligible=False,
                    highest_upstream_version=highest_upstream,
                    clamped_by_policy=True,
                    reason=f"deferred: release-date-unavailable for {best_next_str}",
                    deferred_candidate=best_next_str,
                )
            age_days = (now_dt - rel_dt).total_seconds() / 86400.0
            if age_days < minor_soak_days:
                return SelectionResult(
                    current_version=current_version.strip(),
                    selected_version=current_version.strip(),
                    selected_minor=cur_minor_str,
                    changed=False,
                    status="deferred",
                    update_kind="none",
                    review_required=False,
                    auto_merge_eligible=False,
                    highest_upstream_version=highest_upstream,
                    clamped_by_policy=True,
                    reason=(
                        f"deferred: soak-period-incomplete for {best_next_str} "
                        f"({age_days:.1f}d < {minor_soak_days:.0f}d)"
                    ),
                    deferred_candidate=best_next_str,
                    soak_days_elapsed=round(age_days, 1),
                )
            return SelectionResult(
                current_version=current_version.strip(),
                selected_version=best_next_str,
                selected_minor=best_next_minor,
                changed=True,
                status="review-required",
                update_kind="minor",
                review_required=True,
                auto_merge_eligible=False,
                highest_upstream_version=highest_upstream,
                clamped_by_policy=bool(skipped_series),
                reason=(
                    f"review-required: next-minor {best_next_str} passed "
                    f"{minor_soak_days:.0f}d soak ({age_days:.1f}d); human review required."
                ),
                soak_days_elapsed=round(age_days, 1),
            )

        return SelectionResult(
            current_version=current_version.strip(),
            selected_version=best_next_str,
            selected_minor=best_next_minor,
            changed=True,
            status="review-required",
            update_kind="minor",
            review_required=True,
            auto_merge_eligible=False,
            highest_upstream_version=highest_upstream,
            clamped_by_policy=bool(skipped_series),
            reason=f"review-required: next-minor {best_next_str} requires human review.",
        )

    if skipped_series:
        skipped_best = max(skipped_series)
        skipped_str = f"{skipped_best[0]}.{skipped_best[1]}.{skipped_best[2]}"
        return SelectionResult(
            current_version=current_version.strip(),
            selected_version=current_version.strip(),
            selected_minor=cur_minor_str,
            changed=False,
            status="deferred",
            update_kind="none",
            review_required=False,
            auto_merge_eligible=False,
            highest_upstream_version=highest_upstream,
            clamped_by_policy=True,
            reason=(
                f"deferred: skipped-minor-series ({skipped_str} exceeds max_minor_jump="
                f"{max_minor_jump} from {cur_minor_str})"
            ),
            deferred_candidate=skipped_str,
        )

    return SelectionResult(
        current_version=current_version.strip(),
        selected_version=current_version.strip(),
        selected_minor=cur_minor_str,
        changed=False,
        status="up-to-date",
        update_kind="none",
        review_required=False,
        auto_merge_eligible=False,
        highest_upstream_version=highest_upstream,
        clamped_by_policy=False,
        reason=f"up-to-date: already at newest stable release ({current_version.strip()}).",
    )


def ruff_understands(target: str) -> bool:
    """Return True if the installed `ruff` binary accepts `--target-version <target>`."""
    ruff = shutil.which("ruff")
    if not ruff:
        return True
    res = subprocess.run(
        [ruff, "check", "--target-version", target, "--stdin-filename", "x.py", "-"],
        input="",
        text=True,
        capture_output=True,
        check=False,
    )
    return res.returncode == 0


def resolve_ruff_target(
    minor_version: str,
    policy: dict[str, Any] | None = None,
    probe_binary: bool = True,
) -> tuple[str, bool, str]:
    """Return `(target_version, clamped, reason)` for `ruff.toml` given a Python minor."""
    pol = (policy or DEFAULT_POLICY).get("python", DEFAULT_POLICY["python"])
    known_targets: list[str] = list(
        pol.get("known_ruff_targets", ["py311", "py312", "py313", "py314"])
    )
    maj, minor, _ = parse_pin_version(minor_version)
    desired = f"py{maj}{minor}"

    def _target_tuple(tag: str) -> tuple[int, int]:
        m = re.match(r"^py(\d)(\d+)$", tag)
        if not m:
            return (0, 0)
        return int(m.group(1)), int(m.group(2))

    candidates = sorted(
        {t for t in known_targets if _target_tuple(t) <= (maj, minor)},
        key=_target_tuple,
        reverse=True,
    )
    if (
        desired not in candidates
        and _target_tuple(desired) <= (maj, minor)
        and desired in known_targets
    ):
        candidates.insert(0, desired)

    for candidate in candidates:
        if not probe_binary or ruff_understands(candidate):
            clamped = candidate != desired
            if clamped:
                reason = (
                    f"Clamped ruff.toml target-version to {candidate} because Python "
                    f"{maj}.{minor} ({desired}) exceeds Ruff's supported target enum."
                )
            else:
                reason = f"Ruff target-version {candidate} matches Python {maj}.{minor}."
            return candidate, clamped, reason

    fallback = "py311"
    return (
        fallback,
        fallback != desired,
        f"Fallback ruff.toml target-version {fallback} for Python {maj}.{minor}.",
    )


def update_ruff_toml(
    repo_root: pathlib.Path,
    minor_version: str,
    policy: dict[str, Any] | None = None,
    probe_binary: bool = True,
) -> RuffTargetResult:
    """Update `ruff.toml` target-version to the highest supported Ruff target <= minor_version."""
    pol = (policy or DEFAULT_POLICY).get("python", DEFAULT_POLICY["python"])
    ruff_path = repo_root / pol.get("ruff_config", "ruff.toml")
    target, clamped, reason = resolve_ruff_target(
        minor_version, policy=policy, probe_binary=probe_binary
    )
    if not ruff_path.is_file():
        return RuffTargetResult(
            target_version=target,
            clamped=clamped,
            changed=False,
            reason="ruff.toml not present in repository.",
        )
    text = ruff_path.read_text(encoding="utf-8")
    digits = target.removeprefix("py")
    new_text = RUFF_TARGET_RE.sub(rf"\g<1>{digits}\g<3>", text)
    changed = new_text != text
    if changed:
        ruff_path.write_text(new_text, encoding="utf-8")
    return RuffTargetResult(
        target_version=target,
        clamped=clamped,
        changed=changed,
        reason=reason,
    )


def read_python_pin(
    repo_root: pathlib.Path = REPO_ROOT, policy: dict[str, Any] | None = None
) -> str:
    """Read the runtime pin from `.python-version`, or fall back to workflow `python-version`."""
    pol = (policy or DEFAULT_POLICY).get("python", DEFAULT_POLICY["python"])
    pin_file = repo_root / pol.get("version_file", ".python-version")
    if pin_file.is_file():
        raw = pin_file.read_text(encoding="utf-8").strip()
        if raw:
            parse_pin_version(raw)
            return raw
    for rel in pol.get("workflow_files", DEFAULT_POLICY["python"]["workflow_files"]):
        wf = repo_root / rel
        if wf.is_file():
            m = PIN_RE.search(wf.read_text(encoding="utf-8"))
            if m:
                return m.group(2)
    raise RuntimeError("Could not locate Python version pin in .python-version or workflows.")


def assert_target_interpreter(
    repo_root: pathlib.Path = REPO_ROOT,
    expected_version: str | None = None,
    *,
    allow_same_minor: bool = False,
) -> str:
    """Assert that the running Python interpreter matches the pinned target runtime."""
    target = (expected_version or read_python_pin(repo_root)).strip()
    target_tuple = parse_pin_version(target)
    running = platform.python_version()
    running_tuple = parse_pin_version(running)

    if allow_same_minor:
        if running_tuple[:2] != target_tuple[:2]:
            raise RuntimeError(
                f"Target Python minor {target_tuple[0]}.{target_tuple[1]} required "
                f"(pinned {target}), but running interpreter is {running}."
            )
    elif running_tuple != target_tuple:
        raise RuntimeError(
            f"Exact target Python interpreter {target} required, "
            f"but running interpreter is {running}."
        )
    return running


def write_python_pin(
    repo_root: pathlib.Path,
    new_version: str,
    policy: dict[str, Any] | None = None,
) -> list[str]:
    """Write `.python-version` (or legacy workflow pins when `.python-version` is not used)."""
    pol = (policy or DEFAULT_POLICY).get("python", DEFAULT_POLICY["python"])
    pin_rel = pol.get("version_file", ".python-version")
    pin_file = repo_root / pin_rel
    changed: list[str] = []

    if pin_file.is_file() or not any(
        PIN_RE.search((repo_root / rel).read_text(encoding="utf-8"))
        for rel in pol.get("workflow_files", [])
        if (repo_root / rel).is_file()
    ):
        desired = f"{new_version.strip()}\n"
        current = pin_file.read_text(encoding="utf-8") if pin_file.is_file() else ""
        if current != desired:
            pin_file.write_text(desired, encoding="utf-8")
            changed.append(pin_rel)
        return changed

    for rel in pol.get("workflow_files", []):
        wf = repo_root / rel
        if not wf.is_file():
            continue
        text = wf.read_text(encoding="utf-8")
        new_text = PIN_RE.sub(rf"\g<1>{new_version.strip()}\g<3>", text)
        if new_text != text:
            wf.write_text(new_text, encoding="utf-8")
            changed.append(rel)
    return changed


def validate_workflow_python_pins(
    repo_root: pathlib.Path = REPO_ROOT,
    policy: dict[str, Any] | None = None,
    require_all_workflows: bool = True,
) -> list[str]:
    """Validate `.python-version`, workflow `setup-python` pins, SHA pins, and expression safety."""
    pol = (policy or DEFAULT_POLICY).get("python", DEFAULT_POLICY["python"])
    errors: list[str] = []

    pin_rel = pol.get("version_file", ".python-version")
    pin_file = repo_root / pin_rel
    if not pin_file.is_file():
        errors.append(f"Missing runtime pin file: {pin_rel}")
    else:
        raw_pin = pin_file.read_text(encoding="utf-8").strip()
        if parse_exact_version(raw_pin) is None:
            errors.append(
                f"{pin_rel} must contain an exact MAJOR.MINOR.PATCH version, got {raw_pin!r}"
            )

    configured_workflows = list(pol.get("workflow_files", []))
    present_workflows = [rel for rel in configured_workflows if (repo_root / rel).is_file()]
    if require_all_workflows and len(present_workflows) != len(configured_workflows):
        missing = sorted(set(configured_workflows) - set(present_workflows))
        errors.append(f"Missing expected workflow files: {', '.join(missing)}")
    if not present_workflows:
        errors.append("No configured workflow files exist to validate.")

    for rel in present_workflows:
        wf_path = repo_root / rel
        text = wf_path.read_text(encoding="utf-8")
        if "actions/setup-python@" not in text:
            errors.append(f"{rel}: does not use actions/setup-python")
            continue
        if re.search(r"python-version:\s*['\"]?3\.x['\"]?", text):
            errors.append(f"{rel}: uses forbidden floating python-version 3.x")
        # Allow python-version only in candidate validation job where needs.select.outputs.new_version is used
        for m in PIN_RE.finditer(text):
            errors.append(
                f"{rel}: hardcodes python-version ({m.group(2)!r}) instead of python-version-file: .python-version"
            )
        setup_count = len(re.findall(r"uses:\s*actions/setup-python@", text))
        file_count = len(PIN_FILE_RE.findall(text))
        candidate_expr_count = len(
            re.findall(r"python-version:\s*\$\{\{\s*needs\.select\.outputs\.new_version\s*\}\}", text)
        )
        check_latest_count = len(CHECK_LATEST_FALSE_RE.findall(text))
        if file_count + candidate_expr_count < setup_count:
            errors.append(
                f"{rel}: found {setup_count} setup-python step(s) but only "
                f"{file_count + candidate_expr_count} using .python-version / candidate output"
            )
        if check_latest_count < setup_count:
            errors.append(
                f"{rel}: found {setup_count} setup-python step(s) but only {check_latest_count} "
                "with check-latest: false"
            )

    # Also validate all present workflow YAML files for actionlint-equivalent job-env expression
    # and shellcheck quoting safety when PyYAML is available
    wf_dir = repo_root / ".github" / "workflows"
    if wf_dir.is_dir():
        try:
            import yaml
        except ImportError:
            yaml = None  # type: ignore[assignment]
        for wf_file in sorted(wf_dir.glob("*.yml")):
            rel_wf = str(wf_file.relative_to(repo_root))
            raw_wf = wf_file.read_text(encoding="utf-8")
            for idx, line in enumerate(raw_wf.splitlines(), 1):
                if re.match(r"^\s*-?\s*uses\s*:", line) and not USES_LINE_RE.match(line):
                    errors.append(
                        f"{rel_wf}:{idx}: action reference is not pinned to a 40-char SHA "
                        f"with version comment: {line.strip()!r}"
                    )
            if yaml is not None:
                try:
                    doc = yaml.safe_load(raw_wf)
                except Exception as exc:
                    errors.append(f"{rel_wf}: invalid YAML: {exc}")
                    continue
                if not isinstance(doc, dict):
                    continue
                # Check top-level and job-level env for disallowed `runner.` or `steps.` contexts
                top_env = doc.get("env") or {}
                if isinstance(top_env, dict):
                    for k, v in top_env.items():
                        if re.search(r"\$\{\{[^}]*\b(runner|steps|job)\.", str(v)):
                            errors.append(
                                f"{rel_wf}: workflow-level env {k!r} references unavailable context in {v!r}"
                            )
                for job_id, job in (doc.get("jobs") or {}).items():
                    if not isinstance(job, dict):
                        continue
                    job_env = job.get("env") or {}
                    if isinstance(job_env, dict):
                        for k, v in job_env.items():
                            if re.search(r"\$\{\{[^}]*\b(runner|steps|job)\.", str(v)):
                                errors.append(
                                    f"{rel_wf}: job {job_id!r} env {k!r} references context "
                                    f"not available at job level: {v!r}"
                                )
                    for step in job.get("steps") or []:
                        if not isinstance(step, dict):
                            continue
                        run_script = str(step.get("run") or "")
                        if re.search(r'(?<!")\$\{[A-Za-z0-9_]+:\+[^}]+\}', run_script):
                            errors.append(
                                f"{rel_wf}: job {job_id!r} step {step.get('name')!r} has "
                                "unquoted ${VAR:+...} expansion (shellcheck SC2086)"
                            )
    return errors


def normalize_lock_text(text: str, compile_command: str) -> str:
    """Normalize line endings and custom compile command header without fabricating interpreter headers."""
    normalized = text.replace("\r\n", "\n")
    normalized = re.sub(
        r"^(# by the following command:\n#\n#    ).*$",
        rf"\g<1>{compile_command}",
        normalized,
        count=1,
        flags=re.MULTILINE,
    )
    return normalized


def lockfile_sha256(repo_root: pathlib.Path = REPO_ROOT, rel_path: str = "requirements.txt") -> str:
    """Return the hex SHA-256 digest of `requirements.txt` (or '' if absent)."""
    target = repo_root / rel_path
    if not target.is_file():
        return ""
    return hashlib.sha256(target.read_bytes()).hexdigest()


def _parse_locked_packages(lock_text: str) -> dict[str, tuple[str, list[str]]]:
    """Parse `pkg==version` and its `--hash=sha256:...` list from a lockfile."""
    packages: dict[str, tuple[str, list[str]]] = {}
    lines = lock_text.splitlines()
    i = 0
    while i < len(lines):
        raw = lines[i].strip()
        if not raw or raw.startswith("#"):
            i += 1
            continue
        block = [raw.rstrip("\\").strip()]
        while lines[i].rstrip().endswith("\\") and i + 1 < len(lines):
            i += 1
            nxt = lines[i].strip()
            if nxt and not nxt.startswith("#"):
                block.append(nxt.rstrip("\\").strip())
        joined = " ".join(block)
        tokens = joined.split()
        if not tokens or "==" not in tokens[0]:
            raise ValueError(f"Unpinned requirement line in lockfile: {joined!r}")
        name, version = tokens[0].split("==", 1)
        hashes = [t for t in tokens[1:] if t.startswith("--hash=sha256:")]
        if not hashes:
            raise ValueError(f"Missing --hash=sha256: for {name}=={version}")
        packages[name.lower().replace("_", "-")] = (version, hashes)
        i += 1
    return packages


def compile_lockfile(
    repo_root: pathlib.Path,
    input_rel: str,
    output_rel: str,
    compile_command: str,
    *,
    require_exact_python: bool = True,
    expected_python: str | None = None,
    upgrade: bool = False,
) -> str:
    """Compile `input_rel` with the real running interpreter and `pip-tools` (no marker spoofing)."""
    pin = read_python_pin(repo_root)
    if expected_python:
        assert_target_interpreter(repo_root, expected_python, allow_same_minor=False)
    if require_exact_python:
        assert_target_interpreter(repo_root, pin, allow_same_minor=False)
    else:
        assert_target_interpreter(repo_root, pin, allow_same_minor=True)

    existing_out = repo_root / output_rel
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_out = pathlib.Path(tmp_dir) / pathlib.Path(output_rel).name
        if existing_out.is_file() and not upgrade:
            shutil.copy2(existing_out, tmp_out)
        cmd = [
            sys.executable,
            "-m",
            "piptools",
            "compile",
            "--generate-hashes",
            "--allow-unsafe",
            "--resolver=backtracking",
            "--strip-extras",
            f"--output-file={tmp_out.as_posix()}",
            input_rel,
        ]
        if upgrade:
            cmd.insert(4, "--upgrade")
        env = os.environ.copy()
        env["CUSTOM_COMPILE_COMMAND"] = compile_command
        res = subprocess.run(
            cmd,
            cwd=str(repo_root),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode != 0:
            raise RuntimeError(
                f"pip-compile failed for {input_rel} (exit {res.returncode}):\n{res.stderr}"
            )
        compiled = tmp_out.read_text(encoding="utf-8")
    return normalize_lock_text(compiled, compile_command)


def verify_lockfiles(
    repo_root: pathlib.Path = REPO_ROOT,
    policy: dict[str, Any] | None = None,
    recompile: bool = True,
    *,
    require_exact_python: bool = False,
    expected_python_override: str | None = None,
) -> tuple[bool, list[str]]:
    """Verify runtime and dev lockfiles for hash completeness, constraint alignment, and drift."""
    pol = policy or load_policy(repo_root)
    targets = pol.get("locks", DEFAULT_POLICY["locks"]).get("targets", [])
    errors: list[str] = []
    parsed_by_name: dict[str, dict[str, tuple[str, list[str]]]] = {}

    if expected_python_override:
        try:
            assert_target_interpreter(repo_root, expected_python_override, allow_same_minor=False)
        except RuntimeError as exc:
            errors.append(str(exc))
            return False, errors

    pin = read_python_pin(repo_root, pol)
    pin_tuple = parse_pin_version(pin)
    run_tuple = parse_pin_version(platform.python_version())
    same_minor = run_tuple[:2] == pin_tuple[:2]
    exact_match = run_tuple == pin_tuple

    if require_exact_python and not exact_match:
        errors.append(
            f"Exact target interpreter {pin} required for lock verification, "
            f"but running Python {platform.python_version()}."
        )
        return False, errors

    for target in targets:
        name = target["name"]
        in_rel = target["input_file"]
        out_rel = target["output_file"]
        cmd = target["compile_command"]
        in_path = repo_root / in_rel
        out_path = repo_root / out_rel

        if not in_path.is_file():
            errors.append(f"Missing lock input file: {in_rel}")
            continue
        if not out_path.is_file():
            errors.append(f"Missing committed lockfile: {out_rel}")
            continue

        committed_raw = out_path.read_text(encoding="utf-8")
        expected_header = f"# This file is autogenerated by pip-compile with Python {pin_tuple[0]}.{pin_tuple[1]}"
        if expected_header not in committed_raw:
            errors.append(
                f"{out_rel}: lockfile header does not match target Python {pin_tuple[0]}.{pin_tuple[1]}"
            )

        try:
            pkgs = _parse_locked_packages(committed_raw)
            parsed_by_name[name] = pkgs
        except ValueError as exc:
            errors.append(f"{out_rel}: {exc}")
            continue

        if name == "dev":
            in_text = in_path.read_text(encoding="utf-8")
            if "-c requirements.txt" not in in_text:
                errors.append(f"{in_rel}: must constrain against `-c requirements.txt`")
            compiler_cfg = pol.get("locks", {}).get("compiler", {})
            expected_pip = compiler_cfg.get("pip")
            expected_pt = compiler_cfg.get("pip_tools")
            if expected_pip and pkgs.get("pip", (None,))[0] != expected_pip:
                errors.append(
                    f"{out_rel}: expected pip=={expected_pip}, got {pkgs.get('pip', (None,))[0]}"
                )
            if expected_pt and pkgs.get("pip-tools", (None,))[0] != expected_pt:
                errors.append(
                    f"{out_rel}: expected pip-tools=={expected_pt}, "
                    f"got {pkgs.get('pip-tools', (None,))[0]}"
                )

        if recompile and same_minor:
            try:
                fresh = compile_lockfile(
                    repo_root,
                    in_rel,
                    out_rel,
                    cmd,
                    require_exact_python=require_exact_python,
                )
            except Exception as exc:
                errors.append(str(exc))
                continue
            expected = normalize_lock_text(committed_raw, cmd)
            if fresh != expected:
                errors.append(f"{out_rel} is out of date with {in_rel} (recompiled output differs)")

    runtime_pkgs = parsed_by_name.get("runtime", {})
    dev_pkgs = parsed_by_name.get("dev", {})
    if "pyyaml" in runtime_pkgs:
        errors.append("requirements.txt must not include test-only package pyyaml")
    for pkg_name, (rt_ver, _) in runtime_pkgs.items():
        if pkg_name in dev_pkgs and dev_pkgs[pkg_name][0] != rt_ver:
            errors.append(
                f"Version mismatch for {pkg_name} between requirements.txt ({rt_ver}) "
                f"and requirements-dev.txt ({dev_pkgs[pkg_name][0]})"
            )

    return len(errors) == 0, errors


def _parse_version_With_prerelease(raw: str) -> tuple[tuple[int, ...], bool] | None:
    """Parse a package or Action version string into `(numeric_tuple, is_prerelease)`."""
    cleaned = (raw or "").strip()
    if not cleaned:
        return None
    m = PEP440_SIMPLE_RE.match(cleaned)
    if not m:
        return None
    parts = [int(m.group(1)), int(m.group(2))]
    if m.group(3) is not None:
        parts.append(int(m.group(3)))
    else:
        parts.append(0)
    if m.group(4) is not None:
        parts.append(int(m.group(4)))
    suffix = (m.group(5) or "").strip()
    is_prerelease = bool(suffix)
    return tuple(parts), is_prerelease


def classify_version_update(old_raw: str, new_raw: str) -> tuple[str, bool, str]:
    """Classify a version change into `('patch'|'minor'|'major'|'downgrade'|'prerelease'|'invalid', safe, reason)`."""
    old_parsed = _parse_version_With_prerelease(old_raw)
    new_parsed = _parse_version_With_prerelease(new_raw)
    if old_parsed is None or new_parsed is None:
        return "invalid", False, f"Unparseable version transition {old_raw!r} -> {new_raw!r}"
    old_ver, old_pre = old_parsed
    new_ver, new_pre = new_parsed
    if old_pre or new_pre:
        return "prerelease", False, f"Prerelease/non-final version {old_raw} -> {new_raw}"
    if new_ver <= old_ver:
        return "downgrade", False, f"Non-upgrade version transition {old_raw} -> {new_raw}"
    if new_ver[0] != old_ver[0]:
        return "major", False, f"Major version upgrade {old_raw} -> {new_raw} requires human review"
    if old_ver[0] == 0 and new_ver[1] != old_ver[1]:
        return (
            "0.x-minor",
            False,
            f"Breaking-risk 0.x minor update {old_raw} -> {new_raw} requires human review",
        )
    if new_ver[1] != old_ver[1]:
        return "minor", True, f"Minor update {old_raw} -> {new_raw}"
    return "patch", True, f"Patch update {old_raw} -> {new_raw}"


def classify_dependency_change(upd: dict[str, Any]) -> tuple[str, bool, str]:
    """Classify a dependency/action change item (`updated`, `added`, `removed`, `hash-mutation`, etc.)."""
    name = str(upd.get("name") or "")
    old_raw = str(upd.get("from") or "").strip()
    new_raw = str(upd.get("to") or "").strip()
    change_kind = str(upd.get("change") or "updated").strip()
    file_rel = str(upd.get("file") or "").strip()
    loc_suffix = f" in {file_rel}" if file_rel else ""

    if change_kind == "added" or (not old_raw and new_raw):
        return (
            "added",
            False,
            f"Added new dependency {name}=={new_raw}{loc_suffix} requires human review",
        )
    if change_kind == "removed" or (old_raw and not new_raw):
        return (
            "removed",
            False,
            f"Removed dependency {name}=={old_raw}{loc_suffix} requires human review",
        )
    if change_kind == "hash-mutation":
        return (
            "hash-mutation",
            False,
            f"Hash-only or non-version mutation for {name} ({old_raw} -> {new_raw}){loc_suffix} requires human review",
        )
    if change_kind in ("ambiguous", "constraint-operator-change", "extras-or-marker-change", "sha-mutation"):
        return (
            change_kind,
            False,
            f"Unsafe {change_kind} for {name} ({old_raw} -> {new_raw}){loc_suffix} requires human review",
        )
    return classify_version_update(old_raw, new_raw)


def _extract_pip_updates_from_diffs(
    file_diffs: dict[str, str],
) -> tuple[list[dict[str, str]], list[str]]:
    """Extract all package transitions, additions, deletions, and hash mutations across `requirements*` diffs."""
    errors: list[str] = []
    updates: list[dict[str, str]] = []

    for path in sorted(file_diffs.keys()):
        patch = file_diffs.get(path)
        if not isinstance(patch, str) or not patch.strip():
            errors.append(f"{path}: missing or empty diff patch")
            continue

        removed_entries: dict[str, list[dict[str, Any]]] = {}
        added_entries: dict[str, list[dict[str, Any]]] = {}
        orphan_hash_changes: list[str] = []
        active_removed_pkg: str | None = None
        active_added_pkg: str | None = None

        for raw_line in patch.splitlines():
            if raw_line.startswith(("+++", "---", "@@")):
                active_removed_pkg = None
                active_added_pkg = None
                continue
            if raw_line.startswith(" "):
                ctx_text = raw_line[1:].strip()
                if (
                    ctx_text
                    and not ctx_text.startswith("#")
                    and not ctx_text.startswith("--hash=")
                    and ctx_text != "\\"
                ):
                    active_removed_pkg = None
                    active_added_pkg = None
                continue
            if not raw_line.startswith(("+", "-")):
                continue

            sign = raw_line[0]
            content = raw_line[1:].strip()
            if not content or content.startswith("#") or content == "\\":
                continue

            line_body = content[:-1].strip() if content.endswith("\\") else content

            if line_body.startswith("--hash="):
                hm = HASH_LINE_RE.match(line_body)
                if not hm:
                    errors.append(f"{path}: malformed hash line {content!r}")
                    continue
                digest = hm.group(1)
                if sign == "-":
                    if active_removed_pkg and removed_entries.get(active_removed_pkg):
                        removed_entries[active_removed_pkg][-1]["hashes"].append(digest)
                    else:
                        orphan_hash_changes.append(f"-{digest[:12]}")
                else:
                    if active_added_pkg and added_entries.get(active_added_pkg):
                        added_entries[active_added_pkg][-1]["hashes"].append(digest)
                    else:
                        orphan_hash_changes.append(f"+{digest[:12]}")
                continue

            active_removed_pkg = None
            active_added_pkg = None

            lowered = line_body.lower()
            if (
                line_body.startswith("-")
                or any(
                    bad in lowered
                    for bad in (
                        "git+",
                        "hg+",
                        "svn+",
                        "bzr+",
                        "http://",
                        "https://",
                        "ftp://",
                        "file:",
                        "ssh://",
                        " @ ",
                        "@http",
                        "@git",
                        "@file",
                        "--extra-index-url",
                        "--index-url",
                        "--find-links",
                        "--trusted-host",
                    )
                )
                or line_body.startswith(("./", "../", "/"))
            ):
                errors.append(f"{path}: forbidden option/URL/VCS/constraint directive in diff: {content!r}")
                continue

            if ";" in line_body or "[" in line_body or "]" in line_body:
                errors.append(
                    f"{path}: environment marker or package extras change requires human review: {content!r}"
                )
                pkg_token = re.split(r"[;\[\]=<>!~\s]", line_body, maxsplit=1)[0].strip().lower().replace("_", "-")
                updates.append(
                    {
                        "name": pkg_token or f"<marker:{path}>",
                        "from": line_body if sign == "-" else "",
                        "to": line_body if sign == "+" else "",
                        "file": path,
                        "change": "extras-or-marker-change",
                    }
                )
                continue

            if path.endswith(".in"):
                im = IN_REQ_LINE_RE.match(line_body)
                if not im:
                    errors.append(f"{path}: unpinned or complex requirement change {content!r} requires human review")
                    pkg_token = re.split(r"[=<>!~\s]", line_body, maxsplit=1)[0].strip().lower().replace("_", "-")
                    updates.append(
                        {
                            "name": pkg_token or f"<spec:{path}>",
                            "from": line_body if sign == "-" else "",
                            "to": line_body if sign == "+" else "",
                            "file": path,
                            "change": "constraint-operator-change",
                        }
                    )
                    continue
                pkg = im.group(1).lower().replace("_", "-")
                op = im.group(2)
                ver = im.group(3)
                entry = {"version": ver, "op": op, "hashes": []}
            else:
                pm = REQ_PIN_LINE_RE.match(line_body)
                if not pm:
                    errors.append(f"{path}: unexpected non-pinned lockfile diff line {content!r}")
                    continue
                pkg = pm.group(1).lower().replace("_", "-")
                ver = pm.group(2)
                entry = {"version": ver, "op": "==", "hashes": []}

            if sign == "-":
                removed_entries.setdefault(pkg, []).append(entry)
                active_removed_pkg = pkg
            else:
                added_entries.setdefault(pkg, []).append(entry)
                active_added_pkg = pkg

        if orphan_hash_changes:
            errors.append(f"{path}: hash-only mutation without package version transition requires human review")
            updates.append(
                {
                    "name": f"<hash-only:{path}>",
                    "from": "hash",
                    "to": "hash-modified",
                    "file": path,
                    "change": "hash-mutation",
                }
            )

        for pkg in sorted(set(removed_entries.keys()) | set(added_entries.keys())):
            rem_list = removed_entries.get(pkg, [])
            add_list = added_entries.get(pkg, [])
            if not rem_list and add_list:
                for a in add_list:
                    updates.append(
                        {
                            "name": pkg,
                            "from": "",
                            "to": str(a["version"]),
                            "file": path,
                            "change": "added",
                        }
                    )
            elif rem_list and not add_list:
                for r in rem_list:
                    updates.append(
                        {
                            "name": pkg,
                            "from": str(r["version"]),
                            "to": "",
                            "file": path,
                            "change": "removed",
                        }
                    )
            elif len(rem_list) != 1 or len(add_list) != 1:
                errors.append(f"{path}: duplicate or unbalanced entries for {pkg}")
                updates.append(
                    {
                        "name": pkg,
                        "from": str(rem_list[0]["version"]),
                        "to": str(add_list[-1]["version"]),
                        "file": path,
                        "change": "ambiguous",
                    }
                )
            else:
                r0 = rem_list[0]
                a0 = add_list[0]
                old_ver = str(r0["version"])
                new_ver = str(a0["version"])
                if r0.get("op", "==") != a0.get("op", "=="):
                    updates.append(
                        {
                            "name": pkg,
                            "from": f"{r0.get('op')}{old_ver}",
                            "to": f"{a0.get('op')}{new_ver}",
                            "file": path,
                            "change": "constraint-operator-change",
                        }
                    )
                elif old_ver == new_ver:
                    errors.append(
                        f"{path}: package {pkg}=={old_ver} modified without version change (hash/metadata mutation)"
                    )
                    updates.append(
                        {
                            "name": pkg,
                            "from": old_ver,
                            "to": new_ver,
                            "file": path,
                            "change": "hash-mutation",
                        }
                    )
                else:
                    updates.append(
                        {
                            "name": pkg,
                            "from": old_ver,
                            "to": new_ver,
                            "file": path,
                            "change": "updated",
                        }
                    )

    # Deduplicate identical transitions across files (e.g. requirements.txt and requirements-dev.txt)
    # while preserving any conflicting transitions for the same package across files.
    deduped: list[dict[str, str]] = []
    seen_keys: set[tuple[str, str, str, str]] = set()
    by_pkg: dict[str, set[tuple[str, str, str]]] = {}
    for u in updates:
        key = (u["name"], u["from"], u["to"], u.get("change", "updated"))
        by_pkg.setdefault(u["name"], set()).add((u["from"], u["to"], u.get("change", "updated")))
        if key not in seen_keys:
            seen_keys.add(key)
            deduped.append(u)

    for pkg, transitions in sorted(by_pkg.items()):
        if len(transitions) > 1:
            errors.append(
                f"Conflicting transitions for {pkg} across files: "
                + ", ".join(f"{f or '<none>'}->{t or '<none>'} ({c})" for f, t, c in sorted(transitions))
            )

    return deduped, errors


def _extract_action_updates_from_diffs(
    file_diffs: dict[str, str],
) -> tuple[list[dict[str, str]], list[str]]:
    """Validate that a workflow diff modifies only `uses: owner/repo@<40-sha> # vX.Y.Z` lines."""
    errors: list[str] = []
    updates: list[dict[str, str]] = []

    for path in sorted(file_diffs.keys()):
        patch = file_diffs.get(path)
        if not isinstance(patch, str) or not patch.strip():
            errors.append(f"{path}: missing diff content for workflow file")
            continue

        removed_by_repo: dict[str, list[tuple[str, str]]] = {}
        added_by_repo: dict[str, list[tuple[str, str]]] = {}

        for raw_line in patch.splitlines():
            if raw_line.startswith(("+++", "---", "@@")):
                continue
            if not raw_line.startswith(("+", "-")):
                continue
            sign = raw_line[0]
            content = raw_line[1:]
            if not content.strip():
                continue
            m = USES_LINE_RE.match(content)
            if not m:
                errors.append(
                    f"{path}: workflow diff modifies non-uses line or unpinned action: {content.strip()!r}"
                )
                continue
            repo_id, sha, ver = m.group(1), m.group(2), m.group(3)
            if sign == "-":
                removed_by_repo.setdefault(repo_id, []).append((sha, ver))
            else:
                added_by_repo.setdefault(repo_id, []).append((sha, ver))

        all_repos = sorted(set(removed_by_repo.keys()) | set(added_by_repo.keys()))
        if not all_repos:
            errors.append(f"{path}: workflow diff contains no valid uses: updates.")
            continue

        for repo_id in all_repos:
            rem_list = removed_by_repo.get(repo_id, [])
            add_list = added_by_repo.get(repo_id, [])
            if not rem_list and add_list:
                errors.append(f"{path}: added new action {repo_id!r}; requires human review.")
                for _sha, ver in add_list:
                    updates.append(
                        {"name": repo_id, "from": "", "to": ver, "file": path, "change": "added"}
                    )
            elif rem_list and not add_list:
                errors.append(f"{path}: removed action {repo_id!r}; requires human review.")
                for _sha, ver in rem_list:
                    updates.append(
                        {"name": repo_id, "from": ver, "to": "", "file": path, "change": "removed"}
                    )
            elif len(rem_list) != len(add_list):
                errors.append(
                    f"{path}: unbalanced uses: count for {repo_id!r} ({len(rem_list)} removed vs {len(add_list)} added)."
                )
                updates.append(
                    {
                        "name": repo_id,
                        "from": rem_list[0][1],
                        "to": add_list[-1][1],
                        "file": path,
                        "change": "ambiguous",
                    }
                )
            else:
                for (old_sha, old_ver), (new_sha, new_ver) in zip(rem_list, add_list):
                    if old_sha == new_sha or old_ver == new_ver:
                        errors.append(
                            f"{path}: SHA-only or version-comment-only mutation for {repo_id!r} ({old_ver}@{old_sha[:7]} -> {new_ver}@{new_sha[:7]})."
                        )
                        updates.append(
                            {
                                "name": repo_id,
                                "from": old_ver,
                                "to": new_ver,
                                "file": path,
                                "change": "sha-mutation",
                            }
                        )
                    else:
                        updates.append(
                            {
                                "name": repo_id,
                                "from": old_ver,
                                "to": new_ver,
                                "file": path,
                                "change": "updated",
                            }
                        )

    return updates, errors


def parse_proposer_provenance_from_api_jobs(
    jobs: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Extract proposal provenance from real GitHub Actions API job steps (`PROVENANCE ...`) or job output summary."""
    for job in jobs or []:
        if not isinstance(job, dict):
            continue
        if job.get("conclusion") and str(job.get("conclusion")).strip().lower() != "success":
            continue
        out_obj = job.get("output") if isinstance(job.get("output"), dict) else {}
        for blob in (str(out_obj.get("summary") or ""), str(out_obj.get("text") or "")):
            cm = re.search(
                r"<!--\s*GAMEXPRESS_PROPOSER_PROVENANCE:\s*(\{[\s\S]*?\})\s*-->",
                blob,
            )
            if cm:
                try:
                    parsed = json.loads(cm.group(1))
                    if isinstance(parsed, dict):
                        return parsed
                except Exception:
                    pass
        for step in job.get("steps") or []:
            if not isinstance(step, dict):
                continue
            if step.get("status") and str(step.get("status")).strip().lower() != "completed":
                continue
            if step.get("conclusion") and str(step.get("conclusion")).strip().lower() != "success":
                continue
            sname = str(step.get("name") or "")
            if not sname.startswith("PROVENANCE "):
                continue
            kv: dict[str, str] = {}
            for m in re.finditer(r"([a-z_]+)=([^\s]+)", sname, flags=re.IGNORECASE):
                kv[m.group(1).lower()] = m.group(2)
            pr_raw = kv.get("pr", "")
            return {
                "published_pr_number": int(pr_raw) if pr_raw and pr_raw != "none" and pr_raw.isdigit() else None,
                "published_head_sha": kv.get("head", "") if kv.get("head", "none") != "none" else "",
                "source_sha": kv.get("source", "") if kv.get("source", "none") != "none" else "",
                "old_version": kv.get("old", "") if kv.get("old", "none") != "none" else "",
                "new_version": kv.get("new", "") if kv.get("new", "none") != "none" else "",
                "update_kind": kv.get("kind", "") if kv.get("kind", "none") != "none" else "",
                "review_required": kv.get("review", "true").lower() == "true",
                "auto_merge_eligible": kv.get("eligible", "false").lower() == "true",
                "candidate_tree_sha256": kv.get("tree", "") if kv.get("tree", "none") != "none" else "",
                "dry_run": kv.get("dry_run", "false").lower() == "true",
            }
    return None


def resolve_proposer_provenance_from_api_runs(
    pr_data: dict[str, Any],
    proposer_runs: list[dict[str, Any]],
    jobs_by_run_id: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """Resolve `python_bump` provenance from raw GitHub REST API `workflow_runs` and `jobs` payloads."""
    pr_number = pr_data.get("pr_number")
    head_sha = str(pr_data.get("head_sha") or "").strip()
    base_sha = str(pr_data.get("base_sha") or "").strip()
    head_ref = str(pr_data.get("head_ref") or "chore/python-bump").strip()
    author = str(pr_data.get("author") or "").strip()
    author_type = str(pr_data.get("author_type") or "User").strip()
    actual_manifest = pr_data.get("actual_candidate_manifest")
    actual_tree_sha = str(
        pr_data.get("actual_candidate_tree_sha256")
        or (actual_manifest.get("tree_sha256") if isinstance(actual_manifest, dict) else "")
        or ""
    ).strip()

    inspected: list[dict[str, Any]] = []
    for r in proposer_runs or []:
        if not isinstance(r, dict) or not r.get("id"):
            continue
        run_id = r["id"]
        expected_attempt = int(r.get("run_attempt") or 1)
        raw_jobs = jobs_by_run_id.get(str(run_id)) or jobs_by_run_id.get(run_id) or []
        r_jobs = [
            j
            for j in raw_jobs
            if isinstance(j, dict)
            and (
                j.get("run_attempt") is None
                or int(j.get("run_attempt")) == expected_attempt
            )
        ]
        select_job = next((j for j in r_jobs if re.search(r"select", str(j.get("name") or ""), re.I)), None)
        validate_job = next((j for j in r_jobs if re.search(r"validate", str(j.get("name") or ""), re.I)), None)
        publish_job = next((j for j in r_jobs if re.search(r"publish", str(j.get("name") or ""), re.I)), None)
        pub_meta = parse_proposer_provenance_from_api_jobs(r_jobs) or {}

        select_conc = (
            str(select_job.get("conclusion") or "").lower()
            if select_job
            else str(pub_meta.get("select_conclusion") or "missing").lower()
        )
        validate_conc = (
            str(validate_job.get("conclusion") or "").lower()
            if validate_job
            else str(pub_meta.get("validate_conclusion") or "missing").lower()
        )
        publish_conc = (
            str(publish_job.get("conclusion") or "").lower()
            if publish_job
            else str(pub_meta.get("publish_conclusion") or "missing").lower()
        )
        is_dry_run = bool(
            pub_meta.get("dry_run") is True
            or str(pub_meta.get("dry_run") or "").lower() == "true"
            or (
                select_conc == "success"
                and validate_conc == "success"
                and publish_conc == "skipped"
            )
        )
        pub_pr_num = pub_meta.get("published_pr_number", pub_meta.get("pr_number"))
        if pub_pr_num is not None:
            try:
                pub_pr_num = int(pub_pr_num)
            except (ValueError, TypeError):
                pub_pr_num = None
        pub_head_sha = str(pub_meta.get("published_head_sha") or "").strip()
        pub_source_sha = str(pub_meta.get("source_sha") or r.get("head_sha") or "").strip()
        pub_tree_sha = str(pub_meta.get("candidate_tree_sha256") or "").strip()

        inspected.append(
            {
                "workflow": str(r.get("path") or ""),
                "workflow_name": str(r.get("name") or ""),
                "workflow_run_id": run_id,
                "workflow_run_attempt": expected_attempt,
                "workflow_event": str(r.get("event") or ""),
                "workflow_conclusion": str(r.get("conclusion") or "").lower(),
                "head_branch": str(r.get("head_branch") or "main"),
                "source_sha": pub_source_sha,
                "select_conclusion": select_conc,
                "validate_conclusion": validate_conc,
                "publish_conclusion": publish_conc,
                "dry_run": is_dry_run,
                "published_pr_number": pub_pr_num,
                "published_head_sha": pub_head_sha,
                "old_version": str(pub_meta.get("old_version") or "").strip(),
                "new_version": str(pub_meta.get("new_version") or "").strip(),
                "update_kind": str(pub_meta.get("update_kind") or "").strip(),
                "review_required": bool(pub_meta.get("review_required", True)),
                "auto_merge_eligible": bool(pub_meta.get("auto_merge_eligible", False)),
                "candidate_tree_sha256": pub_tree_sha,
                "candidate_manifest": pub_meta.get("candidate_manifest"),
            }
        )

    matched = (
        next(
            (
                rec
                for rec in inspected
                if pr_number is not None
                and rec["published_pr_number"] == int(pr_number)
                and rec["published_head_sha"]
                and rec["published_head_sha"] == head_sha
            ),
            None,
        )
        or next(
            (
                rec
                for rec in inspected
                if pr_number is not None and rec["published_pr_number"] == int(pr_number)
            ),
            None,
        )
        or (inspected[0] if inspected else None)
    )

    manifest_verified = bool(
        matched
        and matched["candidate_tree_sha256"]
        and re.fullmatch(r"[0-9a-f]{64}", matched["candidate_tree_sha256"])
        and (not actual_tree_sha or actual_tree_sha == matched["candidate_tree_sha256"])
    )
    verified_bump = bool(
        matched
        and matched["workflow"] == ".github/workflows/python_version_bump.yml"
        and matched["head_branch"] == "main"
        and matched["workflow_conclusion"] == "success"
        and matched["select_conclusion"] == "success"
        and matched["validate_conclusion"] == "success"
        and matched["publish_conclusion"] == "success"
        and not matched["dry_run"]
        and (pr_number is None or matched["published_pr_number"] == int(pr_number))
        and matched["published_head_sha"]
        and (not head_sha or matched["published_head_sha"] == head_sha)
        and matched["source_sha"]
        and (not base_sha or matched["source_sha"] == base_sha)
        and matched["update_kind"] == "patch"
        and matched["review_required"] is False
        and matched["auto_merge_eligible"] is True
        and manifest_verified
    )
    return {
        "verified": verified_bump,
        "lane": "python_bump",
        "publisher": author,
        "publisher_type": author_type,
        "source": "python-version-bump-workflow",
        "workflow": matched["workflow"] if matched else "",
        "workflow_name": matched["workflow_name"] if matched else "",
        "workflow_run_id": matched["workflow_run_id"] if matched else None,
        "workflow_run_attempt": matched["workflow_run_attempt"] if matched else None,
        "workflow_event": matched["workflow_event"] if matched else "",
        "workflow_conclusion": matched["workflow_conclusion"] if matched else "",
        "select_conclusion": matched["select_conclusion"] if matched else "missing",
        "validate_conclusion": matched["validate_conclusion"] if matched else "missing",
        "publish_conclusion": matched["publish_conclusion"] if matched else "missing",
        "dry_run": matched["dry_run"] if matched else False,
        "published_pr_number": matched["published_pr_number"] if matched else None,
        "published_head_sha": matched["published_head_sha"] if matched else "",
        "source_sha": matched["source_sha"] if matched else "",
        "old_version": matched["old_version"] if matched else "",
        "new_version": matched["new_version"] if matched else "",
        "update_kind": matched["update_kind"] if matched else "",
        "review_required": matched["review_required"] if matched else True,
        "auto_merge_eligible": matched["auto_merge_eligible"] if matched else False,
        "candidate_tree_sha256": matched["candidate_tree_sha256"] if matched else "",
        "candidate_manifest": matched["candidate_manifest"] if matched else None,
        "actual_candidate_tree_sha256": actual_tree_sha,
        "manifest_verified": manifest_verified,
        "body_tampered": False,
        "head_ref": head_ref,
        "head_sha": matched["published_head_sha"] if matched else "",
    }


def _evaluate_reviews(
    reviews: Any,
    review_decision: str = "",
    approval_required: bool = False,
) -> tuple[bool, str]:
    """Compute effective latest review state per reviewer and enforce hold/approval rules."""
    latest_by_user: dict[str, str] = {}
    if isinstance(reviews, list):
        for rev in reviews:
            if not isinstance(rev, dict):
                continue
            user = (
                str(rev.get("author") or rev.get("user_login") or "")
                or str((rev.get("user") or {}).get("login") or "")
            ).strip()
            state = str(rev.get("state") or "").strip().upper()
            if not user or not state:
                continue
            if state in ("APPROVED", "CHANGES_REQUESTED"):
                latest_by_user[user] = state
            elif state == "DISMISSED":
                latest_by_user.pop(user, None)
            # COMMENTED / PENDING never clear an active CHANGES_REQUESTED

    active_changes_requested = [
        u for u, st in sorted(latest_by_user.items()) if st == "CHANGES_REQUESTED"
    ]
    if active_changes_requested:
        return (
            False,
            f"Rejected: active CHANGES_REQUESTED review by {', '.join(active_changes_requested)}.",
        )

    norm_decision = (review_decision or "").strip().upper()
    if norm_decision == "CHANGES_REQUESTED":
        return False, "Rejected: review_decision is CHANGES_REQUESTED."

    active_approvals = [u for u, st in latest_by_user.items() if st == "APPROVED"]
    if (norm_decision == "REVIEW_REQUIRED" or approval_required) and not active_approvals:
        return False, "Rejected: required maintainer approval is missing."

    return True, "ok"


def _extract_security_findings_from_text(*texts: str) -> list[str]:
    """Extract unique CVE / GHSA / PYSEC identifiers or vulnerability count markers from scan text."""
    found: list[str] = []
    for txt in texts:
        if not txt:
            continue
        for m in ADVISORY_ID_RE.finditer(txt):
            aid = m.group(0)
            if aid not in found:
                found.append(aid)
        vm = VULN_COUNT_RE.search(txt)
        if vm and int(vm.group(1)) > 0 and not found:
            found.append(f"UNIDENTIFIED_VULNERABILITY_COUNT_{vm.group(1)}")
    return found


def evaluate_automerge(
    pr_data: dict[str, Any],
    policy: dict[str, Any] | None = None,
) -> AutoMergeDecision:
    """Verify whether a pull request satisfies all safety gates for automatic merge."""
    pol_root = policy or DEFAULT_POLICY
    pol = pol_root.get("automerge", DEFAULT_POLICY["automerge"])
    target_branch = str(pol.get("target_branch", "main"))
    merge_method = str(pol.get("merge_method", "SQUASH"))
    trusted_apps = {str(a).lower() for a in pol.get("trusted_check_apps", ["github-actions"])}
    trusted_ci_paths = {
        str(p).strip()
        for p in pol.get("trusted_ci_workflow_paths", [".github/workflows/ci.yml"])
        if str(p).strip()
    }
    trusted_ci_names = {
        str(n).strip()
        for n in pol.get("trusted_ci_workflow_names", ["CI", "CI — compile + offline tests"])
        if str(n).strip()
    }
    trusted_proposer_paths = {
        str(p).strip()
        for p in pol.get(
            "trusted_proposer_workflow_paths", [".github/workflows/python_version_bump.yml"]
        )
        if str(p).strip()
    }
    trusted_proposer_names = {
        str(n).strip()
        for n in pol.get("trusted_proposer_workflow_names", ["Python Version Bump"])
        if str(n).strip()
    }
    mandatory_groups: dict[str, list[str]] = dict(
        pol_root.get("ci", {}).get(
            "mandatory_check_groups",
            DEFAULT_POLICY["ci"]["mandatory_check_groups"],
        )
    )
    security_checks = list(
        pol.get("security_checks", ["pip-audit", "Dependency CVE audit (pip-audit, advisory)"])
    )
    hold_labels = {
        str(lbl).strip().lower()
        for lbl in pol.get(
            "hold_labels",
            DEFAULT_POLICY["automerge"]["hold_labels"],
        )
    }
    lanes: dict[str, Any] = pol.get("lanes", {})

    # 1. API error / pagination completeness checks (fail closed)
    if (
        pr_data.get("api_error")
        or pr_data.get("pagination_incomplete")
        or pr_data.get("truncated")
        or pr_data.get("incomplete_results")
    ):
        return AutoMergeDecision(
            False,
            None,
            "Rejected: GitHub API error or incomplete/truncated pagination.",
            merge_method,
            classification="deferred",
        )

    # 2. Same-repository & target branch verification (delegating to maintenance_common.repo_association_failure)
    base_repo = str(pr_data.get("base_repo") or "").strip()
    head_repo = str(pr_data.get("head_repo") or "").strip()
    expected_repo = str(pr_data.get("expected_repo") or base_repo).strip()
    assoc_failure = maintenance_common.repo_association_failure(
        {
            "head": {"repo": {"full_name": head_repo}},
            "base": {"repo": {"full_name": base_repo}},
        },
        expected_repo,
    )
    if assoc_failure or bool(pr_data.get("head_repo_fork", False)):
        return AutoMergeDecision(
            False,
            None,
            f"Rejected: PR is from a fork or missing repository identity ({assoc_failure or 'fork'}).",
            merge_method,
        )

    base_ref = str(pr_data.get("base_ref") or "").strip()
    if base_ref != target_branch:
        return AutoMergeDecision(
            False,
            None,
            f"Rejected: PR targets {base_ref!r} instead of {target_branch!r}.",
            merge_method,
        )

    # 3. PR open, non-draft, and head SHA stability
    state = str(pr_data.get("state") or "OPEN").upper()
    if state != "OPEN":
        return AutoMergeDecision(False, None, f"Rejected: PR state is {state!r}.", merge_method)

    if bool(pr_data.get("is_draft", False)):
        return AutoMergeDecision(
            False, None, "Rejected: PR is a draft.", merge_method, classification="deferred"
        )

    head_sha = str(pr_data.get("head_sha") or "").strip()
    refreshed_head_sha = str(pr_data.get("refreshed_head_sha") or "").strip()
    if refreshed_head_sha and head_sha and refreshed_head_sha != head_sha:
        return AutoMergeDecision(
            False,
            None,
            f"Rejected: PR head SHA changed during evaluation ({head_sha} -> {refreshed_head_sha}).",
            merge_method,
            classification="deferred",
        )

    # 4. Mergeability (unknown / null must never be converted to MERGEABLE)
    mergeable = pr_data.get("mergeable", "MERGEABLE")
    mergeable_state = str(pr_data.get("mergeable_state") or "").strip().lower()
    if mergeable is None or (
        isinstance(mergeable, str) and mergeable.strip().upper() in ("", "UNKNOWN", "NULL", "NONE")
    ):
        return AutoMergeDecision(
            False,
            None,
            "Rejected: PR mergeability is unknown; deferring until GitHub computes mergeable state.",
            merge_method,
            classification="deferred",
        )
    if mergeable is False or (
        isinstance(mergeable, str) and mergeable.strip().upper() not in ("MERGEABLE", "TRUE")
    ):
        return AutoMergeDecision(
            False, None, f"Rejected: PR is not mergeable ({mergeable!r}).", merge_method
        )
    if mergeable_state and mergeable_state not in ("clean", "has_hooks"):
        return AutoMergeDecision(
            False,
            None,
            f"Rejected: PR mergeable_state is {mergeable_state!r} (expected 'clean').",
            merge_method,
            classification="deferred" if mergeable_state == "unknown" else "rejected",
        )

    # 5. Hold labels check
    raw_labels = pr_data.get("labels") or []
    pr_labels: list[str] = []
    if isinstance(raw_labels, list):
        for item in raw_labels:
            if isinstance(item, dict):
                name = str(item.get("name") or "").strip().lower()
            else:
                name = str(item or "").strip().lower()
            if name:
                pr_labels.append(name)
    matched_holds = [
        lbl
        for lbl in pr_labels
        if lbl in hold_labels
        or any(tok in lbl for tok in ("hold", "do-not-merge", "do not merge", "review-required"))
    ]
    if matched_holds:
        return AutoMergeDecision(
            False,
            None,
            f"Rejected: PR has hold/review label(s): {', '.join(matched_holds)}.",
            merge_method,
            classification="review-required",
        )

    # 6. Reviews check (latest review per reviewer + approval requirements)
    reviews_ok, reviews_reason = _evaluate_reviews(
        pr_data.get("reviews"),
        review_decision=str(pr_data.get("review_decision") or ""),
        approval_required=bool(pr_data.get("approval_required", False)),
    )
    if not reviews_ok:
        return AutoMergeDecision(
            False,
            None,
            reviews_reason,
            merge_method,
            classification="review-required",
        )

    # 7. Changed files presence & pagination bound
    changed_files_raw = pr_data.get("changed_files")
    if not isinstance(changed_files_raw, list) or not changed_files_raw:
        return AutoMergeDecision(
            False, None, "Rejected: PR has no changed files listed.", merge_method
        )
    changed_files = [
        str(f).strip().removeprefix("./") for f in changed_files_raw if str(f).strip()
    ]
    if not changed_files:
        return AutoMergeDecision(
            False, None, "Rejected: PR has no valid changed file paths.", merge_method
        )
    files_total = pr_data.get("files_total_count")
    if isinstance(files_total, int) and files_total > len(changed_files):
        return AutoMergeDecision(
            False,
            None,
            f"Rejected: changed files list is truncated ({len(changed_files)}/{files_total}).",
            merge_method,
            classification="deferred",
        )

    # 8. Author & lane matching (never trust event actor or branch name alone)
    author_raw = pr_data.get("author")
    actor_raw = pr_data.get("actor")
    pr_author = str(author_raw if author_raw is not None else (actor_raw or "")).strip()
    head_ref = str(pr_data.get("head_ref") or "").strip()

    matched_lane: str | None = None
    matched_cfg: dict[str, Any] | None = None
    for lane_name, lane_cfg in lanes.items():
        allowed_authors = list(lane_cfg.get("authors") or lane_cfg.get("actors") or [])
        if pr_author not in allowed_authors:
            continue
        branch_names = list(lane_cfg.get("branch_names", []))
        branch_prefixes = list(lane_cfg.get("branch_prefixes", []))
        branch_ok = head_ref in branch_names or any(
            head_ref.startswith(pfx) for pfx in branch_prefixes
        )
        if branch_ok:
            matched_lane = lane_name
            matched_cfg = lane_cfg
            break

    if matched_lane is None or matched_cfg is None:
        return AutoMergeDecision(
            False,
            None,
            f"Rejected: PR author {pr_author!r} on branch {head_ref!r} does not match any trusted lane.",
            merge_method,
        )

    # Verify commit authors if commits metadata is supplied
    commits_raw = pr_data.get("commits")
    allowed_lane_authors = set(matched_cfg.get("authors") or matched_cfg.get("actors") or [])
    if isinstance(commits_raw, list):
        if not commits_raw:
            return AutoMergeDecision(
                False,
                matched_lane,
                "Rejected: commits list is empty.",
                merge_method,
            )
        for c in commits_raw:
            if not isinstance(c, dict):
                continue
            c_author = str(c.get("author") or c.get("login") or "").strip()
            if c_author and c_author not in allowed_lane_authors:
                return AutoMergeDecision(
                    False,
                    matched_lane,
                    f"Rejected: commit author {c_author!r} is not trusted for lane {matched_lane!r}.",
                    merge_method,
                )

    # 9. Independent opt-in variable verification for the matched lane
    opt_in_var = str(matched_cfg.get("opt_in_var") or "")
    opt_in_expected = str(matched_cfg.get("opt_in_value") or "yes")
    if opt_in_var:
        var_key_lower = opt_in_var.lower()
        vars_map = pr_data.get("vars") if isinstance(pr_data.get("vars"), dict) else {}
        if var_key_lower in pr_data:
            actual_opt_in = str(pr_data.get(var_key_lower) or "")
        elif opt_in_var in pr_data:
            actual_opt_in = str(pr_data.get(opt_in_var) or "")
        elif opt_in_var in vars_map:
            actual_opt_in = str(vars_map.get(opt_in_var) or "")
        else:
            actual_opt_in = str(os.environ.get(opt_in_var, "yes"))
        if actual_opt_in != opt_in_expected:
            return AutoMergeDecision(
                False,
                matched_lane,
                f"Rejected: {opt_in_var}={actual_opt_in!r} (expected {opt_in_expected!r}).",
                merge_method,
            )

    # 10. File allowlist check for the matched lane
    allowed_patterns = list(matched_cfg.get("allowed_files", []))
    disallowed = [
        path
        for path in changed_files
        if not any(fnmatch.fnmatch(path, pat) for pat in allowed_patterns)
    ]
    if disallowed:
        for path in disallowed:
            if path.startswith(".github/workflows/"):
                return AutoMergeDecision(
                    False,
                    matched_lane,
                    f"Rejected: PR modifies forbidden workflow path {path!r}.",
                    merge_method,
                )
        return AutoMergeDecision(
            False,
            matched_lane,
            f"Rejected: lane {matched_lane!r} does not allow file(s): {', '.join(disallowed)}.",
            merge_method,
        )

    # 11. Structural diff & version update risk classification per lane (G1)
    if pr_data.get("diff_truncated"):
        return AutoMergeDecision(
            False,
            matched_lane,
            "Rejected: missing or truncated diff patch (diff_truncated=true).",
            merge_method,
            classification="review-required",
        )
    file_diffs = pr_data.get("file_diffs") if isinstance(pr_data.get("file_diffs"), dict) else {}
    pr_title = str(pr_data.get("title") or pr_data.get("pr_title") or "").strip()
    classified_updates: list[dict[str, Any]] = []

    if file_diffs:
        missing_patches = [
            f
            for f in changed_files
            if f not in file_diffs
            or not isinstance(file_diffs.get(f), str)
            or not str(file_diffs.get(f) or "").strip()
        ]
        if missing_patches:
            return AutoMergeDecision(
                False,
                matched_lane,
                f"Rejected: missing or truncated diff patch for {', '.join(missing_patches)}.",
                merge_method,
                classification="review-required",
            )
        extra_diff_files = [
            f
            for f in sorted(file_diffs.keys())
            if f not in changed_files
            and not any(fnmatch.fnmatch(f, pat) for pat in allowed_patterns)
        ]
        if extra_diff_files:
            return AutoMergeDecision(
                False,
                matched_lane,
                f"Rejected: file_diffs contains disallowed path(s): {', '.join(extra_diff_files)}.",
                merge_method,
            )

    if matched_lane == "dependabot_pip":
        raw_updates = pr_data.get("dependency_updates")
        supplied_list: list[dict[str, str]] = []
        if isinstance(raw_updates, list) and raw_updates:
            for item in raw_updates:
                if isinstance(item, dict):
                    supplied_list.append(
                        {
                            "name": str(item.get("name") or item.get("package") or "")
                            .strip()
                            .lower()
                            .replace("_", "-"),
                            "from": str(item.get("from") or item.get("old_version") or "").strip(),
                            "to": str(item.get("to") or item.get("new_version") or "").strip(),
                            "change": str(item.get("change") or "updated").strip(),
                        }
                    )

        diff_updates: list[dict[str, str]] = []
        diff_errors: list[str] = []
        if file_diffs:
            diff_updates, diff_errors = _extract_pip_updates_from_diffs(file_diffs)

        if diff_updates:
            active_updates = list(diff_updates)
        elif supplied_list:
            active_updates = list(supplied_list)
        elif pr_title:
            m = DEP_BUMP_TITLE_RE.search(pr_title)
            if m:
                active_updates = [
                    {
                        "name": m.group(1).strip().lower().replace("_", "-"),
                        "from": m.group(2).strip(),
                        "to": m.group(3).strip(),
                        "change": "updated",
                    }
                ]
            else:
                active_updates = []
        else:
            active_updates = []

        # Classify EVERY update item first so `decision.updates` is always complete
        for upd in active_updates:
            kind, safe, reason = classify_dependency_change(upd)
            classified_updates.append({**upd, "kind": kind, "safe": safe, "reason": reason})

        # Also classify any supplied_list items not already in classified_updates so conflicting metadata is visible
        if supplied_list and diff_updates:
            diff_tuples = {
                (u["name"], u["from"], u["to"], u.get("change", "updated")) for u in diff_updates
            }
            supplied_tuples = {
                (u["name"], u["from"], u["to"], u.get("change", "updated")) for u in supplied_list
            }
            for sup in supplied_list:
                st = (sup["name"], sup["from"], sup["to"], sup.get("change", "updated"))
                if st not in diff_tuples:
                    kind, safe, reason = classify_dependency_change(sup)
                    classified_updates.append(
                        {**sup, "kind": kind, "safe": safe, "reason": f"metadata-mismatch: {reason}"}
                    )
            if supplied_tuples != diff_tuples:
                return AutoMergeDecision(
                    False,
                    matched_lane,
                    "Rejected: supplied dependency_updates metadata disagrees with authoritative diff content.",
                    merge_method,
                    classification="review-required",
                    updates=classified_updates,
                )

        if pr_title and diff_updates:
            tm = DEP_BUMP_TITLE_RE.search(pr_title)
            if tm:
                t_pkg = tm.group(1).strip().lower().replace("_", "-")
                t_old = tm.group(2).strip()
                t_new = tm.group(3).strip()
                pkg_in_diff = [u for u in diff_updates if u["name"] == t_pkg]
                if not pkg_in_diff or any(
                    u["from"] != t_old or u["to"] != t_new for u in pkg_in_diff
                ):
                    return AutoMergeDecision(
                        False,
                        matched_lane,
                        f"Rejected: PR title ({t_pkg} {t_old} -> {t_new}) disagrees with authoritative diff content.",
                        merge_method,
                        classification="review-required",
                        updates=classified_updates,
                    )

        if pr_data.get("require_diff_metadata") and not file_diffs:
            return AutoMergeDecision(
                False,
                matched_lane,
                "Rejected: missing authoritative file_diffs for dependency PR.",
                merge_method,
                updates=classified_updates,
            )

        if diff_errors:
            return AutoMergeDecision(
                False,
                matched_lane,
                f"Rejected: invalid dependency diff content: {'; '.join(diff_errors)}",
                merge_method,
                classification="review-required",
                updates=classified_updates,
            )

        if not classified_updates:
            return AutoMergeDecision(
                False,
                matched_lane,
                "Rejected: missing or unparseable dependency version transition metadata.",
                merge_method,
                updates=classified_updates,
            )

        unsafe_items = [u for u in classified_updates if not u.get("safe")]
        if unsafe_items:
            first_bad = unsafe_items[0]
            return AutoMergeDecision(
                False,
                matched_lane,
                f"Rejected: {first_bad.get('name')}: {first_bad.get('reason')}",
                merge_method,
                classification="review-required",
                updates=classified_updates,
            )

    elif matched_lane == "dependabot_actions":
        raw_updates = pr_data.get("action_updates")
        supplied_actions: list[dict[str, str]] = []
        if isinstance(raw_updates, list) and raw_updates:
            for item in raw_updates:
                if isinstance(item, dict):
                    supplied_actions.append(
                        {
                            "name": str(item.get("name") or item.get("action") or "").strip(),
                            "from": str(item.get("from") or item.get("old_version") or "")
                            .strip()
                            .lstrip("v"),
                            "to": str(item.get("to") or item.get("new_version") or "")
                            .strip()
                            .lstrip("v"),
                            "change": str(item.get("change") or "updated").strip(),
                        }
                    )

        diff_updates = []
        diff_errors = []
        if file_diffs:
            diff_updates, diff_errors = _extract_action_updates_from_diffs(file_diffs)

        active_actions = list(diff_updates) if diff_updates else list(supplied_actions)
        for upd in active_actions:
            kind, safe, reason = classify_dependency_change(upd)
            classified_updates.append({**upd, "kind": kind, "safe": safe, "reason": reason})

        if supplied_actions and diff_updates:
            diff_set = {
                (u["name"].lower(), u["from"].lstrip("v"), u["to"].lstrip("v"))
                for u in diff_updates
            }
            sup_set = {
                (u["name"].lower(), u["from"].lstrip("v"), u["to"].lstrip("v"))
                for u in supplied_actions
            }
            if sup_set != diff_set:
                return AutoMergeDecision(
                    False,
                    matched_lane,
                    "Rejected: supplied action_updates metadata disagrees with authoritative workflow diff.",
                    merge_method,
                    classification="review-required",
                    updates=classified_updates,
                )

        if pr_data.get("require_diff_metadata") and not file_diffs:
            return AutoMergeDecision(
                False,
                matched_lane,
                "Rejected: missing authoritative file_diffs for workflow update.",
                merge_method,
                updates=classified_updates,
            )

        if diff_errors:
            return AutoMergeDecision(
                False,
                matched_lane,
                f"Rejected: unsafe workflow diff: {'; '.join(diff_errors)}",
                merge_method,
                classification="review-required",
                updates=classified_updates,
            )

        if not classified_updates:
            return AutoMergeDecision(
                False,
                matched_lane,
                "Rejected: no valid SHA-pinned action updates found in workflow diff.",
                merge_method,
                updates=classified_updates,
            )

        unsafe_actions = [u for u in classified_updates if not u.get("safe")]
        if unsafe_actions:
            first_bad = unsafe_actions[0]
            return AutoMergeDecision(
                False,
                matched_lane,
                f"Rejected: {first_bad.get('name')}: {first_bad.get('reason')}",
                merge_method,
                classification="review-required",
                updates=classified_updates,
            )

    elif matched_lane == "python_bump":
        if ".python-version" not in changed_files:
            return AutoMergeDecision(
                False,
                matched_lane,
                "Rejected: python_bump PR must update .python-version.",
                merge_method,
            )
        if bool(pr_data.get("manual_override", False)) or bool(
            pr_data.get("review_required", False)
        ):
            return AutoMergeDecision(
                False,
                matched_lane,
                "Rejected: manual override or minor Python upgrade requires human review.",
                merge_method,
                classification="review-required",
            )

        # Also inspect any lockfile diffs in python_bump PRs so unrequested package mutations cannot slip in
        lock_diffs = {
            k: v for k, v in file_diffs.items() if k.startswith("requirements")
        }
        if lock_diffs:
            lock_updates, lock_errors = _extract_pip_updates_from_diffs(lock_diffs)
            if lock_errors or lock_updates:
                for lu in lock_updates:
                    kind, safe, reason = classify_dependency_change(lu)
                    classified_updates.append({**lu, "kind": kind, "safe": False, "reason": reason})
                return AutoMergeDecision(
                    False,
                    matched_lane,
                    "Rejected: python_bump PR contains unexpected package or hash mutations in lockfiles.",
                    merge_method,
                    classification="review-required",
                    updates=classified_updates,
                )

        py_upd = pr_data.get("python_update")
        sup_old_py = ""
        sup_new_py = ""
        if isinstance(py_upd, dict):
            sup_old_py = str(py_upd.get("from") or py_upd.get("old_version") or "").strip()
            sup_new_py = str(py_upd.get("to") or py_upd.get("new_version") or "").strip()

        diff_old_py = ""
        diff_new_py = ""
        if ".python-version" in file_diffs:
            patch_text = str(file_diffs[".python-version"])
            rem_lines: list[str] = []
            add_lines: list[str] = []
            for ln in patch_text.splitlines():
                if ln.startswith(("+++", "---", "@@")):
                    continue
                if ln.startswith("-"):
                    val = ln[1:].strip()
                    if val:
                        rem_lines.append(val)
                elif ln.startswith("+"):
                    val = ln[1:].strip()
                    if val:
                        add_lines.append(val)
            if len(rem_lines) != 1 or len(add_lines) != 1:
                return AutoMergeDecision(
                    False,
                    matched_lane,
                    "Rejected: .python-version diff must contain exactly one removed and one added version line.",
                    merge_method,
                )
            diff_old_py = rem_lines[0]
            diff_new_py = add_lines[0]

        title_old_py = ""
        title_new_py = ""
        if pr_title:
            m = PY_BUMP_TITLE_RE.match(pr_title)
            if m:
                title_old_py = (m.group(1) or "").strip()
                title_new_py = (m.group(2) or "").strip()

        old_py = diff_old_py or sup_old_py or title_old_py
        new_py = diff_new_py or sup_new_py or title_new_py

        if diff_new_py and sup_new_py and (diff_new_py != sup_new_py or (diff_old_py and sup_old_py and diff_old_py != sup_old_py)):
            return AutoMergeDecision(
                False,
                matched_lane,
                "Rejected: python_update metadata disagrees with .python-version diff content.",
                merge_method,
                classification="review-required",
            )
        if diff_new_py and title_new_py and (diff_new_py != title_new_py or (diff_old_py and title_old_py and diff_old_py != title_old_py)):
            return AutoMergeDecision(
                False,
                matched_lane,
                "Rejected: PR title disagrees with .python-version diff content.",
                merge_method,
                classification="review-required",
            )

        if not new_py:
            return AutoMergeDecision(
                False,
                matched_lane,
                "Rejected: unverified python-bump version transition or missing .python-version metadata.",
                merge_method,
            )

        new_tuple = parse_exact_version(new_py)
        if new_tuple is None:
            return AutoMergeDecision(
                False,
                matched_lane,
                f"Rejected: invalid target Python version {new_py!r}.",
                merge_method,
            )
        if old_py:
            old_tuple = parse_exact_version(old_py)
            if old_tuple is None:
                return AutoMergeDecision(
                    False,
                    matched_lane,
                    f"Rejected: invalid previous Python version {old_py!r}.",
                    merge_method,
                )
            if new_tuple[0] != old_tuple[0] or new_tuple[1] != old_tuple[1]:
                classified_updates.append(
                    {
                        "name": "python",
                        "from": old_py,
                        "to": new_py,
                        "kind": "minor" if new_tuple[0] == old_tuple[0] else "major",
                        "safe": False,
                    }
                )
                return AutoMergeDecision(
                    False,
                    matched_lane,
                    f"Rejected: Python minor/major transition {old_py} -> {new_py} requires human review.",
                    merge_method,
                    classification="review-required",
                    updates=classified_updates,
                )
            if new_tuple[2] <= old_tuple[2]:
                classified_updates.append(
                    {"name": "python", "from": old_py, "to": new_py, "kind": "downgrade", "safe": False}
                )
                return AutoMergeDecision(
                    False,
                    matched_lane,
                    f"Rejected: Python patch downgrade or no-op {old_py} -> {new_py}.",
                    merge_method,
                    updates=classified_updates,
                )
        classified_updates.append(
            {"name": "python", "from": old_py, "to": new_py, "kind": "patch", "safe": True}
        )

    # 12. Publisher & proposal provenance verification (G1/G2: never optional when required by policy)
    require_provenance = bool(pol.get("require_provenance", True))
    provenance = pr_data.get("provenance")
    if matched_lane == "python_bump" and (
        isinstance(pr_data.get("proposer_workflow_runs"), list)
        or (isinstance(provenance, dict) and isinstance(provenance.get("proposer_workflow_runs"), list))
    ):
        api_runs = (
            pr_data.get("proposer_workflow_runs")
            if isinstance(pr_data.get("proposer_workflow_runs"), list)
            else provenance.get("proposer_workflow_runs")
        )
        api_jobs = (
            pr_data.get("proposer_jobs_by_run")
            or pr_data.get("jobs_by_run_id")
            or (provenance.get("proposer_jobs_by_run") if isinstance(provenance, dict) else None)
            or (provenance.get("jobs_by_run_id") if isinstance(provenance, dict) else None)
            or {}
        )
        provenance = resolve_proposer_provenance_from_api_runs(pr_data, api_runs, api_jobs)
    if require_provenance or isinstance(provenance, dict):
        if not isinstance(provenance, dict):
            return AutoMergeDecision(
                False,
                matched_lane,
                "Rejected: missing publisher/proposal provenance object.",
                merge_method,
                updates=classified_updates,
            )
        if matched_lane in ("dependabot_pip", "dependabot_actions"):
            if provenance.get("verified") is not True:
                return AutoMergeDecision(
                    False,
                    matched_lane,
                    "Rejected: publisher/proposal provenance is not verified.",
                    merge_method,
                    updates=classified_updates,
                )
            prov_sha = str(provenance.get("head_sha") or "").strip()
            if head_sha and prov_sha and prov_sha != head_sha:
                return AutoMergeDecision(
                    False,
                    matched_lane,
                    f"Rejected: provenance head_sha {prov_sha!r} does not match PR head_sha {head_sha!r}.",
                    merge_method,
                    classification="deferred",
                    updates=classified_updates,
                )
            prov_pub = str(provenance.get("publisher") or "").strip()
            prov_src = str(provenance.get("source") or "").strip().lower()
            if prov_pub not in allowed_lane_authors or prov_src not in (
                "github-dependabot",
                "dependabot",
            ):
                return AutoMergeDecision(
                    False,
                    matched_lane,
                    f"Rejected: untrusted Dependabot provenance (publisher={prov_pub!r}, source={prov_src!r}).",
                    merge_method,
                    updates=classified_updates,
                )
        elif matched_lane == "python_bump":
            wf_ident = str(provenance.get("workflow") or "").strip()
            wf_name = str(provenance.get("workflow_name") or "").strip()
            wf_run_id = provenance.get("workflow_run_id")
            wf_conc = str(provenance.get("workflow_conclusion") or "").strip().lower()
            if (
                wf_ident not in (trusted_proposer_paths | trusted_proposer_names)
                and wf_name not in trusted_proposer_names
            ):
                return AutoMergeDecision(
                    False,
                    matched_lane,
                    f"Rejected: unexpected proposer workflow provenance {wf_ident or wf_name!r}.",
                    merge_method,
                    updates=classified_updates,
                )
            if not wf_run_id or wf_conc != "success":
                return AutoMergeDecision(
                    False,
                    matched_lane,
                    f"Rejected: proposer workflow run provenance is missing or unsuccessful (run_id={wf_run_id!r}, conclusion={wf_conc!r}).",
                    merge_method,
                    updates=classified_updates,
                )
            if provenance.get("dry_run") is True or str(provenance.get("dry_run") or "").strip().lower() == "true":
                return AutoMergeDecision(
                    False,
                    matched_lane,
                    "Rejected: proposer workflow run was a dry_run and did not publish this PR.",
                    merge_method,
                    classification="review-required",
                    updates=classified_updates,
                )
            for job_key in ("select_conclusion", "validate_conclusion", "publish_conclusion"):
                if job_key in provenance:
                    job_conc = str(provenance.get(job_key) or "").strip().lower()
                    if job_conc != "success":
                        return AutoMergeDecision(
                            False,
                            matched_lane,
                            f"Rejected: proposer workflow {job_key}={job_conc!r} (must be 'success').",
                            merge_method,
                            classification="review-required",
                            updates=classified_updates,
                        )
            pr_num_val = pr_data.get("pr_number")
            prov_pr_num = provenance.get("published_pr_number", provenance.get("pr_number"))
            if (pr_num_val is not None or prov_pr_num is not None) and (
                prov_pr_num is None or pr_num_val is None or int(prov_pr_num) != int(pr_num_val)
            ):
                return AutoMergeDecision(
                    False,
                    matched_lane,
                    f"Rejected: proposer run published PR #{prov_pr_num}, which does not match current PR #{pr_num_val}.",
                    merge_method,
                    classification="review-required",
                    updates=classified_updates,
                )
            prov_pub_sha = str(
                provenance.get("published_head_sha")
                if "published_head_sha" in provenance
                else (provenance.get("head_sha") or "")
            ).strip()
            if not prov_pub_sha or (head_sha and prov_pub_sha != head_sha):
                return AutoMergeDecision(
                    False,
                    matched_lane,
                    f"Rejected: proposer run published head {prov_pub_sha!r} does not match current PR head {head_sha!r}.",
                    merge_method,
                    classification="review-required",
                    updates=classified_updates,
                )
            prov_source_sha = str(provenance.get("source_sha") or "").strip()
            pr_base_sha = str(pr_data.get("base_sha") or "").strip()
            if prov_source_sha and pr_base_sha and prov_source_sha != pr_base_sha:
                return AutoMergeDecision(
                    False,
                    matched_lane,
                    f"Rejected: proposer run source_sha {prov_source_sha!r} does not match PR base_sha {pr_base_sha!r}.",
                    merge_method,
                    classification="deferred",
                    updates=classified_updates,
                )
            prov_old_ver = str(provenance.get("old_version") or "").strip()
            prov_new_ver = str(provenance.get("new_version") or "").strip()
            if prov_old_ver and old_py and prov_old_ver != old_py:
                return AutoMergeDecision(
                    False,
                    matched_lane,
                    f"Rejected: proposer provenance old_version {prov_old_ver!r} does not match diff old_version {old_py!r}.",
                    merge_method,
                    classification="review-required",
                    updates=classified_updates,
                )
            if prov_new_ver and new_py and prov_new_ver != new_py:
                return AutoMergeDecision(
                    False,
                    matched_lane,
                    f"Rejected: proposer provenance new_version {prov_new_ver!r} does not match diff new_version {new_py!r}.",
                    merge_method,
                    classification="review-required",
                    updates=classified_updates,
                )
            prov_kind = str(provenance.get("update_kind") or "patch").strip().lower()
            if prov_kind != "patch":
                return AutoMergeDecision(
                    False,
                    matched_lane,
                    f"Rejected: proposer provenance update_kind {prov_kind!r} is not 'patch'.",
                    merge_method,
                    classification="review-required",
                    updates=classified_updates,
                )
            if provenance.get("review_required") is True or provenance.get("auto_merge_eligible") is False:
                return AutoMergeDecision(
                    False,
                    matched_lane,
                    "Rejected: proposer provenance marks this update as review-required.",
                    merge_method,
                    classification="review-required",
                    updates=classified_updates,
                )
            if provenance.get("body_tampered") is True:
                return AutoMergeDecision(
                    False,
                    matched_lane,
                    "Rejected: PR body metadata was modified or contradicts immutable proposer run provenance.",
                    merge_method,
                    classification="review-required",
                    updates=classified_updates,
                )
            prov_tree_sha = str(provenance.get("candidate_tree_sha256") or "").strip()
            actual_tree_sha = str(
                pr_data.get("actual_candidate_tree_sha256")
                or provenance.get("actual_candidate_tree_sha256")
                or ""
            ).strip()
            if prov_tree_sha:
                if not re.fullmatch(r"[0-9a-f]{64}", prov_tree_sha):
                    return AutoMergeDecision(
                        False,
                        matched_lane,
                        f"Rejected: invalid proposer candidate_tree_sha256 {prov_tree_sha!r}.",
                        merge_method,
                        classification="review-required",
                        updates=classified_updates,
                    )
                if actual_tree_sha and actual_tree_sha != prov_tree_sha:
                    return AutoMergeDecision(
                        False,
                        matched_lane,
                        f"Rejected: published PR tree digest {actual_tree_sha!r} does not match validated candidate manifest {prov_tree_sha!r}.",
                        merge_method,
                        classification="review-required",
                        updates=classified_updates,
                    )
            if provenance.get("manifest_verified") is False:
                return AutoMergeDecision(
                    False,
                    matched_lane,
                    "Rejected: published PR tree failed candidate manifest verification.",
                    merge_method,
                    classification="review-required",
                    updates=classified_updates,
                )
            prov_manifest = provenance.get("candidate_manifest")
            actual_manifest = pr_data.get("actual_candidate_manifest") or provenance.get("actual_candidate_manifest")
            if (
                isinstance(prov_manifest, dict)
                and isinstance(actual_manifest, dict)
                and (
                    prov_manifest.get("tree_sha256") != actual_manifest.get("tree_sha256")
                    or prov_manifest.get("files") != actual_manifest.get("files")
                )
            ):
                return AutoMergeDecision(
                    False,
                    matched_lane,
                    "Rejected: published PR file manifest does not match validated candidate manifest.",
                    merge_method,
                    classification="review-required",
                    updates=classified_updates,
                )
            if provenance.get("verified") is not True:
                return AutoMergeDecision(
                    False,
                    matched_lane,
                    "Rejected: publisher/proposal provenance is not verified.",
                    merge_method,
                    updates=classified_updates,
                )
            published_commit_obj = pr_data.get("published_commit") or provenance.get("published_commit")
            if isinstance(published_commit_obj, dict):
                exp_login, exp_name, exp_email = maintenance_common.configured_commit_identity(pol_root)
                commit_id_err = maintenance_common.published_commit_identity_failure(
                    published_commit_obj,
                    head=head_sha,
                    expected_login=exp_login,
                    expected_name=exp_name,
                    expected_email=exp_email,
                )
                if commit_id_err:
                    return AutoMergeDecision(
                        False,
                        matched_lane,
                        f"Rejected: {commit_id_err}.",
                        merge_method,
                        classification="review-required",
                        updates=classified_updates,
                    )
            pub_ev_obj = pr_data.get("publication_evidence")
            if isinstance(pub_ev_obj, dict) and pub_ev_obj:
                pub_mode, pub_wf, pub_files = maintenance_common.publication_policy(pol_root)
                pinned_pip, pinned_tools = maintenance_common.compiler_pins(pol_root)
                pub_gate = maintenance_common.verify_publication_gate(
                    mode=pub_mode,
                    kind="python_bump",
                    evidence=pub_ev_obj,
                    pr={
                        "number": pr_data.get("pr_number"),
                        "user": {"login": pr_author},
                        "head": {"sha": head_sha, "ref": head_ref},
                    },
                    candidate_version=new_py,
                    trusted_proposer_path=pub_wf,
                    proposal_files=pub_files,
                    pinned_pip=pinned_pip,
                    pinned_pip_tools=pinned_tools,
                    repository=expected_repo,
                )
                if pub_gate.get("state") != "ready":
                    return AutoMergeDecision(
                        False,
                        matched_lane,
                        f"Rejected: {pub_gate.get('reason') or 'publication-evidence'}.",
                        merge_method,
                        classification="review-required",
                        updates=classified_updates,
                    )
        elif provenance.get("verified") is not True:
            return AutoMergeDecision(
                False,
                matched_lane,
                "Rejected: publisher/proposal provenance is not verified.",
                merge_method,
                updates=classified_updates,
            )

    # 13. Check runs, producing workflow identity, complete mandatory gate set, and real security evidence (G2)
    if not head_sha:
        return AutoMergeDecision(
            False,
            matched_lane,
            "Rejected: missing PR head_sha for check verification.",
            merge_method,
            updates=classified_updates,
        )

    producer_ev_obj = pr_data.get("producer_evidence")
    if isinstance(producer_ev_obj, dict) and producer_ev_obj:
        prod_policy = pol_root.get("check_producers") or {}
        expected_prod_names = list(pol_root.get("mandatory_check_names") or pol.get("required_checks") or [])
        prod_res = maintenance_common.verify_check_producers(
            producer_ev_obj,
            expected_names=expected_prod_names,
            head_sha=head_sha,
            producers=prod_policy,
            repository=expected_repo,
        )
        if prod_res.get("state") != "ready":
            return AutoMergeDecision(
                False,
                matched_lane,
                f"Rejected: {prod_res.get('reason') or 'producer-evidence'}.",
                merge_method,
                updates=classified_updates,
            )

    sec_ev_obj = pr_data.get("security_evidence")
    if isinstance(sec_ev_obj, dict):
        sec_mode, sec_req = maintenance_common.security_policy(pol_root)
        if pr_data.get("security_evidence_mode"):
            sec_mode = str(pr_data.get("security_evidence_mode"))
        if isinstance(pr_data.get("required_security_evidence"), list):
            sec_req = [str(k) for k in pr_data["required_security_evidence"] if k]
        sec_res = maintenance_common.verify_security_evidence(
            sec_ev_obj,
            sec_req,
            mode=sec_mode,
        )
        if sec_res.get("state") != "ready":
            return AutoMergeDecision(
                False,
                matched_lane,
                f"Rejected: {sec_res.get('reason') or 'security-evidence'}.",
                merge_method,
                classification="deferred" if sec_res.get("state") == "defer" else "review-required",
                updates=classified_updates,
            )

    check_runs_raw = pr_data.get("check_runs")
    checks_raw = pr_data.get("checks")
    checks_total = pr_data.get("checks_total_count")

    # Convert structured `checks` list if `check_runs` is not passed, but reject bare name->status dicts
    # when full workflow/app/SHA provenance is required.
    structured_runs: list[dict[str, Any]] = []
    if isinstance(check_runs_raw, list):
        if isinstance(checks_total, int) and checks_total > len(check_runs_raw):
            return AutoMergeDecision(
                False,
                matched_lane,
                f"Rejected: check_runs pagination is incomplete ({len(check_runs_raw)}/{checks_total}).",
                merge_method,
                classification="deferred",
                updates=classified_updates,
            )
        structured_runs = [r for r in check_runs_raw if isinstance(r, dict) and r.get("name")]
    elif isinstance(checks_raw, list):
        structured_runs = [r for r in checks_raw if isinstance(r, dict) and r.get("name")]

    if not structured_runs:
        if isinstance(checks_raw, dict) and checks_raw:
            # Bare dict checks have no head_sha, app_slug, producing workflow, or security step evidence.
            for check_name, raw_state in sorted(checks_raw.items()):
                st = str(raw_state or "").strip().upper()
                if st in ("PENDING", "IN_PROGRESS", "QUEUED", "WAITING", "REQUESTED"):
                    return AutoMergeDecision(
                        False,
                        matched_lane,
                        f"Rejected: check {check_name!r} is still {st!r}.",
                        merge_method,
                        classification="deferred",
                        updates=classified_updates,
                    )
                if st not in ("SUCCESS", "PASSED"):
                    return AutoMergeDecision(
                        False,
                        matched_lane,
                        f"Rejected: check {check_name!r} has non-passing state {st or 'EMPTY'!r}.",
                        merge_method,
                        updates=classified_updates,
                    )
            return AutoMergeDecision(
                False,
                matched_lane,
                "Rejected: check evidence lacks required head_sha, app_slug, producing workflow identity, and complete mandatory gate set.",
                merge_method,
                updates=classified_updates,
            )
        return AutoMergeDecision(
            False,
            matched_lane,
            "Rejected: zero checks reported on PR head; refusing to manufacture passing checks.",
            merge_method,
            classification="deferred",
            updates=classified_updates,
        )

    all_mandatory_names: set[str] = {
        alias for aliases in mandatory_groups.values() for alias in aliases
    }
    latest_by_check_name: dict[str, dict[str, Any]] = {}
    latest_rank_by_check_name: dict[str, tuple[int, int, int]] = {}

    for idx, run in enumerate(structured_runs):
        name = str(run.get("name") or "").strip()
        run_sha = str(run.get("head_sha") or "").strip()
        if not run_sha or run_sha != head_sha:
            return AutoMergeDecision(
                False,
                matched_lane,
                f"Rejected: check run {name!r} has missing or stale head_sha {run_sha!r} (expected {head_sha!r}).",
                merge_method,
                classification="deferred" if run_sha else "rejected",
                updates=classified_updates,
            )

        app_slug = (
            str(run.get("app_slug") or (run.get("app") or {}).get("slug") or "")
            .strip()
            .lower()
        )
        if not app_slug or app_slug not in trusted_apps:
            return AutoMergeDecision(
                False,
                matched_lane,
                f"Rejected: check run {name!r} has missing or untrusted app_slug {app_slug!r}.",
                merge_method,
                updates=classified_updates,
            )

        wf_path = str(run.get("workflow_path") or "").strip()
        wf_name = str(run.get("workflow_name") or "").strip()
        run_id_val = run.get("run_id")
        run_id_str = str(run_id_val).strip() if run_id_val is not None else ""

        if name in all_mandatory_names:
            is_trusted_ci_wf = (
                wf_path in trusted_ci_paths
                and (not wf_name or wf_name in trusted_ci_names)
                and bool(run_id_str)
            )
            if not is_trusted_ci_wf:
                return AutoMergeDecision(
                    False,
                    matched_lane,
                    f"Rejected: mandatory check {name!r} has missing or untrusted producing workflow provenance (workflow_path={wf_path!r}, workflow_name={wf_name!r}, run_id={run_id_str!r}).",
                    merge_method,
                    updates=classified_updates,
                )

        rid_num = int(run_id_str) if run_id_str.isdigit() else 0
        att_val = run.get("run_attempt")
        att_num = int(att_val) if str(att_val or "").isdigit() else 1
        id_val = run.get("id")
        id_num = int(id_val) if str(id_val or "").isdigit() else idx
        rank = (rid_num, att_num, id_num)
        if name not in latest_rank_by_check_name or rank >= latest_rank_by_check_name[name]:
            latest_rank_by_check_name[name] = rank
            latest_by_check_name[name] = run

    trusted_ci_runs_by_id: dict[str, list[dict[str, Any]]] = {}
    for name, run in sorted(latest_by_check_name.items()):
        run_status = str(run.get("status") or "").strip().upper()
        conclusion = str(run.get("conclusion") or run.get("state") or "").strip().upper()
        if run_status != "COMPLETED":
            return AutoMergeDecision(
                False,
                matched_lane,
                f"Rejected: check {name!r} is still {run_status or 'INCOMPLETE'!r}.",
                merge_method,
                classification="deferred",
                updates=classified_updates,
            )
        if conclusion not in ("SUCCESS", "PASSED"):
            return AutoMergeDecision(
                False,
                matched_lane,
                f"Rejected: check {name!r} has non-passing conclusion {conclusion or 'MISSING'!r}.",
                merge_method,
                updates=classified_updates,
            )
        if name in all_mandatory_names:
            run_id_str = str(run.get("run_id") or "").strip()
            trusted_ci_runs_by_id.setdefault(run_id_str, []).append(run)

    if not trusted_ci_runs_by_id:
        return AutoMergeDecision(
            False,
            matched_lane,
            "Rejected: no check runs from trusted CI workflow (.github/workflows/ci.yml) found on PR head.",
            merge_method,
            classification="deferred",
            updates=classified_updates,
        )

    # Select the latest CI workflow run_id on head_sha and require that ALL mandatory check groups
    # succeeded in that single workflow run (preventing partial/split rerun bypasses).
    latest_run_id = sorted(
        trusted_ci_runs_by_id.keys(),
        key=lambda rid: (int(rid) if rid.isdigit() else 0, rid),
    )[-1]
    latest_ci_runs = trusted_ci_runs_by_id[latest_run_id]
    latest_ci_names = {str(r.get("name") or "").strip() for r in latest_ci_runs}

    missing_groups: list[str] = []
    for group_key, accepted_names in mandatory_groups.items():
        if not any(alias in latest_ci_names for alias in accepted_names):
            missing_groups.append(accepted_names[0] if accepted_names else group_key)

    if missing_groups:
        return AutoMergeDecision(
            False,
            matched_lane,
            f"Rejected: incomplete mandatory CI check set on run {latest_run_id}; missing: {', '.join(missing_groups)}.",
            merge_method,
            classification="deferred",
            updates=classified_updates,
        )

    # 14. Legacy commit statuses check
    combined_status = str(pr_data.get("combined_status") or "").strip().lower()
    if combined_status in ("failure", "error", "pending"):
        return AutoMergeDecision(
            False,
            matched_lane,
            f"Rejected: commit combined_status is {combined_status!r}.",
            merge_method,
            classification="deferred" if combined_status == "pending" else "rejected",
            updates=classified_updates,
        )
    commit_statuses = pr_data.get("commit_statuses")
    if isinstance(commit_statuses, list):
        for st_obj in commit_statuses:
            if isinstance(st_obj, dict):
                st_val = str(st_obj.get("state") or "").strip().lower()
                ctx_name = str(st_obj.get("context") or "status")
                if st_val in ("failure", "error", "pending"):
                    return AutoMergeDecision(
                        False,
                        matched_lane,
                        f"Rejected: commit status {ctx_name!r} is {st_val!r}.",
                        merge_method,
                        classification="deferred" if st_val == "pending" else "rejected",
                        updates=classified_updates,
                    )

    # 15. Real security scan evidence & advisory check (G2: never trust advisory wrapper conclusion alone)
    sec_audit = str(pr_data.get("security_audit") or "").strip().lower()
    if sec_audit in ("failure", "failed", "error", "unavailable", "missing", "timed_out", "vulnerable"):
        return AutoMergeDecision(
            False,
            matched_lane,
            f"Rejected: security audit evidence is {sec_audit!r}.",
            merge_method,
            classification="review-required",
            updates=classified_updates,
        )

    latest_pip_audit_runs = [
        r
        for r in latest_ci_runs
        if str(r.get("name") or "").strip() in mandatory_groups.get("pip-audit", security_checks)
    ]
    if not latest_pip_audit_runs:
        return AutoMergeDecision(
            False,
            matched_lane,
            "Rejected: required pip-audit security check run is missing from CI run.",
            merge_method,
            classification="review-required",
            updates=classified_updates,
        )

    pip_audit_run = latest_pip_audit_runs[-1]
    security_scan = pr_data.get("security_scan") if isinstance(pr_data.get("security_scan"), dict) else {}
    if bool(pol.get("require_security_scan_evidence", True)) and not security_scan:
        return AutoMergeDecision(
            False,
            matched_lane,
            "Rejected: required security_scan evidence is missing.",
            merge_method,
            classification="review-required",
            updates=classified_updates,
        )

    # Inspect inner steps of the pip-audit job (because the outer job has continue-on-error: true)
    audit_steps = pip_audit_run.get("steps") if isinstance(pip_audit_run.get("steps"), list) else []
    real_audit_steps = [
        s
        for s in audit_steps
        if isinstance(s, dict)
        and any(
            tok in str(s.get("name") or "").lower()
            for tok in ("audit", "pip-audit", "osv", "vulnerability")
        )
    ]

    if not real_audit_steps and not security_scan.get("present"):
        return AutoMergeDecision(
            False,
            matched_lane,
            "Rejected: pip-audit check run has only outer wrapper status without inner audit step or security_scan evidence.",
            merge_method,
            classification="review-required",
            updates=classified_updates,
        )

    for st_item in audit_steps:
        if not isinstance(st_item, dict):
            continue
        st_name = str(st_item.get("name") or "step")
        st_status = str(st_item.get("status") or "completed").strip().lower()
        st_conc = str(st_item.get("conclusion") or "").strip().lower()
        if st_status != "completed" or st_conc not in ("success", "skipped"):
            return AutoMergeDecision(
                False,
                matched_lane,
                f"Rejected: pip-audit inner step {st_name!r} concluded with {st_conc or st_status!r} inside advisory wrapper.",
                merge_method,
                classification="review-required",
                updates=classified_updates,
            )

    for st_item in real_audit_steps:
        st_name = str(st_item.get("name") or "audit")
        st_conc = str(st_item.get("conclusion") or "").strip().lower()
        if st_conc != "success":
            return AutoMergeDecision(
                False,
                matched_lane,
                f"Rejected: pip-audit inner scan step {st_name!r} did not succeed (conclusion={st_conc!r}).",
                merge_method,
                classification="review-required",
                updates=classified_updates,
            )

    if security_scan:
        scan_status = str(security_scan.get("status") or "").strip().lower()
        step_conc = str(security_scan.get("step_conclusion") or "").strip().lower()
        scan_sha = str(security_scan.get("head_sha") or "").strip()
        if scan_sha and scan_sha != head_sha:
            return AutoMergeDecision(
                False,
                matched_lane,
                f"Rejected: security_scan head_sha {scan_sha!r} does not match PR head_sha {head_sha!r}.",
                merge_method,
                classification="deferred",
                updates=classified_updates,
            )
        if step_conc and step_conc != "success":
            return AutoMergeDecision(
                False,
                matched_lane,
                f"Rejected: security_scan step_conclusion is {step_conc!r} despite advisory wrapper.",
                merge_method,
                classification="review-required",
                updates=classified_updates,
            )
        if scan_status and scan_status != "clean":
            return AutoMergeDecision(
                False,
                matched_lane,
                f"Rejected: security_scan status is {scan_status!r} (expected 'clean').",
                merge_method,
                classification="review-required",
                updates=classified_updates,
            )

    # Collect findings from advisories, security_scan.findings, pip-audit output_title/summary/text, and annotations
    raw_findings: list[str] = []
    for src_list in (
        pr_data.get("advisories"),
        security_scan.get("findings") if security_scan else None,
        pip_audit_run.get("findings"),
    ):
        if isinstance(src_list, list):
            for item in src_list:
                fid = str(item.get("id") if isinstance(item, dict) else item).strip()
                if fid and fid not in raw_findings:
                    raw_findings.append(fid)

    annotations_text_parts: list[str] = []
    if isinstance(pip_audit_run.get("annotations"), list):
        for ann in pip_audit_run["annotations"]:
            if isinstance(ann, dict):
                annotations_text_parts.append(str(ann.get("message") or ""))
                annotations_text_parts.append(str(ann.get("title") or ""))
            else:
                annotations_text_parts.append(str(ann))

    text_findings = _extract_security_findings_from_text(
        str(pip_audit_run.get("output_title") or ""),
        str(pip_audit_run.get("output_summary") or ""),
        str(pip_audit_run.get("output_text") or ""),
        "\n".join(annotations_text_parts),
    )
    for tf in text_findings:
        if tf not in raw_findings:
            raw_findings.append(tf)

    if raw_findings:
        waivers = pol.get("waivers") or []
        now_dt = datetime.datetime.now(datetime.timezone.utc)
        active_waiver_ids: set[str] = set()
        for w in waivers:
            if not isinstance(w, dict):
                continue
            w_id = str(w.get("id") or "").strip()
            exp_dt = parse_iso_timestamp(str(w.get("expires_at") or ""))
            if w_id and exp_dt and exp_dt > now_dt:
                active_waiver_ids.add(w_id)
        unwaived = [fid for fid in raw_findings if fid not in active_waiver_ids]
        if unwaived:
            return AutoMergeDecision(
                False,
                matched_lane,
                f"Rejected: unresolved security advisories from pip-audit scan: {', '.join(unwaived)}.",
                merge_method,
                classification="review-required",
                updates=classified_updates,
            )

    return AutoMergeDecision(
        True,
        matched_lane,
        f"Eligible for {merge_method} merge in lane {matched_lane!r}.",
        merge_method,
        classification="auto-eligible",
        validated_head_sha=head_sha,
        updates=classified_updates,
    )


def verify_merge_response(
    merge_response: dict[str, Any] | None,
    *,
    expected_head_sha: str = "",
) -> tuple[bool, str]:
    """Verify that the GitHub REST merge API response confirmed `merged: true` on the expected SHA."""
    if not isinstance(merge_response, dict):
        return False, "Merge failed: empty or non-JSON response from merge API."
    if merge_response.get("merged") is not True:
        msg = str(merge_response.get("message") or "merged is not true")
        return False, f"Merge failed: API returned merged={merge_response.get('merged')!r} ({msg})."
    sha = str(merge_response.get("sha") or "").strip()
    if not sha:
        return False, "Merge failed: API response did not include a merge commit SHA."
    if (
        expected_head_sha
        and merge_response.get("head_sha")
        and str(merge_response["head_sha"]).strip() != expected_head_sha
    ):
        return (
            False,
            f"Merge failed: head SHA mismatch ({merge_response['head_sha']} != {expected_head_sha}).",
        )
    return True, f"Merged successfully ({sha})."


def render_bump_pr_body(
    selection: SelectionResult,
    ruff_res: RuffTargetResult,
    changed_files: list[str],
    policy: dict[str, Any] | None = None,
) -> str:
    """Render the Markdown pull-request body for a Python runtime maintenance update."""
    pol = (policy or DEFAULT_POLICY).get("python", DEFAULT_POLICY["python"])
    ruff_line = (
        f"`{ruff_res.target_version}` (updated)"
        if ruff_res.changed
        else f"`{ruff_res.target_version}` (unchanged)"
    )
    notes: list[str] = []
    if ruff_res.clamped:
        notes.append(f"- **Ruff target clamp:** {ruff_res.reason}")
    if selection.review_required:
        notes.append(
            f"- **Human review required:** `{selection.update_kind}` update (`{selection.reason}`)."
        )
    if selection.clamped_by_policy and selection.highest_upstream_version:
        notes.append(
            f"- **Runtime policy note:** Upstream `{selection.highest_upstream_version}` was "
            f"evaluated under `.github/maintenance.json` (`max_minor_jump="
            f"{pol.get('max_minor_jump', 1)}`, `minor_soak_days={pol.get('minor_soak_days', 30)}`)."
        )
    notes_block = "\n".join(notes) if notes else "- All runtime and linter targets are aligned."
    files_md = "\n".join(f"- `{p}`" for p in changed_files) if changed_files else "- _(none)_"

    return (
        f"## Summary\n\n"
        f"Updates the pinned CPython runtime in `.python-version` from "
        f"`{selection.current_version}` to **`{selection.selected_version}`**.\n\n"
        f"| Field | Value |\n"
        f"| --- | --- |\n"
        f"| Previous `.python-version` | `{selection.current_version}` |\n"
        f"| Selected `.python-version` | `{selection.selected_version}` |\n"
        f"| Update classification | `{selection.update_kind}` (`{selection.status}`) |\n"
        f"| Review required | `{str(selection.review_required).lower()}` |\n"
        f"| Auto-merge eligible | `{str(selection.auto_merge_eligible).lower()}` |\n"
        f"| Proposer workflow | `.github/workflows/python_version_bump.yml` |\n"
        f"| `ruff.toml` `target-version` | {ruff_line} |\n\n"
        f"## Policy & Compatibility Notes\n\n"
        f"{notes_block}\n\n"
        f"## Changed Files\n\n"
        f"{files_md}\n"
    )


def write_github_outputs(values: dict[str, str]) -> None:
    """Write key=value lines to `$GITHUB_OUTPUT` if set, and echo to stdout."""
    sink = os.environ.get("GITHUB_OUTPUT")
    for k, v in values.items():
        print(f"{k}={v}")
        if sink:
            with open(sink, "a", encoding="utf-8") as fh:
                fh.write(f"{k}={v}\n")


def apply_python_version(
    new_version: str,
    repo_root: pathlib.Path = REPO_ROOT,
    policy: dict[str, Any] | None = None,
) -> tuple[list[str], RuffTargetResult]:
    """Write `new_version` to `.python-version` and update `ruff.toml` if present."""
    pol = policy or load_policy(repo_root)
    parsed = parse_pin_version(new_version)
    minor_str = f"{parsed[0]}.{parsed[1]}"
    changed_files = write_python_pin(repo_root, new_version, pol)
    ruff_res = update_ruff_toml(repo_root, minor_str, pol)
    if ruff_res.changed:
        changed_files.append(pol.get("python", {}).get("ruff_config", "ruff.toml"))
    return changed_files, ruff_res


def run_select(
    repo_root: pathlib.Path = REPO_ROOT,
    manifest: list[dict[str, Any]] | None = None,
    policy: dict[str, Any] | None = None,
    *,
    release_dates: dict[str, str] | list[dict[str, Any]] | None = None,
    override_version: str | None = None,
) -> SelectionResult:
    """Run candidate selection without modifying any files."""
    pol = policy or load_policy(repo_root)
    current = read_python_pin(repo_root, pol)
    py_pol = pol.get("python", {})
    manifest_data = (
        manifest
        if manifest is not None
        else fetch_manifest(py_pol.get("manifest_url", MANIFEST_URL))
    )
    dates_data = (
        release_dates
        if release_dates is not None
        else fetch_release_dates(
            py_pol.get("release_dates_url", RELEASE_DATES_URL),
            py_pol.get("release_dates_fallback_url", RELEASE_DATES_FALLBACK_URL),
        )
    )
    selection = select_target_python(
        manifest_data,
        current,
        pol,
        release_dates=dates_data,
        override_version=override_version,
    )
    write_github_outputs(
        {
            "changed": "true" if selection.changed else "false",
            "status": selection.status,
            "update_kind": selection.update_kind,
            "review_required": "true" if selection.review_required else "false",
            "auto_merge_eligible": "true" if selection.auto_merge_eligible else "false",
            "old_version": selection.current_version,
            "new_version": selection.selected_version,
            "selected_minor": selection.selected_minor,
            "deferred_candidate": selection.deferred_candidate or "",
            "reason": selection.reason,
        }
    )
    return selection


def run_bump(
    repo_root: pathlib.Path = REPO_ROOT,
    manifest: list[dict[str, Any]] | None = None,
    policy: dict[str, Any] | None = None,
    *,
    release_dates: dict[str, str] | list[dict[str, Any]] | None = None,
    override_version: str | None = None,
    dry_run: bool = False,
) -> int:
    """Execute the Python runtime selection and (unless `dry_run=True`) file update flow."""
    pol = policy or load_policy(repo_root)
    selection = run_select(
        repo_root,
        manifest=manifest,
        policy=pol,
        release_dates=release_dates,
        override_version=override_version,
    )
    if selection.status == "failed":
        print(f"ERROR: {selection.reason}", file=sys.stderr)
        return 1
    if not selection.changed or dry_run:
        return 0

    changed_files, ruff_res = apply_python_version(
        selection.selected_version, repo_root=repo_root, policy=pol
    )
    if not changed_files:
        return 0

    body_path = pathlib.Path(os.environ.get("PR_BODY_PATH", "/tmp/python-bump-body.md"))
    body_path.write_text(
        render_bump_pr_body(selection, ruff_res, changed_files, pol),
        encoding="utf-8",
    )

    write_github_outputs(
        {
            "ruff_bumped": "true" if ruff_res.changed else "false",
            "ruff_target": ruff_res.target_version,
            "ruff_clamped": "true" if ruff_res.clamped else "false",
            "body_path": str(body_path),
            "changed_files": " ".join(changed_files),
        }
    )
    return 0


def verify_bump_diff(
    repo_root: pathlib.Path = REPO_ROOT, policy: dict[str, Any] | None = None
) -> tuple[bool, list[str]]:
    """Verify `git status --porcelain` contains only allowlisted Python bump files."""
    pol = policy or load_policy(repo_root)
    allowed = set(
        pol.get("python", {}).get(
            "allowed_bump_files",
            [".python-version", "ruff.toml", "requirements.txt", "requirements-dev.txt"],
        )
    )
    res = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    if res.returncode != 0:
        return False, [f"git status failed: {res.stderr.strip()}"]
    unexpected: list[str] = []
    for line in res.stdout.splitlines():
        if not line.strip():
            continue
        path = line[3:].strip()
        if path not in allowed:
            unexpected.append(path)
    return len(unexpected) == 0, unexpected


def compute_candidate_manifest(
    repo_root: pathlib.Path = REPO_ROOT,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compute SHA-256 digests of the candidate runtime and lockfiles after validation."""
    pol = policy or load_policy(repo_root)
    tracked_files = list(
        pol.get("python", {}).get(
            "allowed_bump_files",
            [".python-version", "ruff.toml", "requirements.txt", "requirements-dev.txt"],
        )
    )
    file_digests: dict[str, str] = {}
    combined_hasher = hashlib.sha256()
    for rel in sorted(tracked_files):
        fpath = repo_root / rel
        if fpath.is_file():
            raw = fpath.read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            file_digests[rel] = digest
            combined_hasher.update(f"{rel}:{digest}\n".encode())
    return {
        "python_version": read_python_pin(repo_root, pol),
        "files": file_digests,
        "tree_sha256": combined_hasher.hexdigest(),
    }


def verify_candidate_manifest(
    repo_root: pathlib.Path,
    expected_manifest: dict[str, Any],
    policy: dict[str, Any] | None = None,
) -> tuple[bool, list[str]]:
    """Verify that the candidate tree to be published matches the validated candidate manifest byte-for-byte."""
    if not isinstance(expected_manifest, dict) or not expected_manifest.get("tree_sha256"):
        return False, ["Missing or invalid expected candidate manifest."]
    actual = compute_candidate_manifest(repo_root, policy)
    errors: list[str] = []
    if actual.get("python_version") != expected_manifest.get("python_version"):
        errors.append(
            f"Candidate .python-version mismatch: expected {expected_manifest.get('python_version')!r}, got {actual.get('python_version')!r}"
        )
    exp_files = expected_manifest.get("files") if isinstance(expected_manifest.get("files"), dict) else {}
    act_files = actual.get("files") if isinstance(actual.get("files"), dict) else {}
    for rel in sorted(set(exp_files.keys()) | set(act_files.keys())):
        if exp_files.get(rel) != act_files.get(rel):
            errors.append(
                f"Candidate file digest mismatch for {rel}: expected {exp_files.get(rel)!r}, got {act_files.get(rel)!r}"
            )
    if actual.get("tree_sha256") != expected_manifest.get("tree_sha256"):
        errors.append(
            f"Candidate tree_sha256 mismatch: expected {expected_manifest.get('tree_sha256')!r}, got {actual.get('tree_sha256')!r}"
        )
    return len(errors) == 0, errors


def record_publication_provenance(
    repo_root: pathlib.Path = REPO_ROOT,
    *,
    workflow: str = ".github/workflows/python_version_bump.yml",
    workflow_name: str = "Python Version Bump",
    run_id: int | str = "",
    run_attempt: int | str = 1,
    source_sha: str = "",
    pr_number: int | str = "",
    published_head_sha: str = "",
    old_version: str = "",
    new_version: str = "",
    update_kind: str = "",
    review_required: bool | str = False,
    auto_merge_eligible: bool | str = False,
    candidate_tree_sha256: str = "",
    candidate_manifest_json: str = "",
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate and emit immutable publication provenance binding the proposer run to the published PR head."""
    pol = policy or load_policy(repo_root)
    eff_head_sha = (published_head_sha or "").strip().lower()
    if not eff_head_sha:
        for ref_cand in ("refs/remotes/origin/chore/python-bump", "HEAD"):
            res = subprocess.run(
                ["git", "rev-parse", ref_cand],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode == 0 and re.fullmatch(r"[0-9a-f]{40}", res.stdout.strip().lower()):
                eff_head_sha = res.stdout.strip().lower()
                break

    if not re.fullmatch(r"[0-9a-f]{40}", eff_head_sha):
        raise ValueError(f"Invalid or missing published_head_sha: {published_head_sha!r}")

    eff_source_sha = (source_sha or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{40}", eff_source_sha):
        raise ValueError(f"Invalid or missing source_sha: {source_sha!r}")

    try:
        eff_pr_number = int(str(pr_number).strip())
        if eff_pr_number <= 0:
            raise ValueError
    except ValueError as exc:
        raise ValueError(f"Invalid or missing pr_number: {pr_number!r}") from exc

    try:
        eff_run_id = int(str(run_id).strip())
        if eff_run_id <= 0:
            raise ValueError
    except ValueError as exc:
        raise ValueError(f"Invalid or missing workflow run_id: {run_id!r}") from exc

    try:
        eff_run_attempt = int(str(run_attempt or 1).strip())
        if eff_run_attempt <= 0:
            raise ValueError
    except ValueError as exc:
        raise ValueError(f"Invalid workflow run_attempt: {run_attempt!r}") from exc

    eff_tree_sha = (candidate_tree_sha256 or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", eff_tree_sha):
        raise ValueError(f"Invalid or missing candidate_tree_sha256: {candidate_tree_sha256!r}")

    manifest_obj: dict[str, Any] = {}
    if candidate_manifest_json:
        raw_m = candidate_manifest_json.strip()
        if raw_m.startswith("@"):
            manifest_obj = json.loads(pathlib.Path(raw_m[1:]).read_text(encoding="utf-8"))
        else:
            manifest_obj = json.loads(raw_m)
        ok_m, m_errs = verify_candidate_manifest(repo_root, manifest_obj, pol)
        if not ok_m:
            raise ValueError(f"Published tree does not match candidate manifest: {'; '.join(m_errs)}")
        if str(manifest_obj.get("tree_sha256") or "").strip().lower() != eff_tree_sha:
            raise ValueError(
                f"candidate_tree_sha256 {eff_tree_sha!r} does not match manifest tree_sha256 {manifest_obj.get('tree_sha256')!r}"
            )
    else:
        manifest_obj = compute_candidate_manifest(repo_root, pol)
        if str(manifest_obj.get("tree_sha256") or "").strip().lower() != eff_tree_sha:
            raise ValueError(
                f"Working tree manifest {manifest_obj.get('tree_sha256')!r} does not match expected {eff_tree_sha!r}"
            )

    rev_bool = (
        review_required
        if isinstance(review_required, bool)
        else str(review_required).strip().lower() == "true"
    )
    elig_bool = (
        auto_merge_eligible
        if isinstance(auto_merge_eligible, bool)
        else str(auto_merge_eligible).strip().lower() == "true"
    )

    record = {
        "workflow": workflow,
        "workflow_name": workflow_name,
        "workflow_run_id": eff_run_id,
        "workflow_run_attempt": eff_run_attempt,
        "source_sha": eff_source_sha,
        "published_pr_number": eff_pr_number,
        "published_head_sha": eff_head_sha,
        "old_version": str(old_version).strip(),
        "new_version": str(new_version).strip(),
        "update_kind": str(update_kind or "patch").strip(),
        "review_required": rev_bool,
        "auto_merge_eligible": elig_bool,
        "candidate_tree_sha256": eff_tree_sha,
        "candidate_manifest": manifest_obj,
        "dry_run": False,
        "select_conclusion": "success",
        "validate_conclusion": "success",
        "publish_conclusion": "success",
    }
    compact_json = json.dumps(record, separators=(",", ":"), sort_keys=True)
    write_github_outputs(
        {
            "pr_number": str(eff_pr_number),
            "published_head_sha": eff_head_sha,
            "source_sha": eff_source_sha,
            "candidate_tree_sha256": eff_tree_sha,
            "publication_provenance_json": compact_json,
        }
    )
    return record


def _distribution_version(dist_name: str) -> str:
    """Return installed distribution version via importlib.metadata."""
    try:
        return str(importlib.metadata.version(dist_name) or "")
    except Exception:
        return ""


def emit_validation_notice(
    repo_root: pathlib.Path = REPO_ROOT,
    *,
    candidate: str,
    source_head: str = "",
    run_id: int | str = "",
    run_attempt: int | str = "",
    interpreter: str = "",
    pip_version: str = "",
    pip_tools_version: str = "",
    policy: dict[str, Any] | None = None,
) -> str:
    """Build and return a bounded `maintenance_common` validation notice string."""
    pol = policy or load_policy(repo_root)
    if parse_exact_version(candidate) is None:
        raise ValueError(f"Invalid candidate version for validation notice: {candidate!r}")
    src_sha = (source_head or os.environ.get("GITHUB_SHA") or "").strip().lower()
    if not maintenance_common.SHA_RE.fullmatch(src_sha):
        raise ValueError(f"Invalid source_head for validation notice: {src_sha!r}")
    eff_interp = interpreter or ".".join(str(p) for p in sys.version_info[:3])
    eff_pip = pip_version or _distribution_version("pip")
    eff_tools = pip_tools_version or _distribution_version("pip-tools")
    pinned_pip, pinned_tools = maintenance_common.compiler_pins(pol)
    if eff_pip != pinned_pip or eff_tools != pinned_tools:
        raise ValueError(
            f"Compiler toolchain mismatch: pip={eff_pip!r} (expected {pinned_pip!r}), "
            f"pip-tools={eff_tools!r} (expected {pinned_tools!r})"
        )
    _mode, _wf, prop_files = maintenance_common.publication_policy(pol)
    digests = maintenance_common.digest_files(repo_root, prop_files)
    rid = int(str(run_id or os.environ.get("GITHUB_RUN_ID") or 0) or 0) or None
    att = int(str(run_attempt or os.environ.get("GITHUB_RUN_ATTEMPT") or 0) or 0) or None
    rec = maintenance_common.build_validation_record(
        source_head=src_sha,
        candidate=candidate,
        interpreter=eff_interp,
        pip_version=eff_pip,
        pip_tools_version=eff_tools,
        digests=digests,
        run_id=rid,
        run_attempt=att,
    )
    rendered = maintenance_common.notice(maintenance_common.VALIDATION_NOTICE, rec)
    if not rendered:
        raise ValueError("Validation notice exceeds maintenance_common.NOTICE_LIMIT")
    return rendered


def emit_publication_notice(
    repo_root: pathlib.Path = REPO_ROOT,
    *,
    pull_number: int | str,
    published_head: str,
    branch: str = "chore/python-bump",
    pr_author: str = "github-actions[bot]",
    commit_identity: str = "",
    run_actor: str = "",
    run_id: int | str = "",
    run_attempt: int | str = "",
    policy: dict[str, Any] | None = None,
) -> str:
    """Build and return a bounded `maintenance_common` publication notice string."""
    pol = policy or load_policy(repo_root)
    head_sha = (published_head or "").strip().lower()
    if not maintenance_common.SHA_RE.fullmatch(head_sha):
        raise ValueError(f"Invalid published_head for publication notice: {published_head!r}")
    pnum = int(str(pull_number).strip())
    if pnum <= 0:
        raise ValueError(f"Invalid pull_number for publication notice: {pull_number!r}")
    _mode, _wf, prop_files = maintenance_common.publication_policy(pol)
    exp_login, _exp_name, _exp_email = maintenance_common.configured_commit_identity(pol)
    eff_commit_id = commit_identity or exp_login or "github-actions[bot]"
    eff_actor = run_actor or os.environ.get("GITHUB_ACTOR") or "github-actions[bot]"
    digests = maintenance_common.digest_files(repo_root, prop_files)
    rid = int(str(run_id or os.environ.get("GITHUB_RUN_ID") or 0) or 0) or None
    att = int(str(run_attempt or os.environ.get("GITHUB_RUN_ATTEMPT") or 0) or 0) or None
    rec = maintenance_common.build_publication_record(
        run_id=rid,
        run_attempt=att,
        pull_number=pnum,
        published_head=head_sha,
        branch=branch,
        digests=digests,
        pr_author=pr_author,
        commit_identity=eff_commit_id,
        run_actor=eff_actor,
    )
    rendered = maintenance_common.notice(maintenance_common.PUBLICATION_NOTICE, rec)
    if not rendered:
        raise ValueError("Publication notice exceeds maintenance_common.NOTICE_LIMIT")
    return rendered


def run_candidate_validation_pipeline(
    repo_root: pathlib.Path,
    candidate_version: str,
    old_version: str,
    *,
    policy: dict[str, Any] | None = None,
    review_required: bool = False,
    require_exact_python: bool = True,
    registry_runner: Any = None,
    lock_compiler: Any = None,
    publisher: Any = None,
) -> dict[str, Any]:
    """Execute the proposer's pre-rewrite + rewrite + post-rewrite validation and gated publication pipeline."""
    pol = policy or load_policy(repo_root)
    invocations: list[str] = []

    def _default_registry(stage: str) -> bool:
        ci_script = repo_root / ".github" / "scripts" / "ci.py"
        cmd = [
            sys.executable,
            str(ci_script),
            "run-all",
            "--phase",
            stage,
            "--expected-python",
            candidate_version,
            "--with-security",
        ]
        if stage == "post-rewrite" and require_exact_python:
            cmd.append("--require-exact-python")
        res = subprocess.run(
            cmd,
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        return res.returncode == 0

    run_reg = registry_runner or _default_registry

    # 1. Pre-rewrite shared validation registry (asserts candidate interpreter when using real registry)
    if registry_runner is None and require_exact_python:
        try:
            assert_target_interpreter(repo_root, candidate_version, allow_same_minor=False)
        except RuntimeError as exc:
            return {
                "ok": False,
                "stage": "assert-interpreter-pre-rewrite",
                "published": False,
                "invocations": invocations,
                "reason": str(exc),
            }
    invocations.append("pre-rewrite-registry")
    if not run_reg("pre-rewrite"):
        return {
            "ok": False,
            "stage": "pre-rewrite-registry",
            "published": False,
            "invocations": invocations,
            "reason": "Pre-rewrite validation registry failed.",
        }

    # 2. Rewrite candidate pin, ruff target, and recompile lockfiles with exact candidate interpreter
    invocations.append("rewrite-candidate")
    changed_files, _ruff_res = apply_python_version(candidate_version, repo_root=repo_root, policy=pol)
    if lock_compiler is not None:
        lock_compiler(repo_root, candidate_version)
    else:
        assert_target_interpreter(
            repo_root,
            candidate_version,
            allow_same_minor=not require_exact_python,
        )
        for target in pol.get("locks", DEFAULT_POLICY["locks"]).get("targets", []):
            compiled = compile_lockfile(
                repo_root,
                target["input_file"],
                target["output_file"],
                target["compile_command"],
                require_exact_python=require_exact_python,
                expected_python=candidate_version if require_exact_python else None,
            )
            (repo_root / target["output_file"]).write_text(compiled, encoding="utf-8")
            if target["output_file"] not in changed_files:
                changed_files.append(target["output_file"])

    diff_ok, unexpected = verify_bump_diff(repo_root, pol)
    if not diff_ok:
        return {
            "ok": False,
            "stage": "verify-bump-diff",
            "published": False,
            "invocations": invocations,
            "reason": f"Unexpected files in candidate diff: {', '.join(unexpected)}",
        }

    # 3. Post-rewrite shared validation registry on the actual candidate tree
    if registry_runner is None and require_exact_python:
        try:
            assert_target_interpreter(repo_root, candidate_version, allow_same_minor=False)
        except RuntimeError as exc:
            return {
                "ok": False,
                "stage": "assert-interpreter-post-rewrite",
                "published": False,
                "invocations": invocations,
                "reason": str(exc),
            }
    invocations.append("post-rewrite-registry")
    if not run_reg("post-rewrite"):
        return {
            "ok": False,
            "stage": "post-rewrite-registry",
            "published": False,
            "invocations": invocations,
            "reason": "Post-rewrite validation registry failed on candidate tree.",
        }

    validated_manifest = compute_candidate_manifest(repo_root, pol)

    # 4. Gated publication: verify candidate tree matches validated manifest before publishing
    published = False
    if publisher is not None:
        ok_manifest, manifest_errors = verify_candidate_manifest(repo_root, validated_manifest, pol)
        if not ok_manifest:
            return {
                "ok": False,
                "stage": "verify-candidate-manifest",
                "published": False,
                "invocations": invocations,
                "reason": "; ".join(manifest_errors),
            }
        invocations.append("publish")
        publisher(repo_root, validated_manifest)
        published = True

    return {
        "ok": True,
        "stage": "complete",
        "published": published,
        "invocations": invocations,
        "manifest": validated_manifest,
        "changed_files": changed_files,
        "review_required": review_required,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd")

    sel_p = sub.add_parser("select", help="Select candidate Python runtime without modifying files")
    sel_p.add_argument("--override", default="", help="Optional manual X.Y.Z override version")

    apply_p = sub.add_parser("apply", help="Apply a selected Python version to .python-version and ruff.toml")
    apply_p.add_argument("--version", required=True, help="Exact X.Y.Z version to apply")
    apply_p.add_argument("--old-version", default="", help="Previous X.Y.Z version for PR body")
    apply_p.add_argument("--review-required", default="", help="Explicit true/false override for review_required")
    apply_p.add_argument("--update-kind", default="", help="Explicit update_kind (patch, minor, manual-override)")

    bump_p = sub.add_parser("bump", help="Select and apply a policy-bounded Python runtime update")
    bump_p.add_argument("--override", default="", help="Optional manual X.Y.Z override version")
    bump_p.add_argument("--dry-run", action="store_true", help="Select only; do not modify files")

    interp_p = sub.add_parser("assert-interpreter", help="Assert running Python matches target version")
    interp_p.add_argument("--expected", default="", help="Expected X.Y.Z version (defaults to .python-version)")
    interp_p.add_argument("--allow-same-minor", action="store_true")

    sub.add_parser(
        "validate-workflows",
        help="Verify .python-version, setup-python pins, SHA pins, and workflow expression rules",
    )
    sub.add_parser("verify-bump-diff", help="Verify only allowlisted runtime files changed")

    sub.add_parser("compute-candidate-manifest", help="Compute SHA-256 manifest of candidate runtime/lock files")
    vcm_p = sub.add_parser("verify-candidate-manifest", help="Verify candidate runtime/lock files match manifest")
    vcm_p.add_argument("--expected-json", required=True, help="Inline JSON or @path to expected manifest")

    rpp_p = sub.add_parser(
        "record-publication-provenance",
        help="Validate and emit immutable publication provenance binding run to published PR head",
    )
    rpp_p.add_argument("--workflow", default=os.environ.get("PROPOSER_WORKFLOW", ".github/workflows/python_version_bump.yml"))
    rpp_p.add_argument("--workflow-name", default=os.environ.get("PROPOSER_WORKFLOW_NAME", "Python Version Bump"))
    rpp_p.add_argument("--run-id", default=os.environ.get("RUN_ID") or os.environ.get("GITHUB_RUN_ID", ""))
    rpp_p.add_argument("--run-attempt", default=os.environ.get("RUN_ATTEMPT") or os.environ.get("GITHUB_RUN_ATTEMPT", "1"))
    rpp_p.add_argument("--source-sha", default=os.environ.get("SOURCE_SHA") or os.environ.get("GITHUB_SHA", ""))
    rpp_p.add_argument("--pr-number", default=os.environ.get("PR_NUMBER", ""))
    rpp_p.add_argument(
        "--published-head-sha",
        default=os.environ.get("PUBLISHED_HEAD_SHA") or os.environ.get("CPR_HEAD_SHA", ""),
    )
    rpp_p.add_argument("--old-version", default=os.environ.get("OLD_VERSION", ""))
    rpp_p.add_argument("--new-version", default=os.environ.get("NEW_VERSION") or os.environ.get("CANDIDATE_VERSION", ""))
    rpp_p.add_argument("--update-kind", default=os.environ.get("UPDATE_KIND", "patch"))
    rpp_p.add_argument("--review-required", default=os.environ.get("REVIEW_REQUIRED", "false"))
    rpp_p.add_argument("--auto-merge-eligible", default=os.environ.get("AUTO_MERGE_ELIGIBLE", "true"))
    rpp_p.add_argument("--candidate-tree-sha256", default=os.environ.get("CANDIDATE_TREE_SHA256", ""))
    rpp_p.add_argument(
        "--candidate-manifest-json",
        default=os.environ.get("CANDIDATE_MANIFEST_JSON") or os.environ.get("EXPECTED_MANIFEST_JSON", ""),
    )

    lc_p = sub.add_parser("lock-compile", help="Compile requirements.in and requirements-dev.in")
    lc_p.add_argument("--require-exact-python", action="store_true", default=True)
    lc_p.add_argument("--allow-same-minor", action="store_true")
    lc_p.add_argument("--expected", default="", help="Expected X.Y.Z candidate version")

    lchk_p = sub.add_parser("lock-check", help="Verify lockfiles are hashed, aligned, and up to date")
    lchk_p.add_argument("--require-exact-python", action="store_true")
    lchk_p.add_argument("--expected-python", default="", help="Expected X.Y.Z running interpreter override")

    am_p = sub.add_parser("evaluate-automerge", help="Evaluate PR auto-merge eligibility (side-effect-free)")
    am_p.add_argument("--pr-json", help="Inline JSON string or @path to PR metadata JSON")
    am_p.add_argument(
        "--require-eligible",
        action="store_true",
        help="Exit non-zero when the PR is not eligible for auto-merge",
    )

    vm_p = sub.add_parser("verify-merge-result", help="Verify GitHub merge API response JSON")
    vm_p.add_argument("--response-json", required=True, help="Inline JSON or @path to merge response")
    vm_p.add_argument("--expected-head-sha", default="", help="Expected head SHA")

    args = parser.parse_args(argv)
    cmd = args.cmd or "bump"

    if cmd == "select":
        sel = run_select(REPO_ROOT, override_version=args.override or None)
        return 1 if sel.status == "failed" else 0

    if cmd == "apply":
        pol = load_policy(REPO_ROOT)
        old_ver = args.old_version or read_python_pin(REPO_ROOT, pol)
        changed_files, ruff_res = apply_python_version(args.version, repo_root=REPO_ROOT, policy=pol)
        parsed = parse_pin_version(args.version)
        old_parsed = parse_pin_version(old_ver)
        is_minor = parsed[1] != old_parsed[1]
        explicit_rev = str(getattr(args, "review_required", "") or "").strip().lower()
        rev_req = is_minor or explicit_rev == "true"
        upd_kind = str(getattr(args, "update_kind", "") or "").strip() or (
            "minor" if is_minor else ("manual-override" if rev_req else "patch")
        )
        sel = SelectionResult(
            current_version=old_ver,
            selected_version=args.version,
            selected_minor=f"{parsed[0]}.{parsed[1]}",
            changed=bool(changed_files),
            status="review-required" if rev_req else "proposed",
            update_kind=upd_kind,
            review_required=rev_req,
            auto_merge_eligible=not rev_req,
            highest_upstream_version=args.version,
            clamped_by_policy=False,
            reason=f"Applied {args.version} (from {old_ver}).",
        )
        body_path = pathlib.Path(os.environ.get("PR_BODY_PATH", "/tmp/python-bump-body.md"))
        body_path.write_text(
            render_bump_pr_body(sel, ruff_res, changed_files, pol),
            encoding="utf-8",
        )
        write_github_outputs(
            {
                "changed": "true" if changed_files else "false",
                "old_version": old_ver,
                "new_version": args.version,
                "review_required": "true" if rev_req else "false",
                "auto_merge_eligible": "true" if not rev_req else "false",
                "ruff_bumped": "true" if ruff_res.changed else "false",
                "ruff_target": ruff_res.target_version,
                "ruff_clamped": "true" if ruff_res.clamped else "false",
                "body_path": str(body_path),
                "changed_files": " ".join(changed_files),
            }
        )
        return 0

    if cmd == "bump":
        return run_bump(
            REPO_ROOT,
            override_version=getattr(args, "override", "") or None,
            dry_run=bool(getattr(args, "dry_run", False)),
        )

    if cmd == "assert-interpreter":
        try:
            running = assert_target_interpreter(
                REPO_ROOT,
                expected_version=args.expected or None,
                allow_same_minor=bool(args.allow_same_minor),
            )
            print(f"OK: running Python interpreter {running} matches target.")
            return 0
        except RuntimeError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1

    if cmd == "validate-workflows":
        errors = validate_workflow_python_pins(REPO_ROOT, load_policy(REPO_ROOT))
        if errors:
            for err in errors:
                print(f"ERROR: {err}", file=sys.stderr)
            return 1
        print(f"OK: workflow Python pins and contracts validated ({read_python_pin(REPO_ROOT)})")
        return 0

    if cmd == "verify-bump-diff":
        ok, unexpected = verify_bump_diff(REPO_ROOT, load_policy(REPO_ROOT))
        if not ok:
            print(
                f"ERROR: unexpected modified files during python bump: {', '.join(unexpected)}",
                file=sys.stderr,
            )
            return 1
        print("OK: only allowlisted runtime bump files changed.")
        return 0

    if cmd == "compute-candidate-manifest":
        manifest_obj = compute_candidate_manifest(REPO_ROOT, load_policy(REPO_ROOT))
        manifest_json = json.dumps(manifest_obj, separators=(",", ":"), sort_keys=True)
        write_github_outputs(
            {
                "candidate_tree_sha256": str(manifest_obj["tree_sha256"]),
                "candidate_manifest_json": manifest_json,
            }
        )
        return 0

    if cmd == "verify-candidate-manifest":
        raw = args.expected_json
        if raw.startswith("@"):
            expected_obj = json.loads(pathlib.Path(raw[1:]).read_text(encoding="utf-8"))
        else:
            expected_obj = json.loads(raw)
        ok, errors = verify_candidate_manifest(REPO_ROOT, expected_obj, load_policy(REPO_ROOT))
        if not ok:
            for err in errors:
                print(f"ERROR: {err}", file=sys.stderr)
            return 1
        print(f"OK: candidate tree matches validated manifest ({expected_obj.get('tree_sha256')}).")
        return 0

    if cmd == "record-publication-provenance":
        try:
            rec = record_publication_provenance(
                REPO_ROOT,
                workflow=args.workflow,
                workflow_name=args.workflow_name,
                run_id=args.run_id,
                run_attempt=args.run_attempt,
                source_sha=args.source_sha,
                pr_number=args.pr_number,
                published_head_sha=args.published_head_sha,
                old_version=args.old_version,
                new_version=args.new_version,
                update_kind=args.update_kind,
                review_required=args.review_required,
                auto_merge_eligible=args.auto_merge_eligible,
                candidate_tree_sha256=args.candidate_tree_sha256,
                candidate_manifest_json=args.candidate_manifest_json,
                policy=load_policy(REPO_ROOT),
            )
            print(json.dumps(rec, indent=2))
            return 0
        except Exception as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1

    if cmd == "lock-compile":
        pol = load_policy(REPO_ROOT)
        req_exact = not bool(getattr(args, "allow_same_minor", False))
        expected_ver = getattr(args, "expected", "") or None
        for target in pol["locks"]["targets"]:
            content = compile_lockfile(
                REPO_ROOT,
                target["input_file"],
                target["output_file"],
                target["compile_command"],
                require_exact_python=req_exact,
                expected_python=expected_ver,
            )
            (REPO_ROOT / target["output_file"]).write_text(content, encoding="utf-8")
            print(f"Compiled {target['input_file']} -> {target['output_file']}")
        return 0

    if cmd == "lock-check":
        ok, errors = verify_lockfiles(
            REPO_ROOT,
            load_policy(REPO_ROOT),
            recompile=True,
            require_exact_python=bool(args.require_exact_python),
            expected_python_override=getattr(args, "expected_python", "") or None,
        )
        if not ok:
            for err in errors:
                print(f"ERROR: {err}", file=sys.stderr)
            return 1
        print("OK: requirements.txt and requirements-dev.txt match inputs and hash rules.")
        return 0

    if cmd == "evaluate-automerge":
        raw = args.pr_json or ""
        if raw.startswith("@"):
            pr_data = json.loads(pathlib.Path(raw[1:]).read_text(encoding="utf-8"))
        elif raw:
            pr_data = json.loads(raw)
        else:
            pr_data = json.load(sys.stdin)
        decision = evaluate_automerge(pr_data, load_policy(REPO_ROOT))
        print(json.dumps(asdict(decision), indent=2))
        write_github_outputs(
            {
                "eligible": "true" if decision.eligible else "false",
                "lane": decision.lane or "",
                "classification": decision.classification,
                "merge_method": decision.merge_method,
                "validated_head_sha": decision.validated_head_sha,
                "reason": decision.reason,
            }
        )
        if args.require_eligible and not decision.eligible:
            return 1
        return 0

    if cmd == "verify-merge-result":
        raw = args.response_json
        if raw.startswith("@"):
            resp_data = json.loads(pathlib.Path(raw[1:]).read_text(encoding="utf-8"))
        else:
            resp_data = json.loads(raw)
        ok, msg = verify_merge_response(resp_data, expected_head_sha=args.expected_head_sha)
        print(msg)
        return 0 if ok else 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
