"""Offline tests for the unified maintenance system, runtime pinning, and auto-merge lanes."""

from __future__ import annotations

import contextlib
import datetime
import importlib.util
import io
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "maintenance"


def _load_script(name: str):
    path = ROOT / ".github" / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.removesuffix(".py"), path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


maintenance = _load_script("maintenance.py")
python_version_bump = _load_script("python_version_bump.py")
ci_script = _load_script("ci.py")


def _full_ci_check_runs(
    head_sha: str = "a" * 40,
    *,
    workflow_name: str = "CI — compile + offline tests",
    workflow_path: str = ".github/workflows/ci.yml",
    app_slug: str = "github-actions",
    run_id: int = 1001,
    run_attempt: int = 1,
    overrides: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    names = [
        "Verify (syntax, workflow contract & offline tests)",
        "Dependency lockfile consistency",
        "Ruff lint",
        "Workflow lint (actionlint)",
        "Workflow security audit (zizmor)",
        "Dependency CVE audit (pip-audit, advisory)",
        "maintenance-ci",
    ]
    overrides = overrides or {}
    runs: list[dict[str, Any]] = []
    for idx, name in enumerate(names, start=1):
        default_step_name = (
            "Run pip-audit against runtime & dev lockfiles"
            if "pip-audit" in name
            else "Main step"
        )
        entry: dict[str, Any] = {
            "id": run_id * 100 + idx,
            "name": name,
            "head_sha": head_sha,
            "status": "COMPLETED",
            "conclusion": "SUCCESS",
            "details_url": f"https://github.com/uesu/Game-Express/actions/runs/{run_id}/job/{run_id * 100 + idx}",
            "html_url": f"https://github.com/uesu/Game-Express/actions/runs/{run_id}/job/{run_id * 100 + idx}",
            "app": {"slug": app_slug},
            "app_slug": app_slug,
            "workflow_id": 42,
            "workflow_name": workflow_name,
            "workflow_path": workflow_path,
            "run_id": run_id,
            "run_attempt": run_attempt,
            "steps": [
                {"name": default_step_name, "status": "completed", "conclusion": "success"}
            ],
            "output_title": "",
            "output_summary": "",
            "output_text": "",
            "annotations": [],
        }
        if name in overrides:
            entry.update(overrides[name])
        runs.append(entry)
    return runs


def _full_producer_evidence(
    head_sha: str = "a" * 40,
    *,
    run_id: int = 1001,
    run_attempt: int = 1,
    workflow_path: str = ".github/workflows/ci.yml",
) -> dict[str, dict[str, Any]]:
    names = [
        "Verify (syntax, workflow contract & offline tests)",
        "Dependency lockfile consistency",
        "Ruff lint",
        "Workflow lint (actionlint)",
        "Workflow security audit (zizmor)",
        "Dependency CVE audit (pip-audit, advisory)",
        "maintenance-ci",
    ]
    out: dict[str, dict[str, Any]] = {}
    for idx, name in enumerate(names, start=1):
        cid = run_id * 100 + idx
        out[name] = {
            "workflow": workflow_path,
            "job": name,
            "check_run_id": cid,
            "run_id": run_id,
            "run_record_id": run_id,
            "job_id": cid,
            "job_record_id": cid,
            "job_run_id": run_id,
            "job_check_run_url": f"https://api.github.com/repos/uesu/Game-Express/check-runs/{cid}",
            "run_attempt": run_attempt,
            "job_run_attempt": run_attempt,
            "head_sha": head_sha,
            "job_head_sha": head_sha,
            "job_status": "completed",
            "job_conclusion": "success",
            "run_status": "completed",
            "run_conclusion": "success",
        }
    return out


def _valid_published_commit(
    head_sha: str = "a" * 40,
    *,
    login: str = "github-actions[bot]",
    committer_login: str | None = None,
    name: str = "github-actions[bot]",
    email: str = "41898282+github-actions[bot]@users.noreply.github.com",
) -> dict[str, Any]:
    eff_committer = committer_login if committer_login is not None else login
    return {
        "sha": head_sha,
        "author": {"login": login},
        "committer": {"login": eff_committer},
        "commit": {
            "author": {"name": name, "email": email},
            "committer": {"name": name, "email": email},
            "message": "chore(python): bump pinned Python from 3.14.8 to 3.14.9",
        },
    }


def _valid_publication_evidence(
    head_sha: str = "a" * 40,
    *,
    pr_number: int | None = 50,
    pr_author: str = "uesu",
    source_sha: str = "b" * 40,
    candidate_version: str = "3.14.9",
    run_id: int = 555,
    run_attempt: int = 1,
    published_commit: dict[str, Any] | None = None,
) -> dict[str, Any]:
    digests = {
        ".python-version": "1" * 64,
        "ruff.toml": "2" * 64,
        "requirements.txt": "3" * 64,
        "requirements-dev.txt": "4" * 64,
    }
    commit_obj = (
        published_commit
        if published_commit is not None
        else _valid_published_commit(head_sha)
    )
    return {
        "repository": "uesu/Game-Express",
        "candidate_version": candidate_version,
        "expected_commit_identity": "github-actions[bot]",
        "expected_commit_name": "github-actions[bot]",
        "expected_commit_email": "41898282+github-actions[bot]@users.noreply.github.com",
        "proposal_digests": dict(digests),
        "published_commit": commit_obj,
        "proposer_run": {
            "id": run_id,
            "workflow_id": 77,
            "path": ".github/workflows/python_version_bump.yml",
            "status": "completed",
            "conclusion": "success",
            "run_attempt": run_attempt,
            "head_sha": source_sha,
            "actor": {"login": "github-actions[bot]"},
            "repository": {"full_name": "uesu/Game-Express"},
            "head_repository": {"full_name": "uesu/Game-Express"},
        },
        "proposer_attempt": {
            "id": run_id,
            "run_attempt": run_attempt,
            "status": "completed",
            "conclusion": "success",
            "head_sha": source_sha,
        },
        "validation_record": {
            "run_id": run_id,
            "run_attempt": run_attempt,
            "source_head": source_sha,
            "candidate_version": candidate_version,
            "interpreter": candidate_version,
            "pip": "26.1.1",
            "pip_tools": "7.5.3",
            "digests": dict(digests),
        },
        "publication_record": {
            "run_id": run_id,
            "run_attempt": run_attempt,
            "pull_number": pr_number,
            "published_head": head_sha,
            "branch": "chore/python-bump",
            "pr_author": pr_author,
            "run_actor": "github-actions[bot]",
            "commit_identity": "github-actions[bot]",
            "digests": dict(digests),
        },
    }


def _clean_security_scan(head_sha: str = "a" * 40) -> dict[str, Any]:
    return {
        "present": True,
        "check_name": "Dependency CVE audit (pip-audit, advisory)",
        "head_sha": head_sha,
        "app_slug": "github-actions",
        "workflow_name": "CI — compile + offline tests",
        "workflow_path": ".github/workflows/ci.yml",
        "status": "clean",
        "conclusion": "SUCCESS",
        "step_conclusion": "success",
        "vulnerability_count": 0,
        "annotations_count": 0,
        "findings": [],
        "summary": "No known vulnerabilities found",
    }


def _trusted_provenance(lane: str, head_sha: str = "a" * 40) -> dict[str, Any]:
    if lane == "python_bump":
        return {
            "verified": True,
            "lane": "python_bump",
            "publisher": "uesu",
            "publisher_type": "User",
            "source": "python-version-bump-workflow",
            "workflow": ".github/workflows/python_version_bump.yml",
            "workflow_name": "Python Version Bump",
            "workflow_run_id": 555,
            "workflow_run_attempt": 1,
            "workflow_conclusion": "success",
            "select_conclusion": "success",
            "validate_conclusion": "success",
            "publish_conclusion": "success",
            "dry_run": False,
            "published_head_sha": head_sha,
            "source_sha": "b" * 40,
            "old_version": "3.14.8",
            "new_version": "3.14.9",
            "update_kind": "patch",
            "review_required": False,
            "auto_merge_eligible": True,
            "candidate_tree_sha256": "c" * 64,
            "manifest_verified": True,
            "head_ref": "chore/python-bump",
            "head_sha": head_sha,
        }
    return {
        "verified": True,
        "lane": lane,
        "publisher": "dependabot[bot]",
        "publisher_type": "Bot",
        "source": "github-dependabot",
        "head_ref": "dependabot/pip/aiohttp-3.14.6",
        "head_sha": head_sha,
    }


def test_python_version_file_and_policy_match() -> None:
    pin = (ROOT / ".python-version").read_text(encoding="utf-8").strip()
    assert re.fullmatch(r"3\.\d+\.\d+", pin), f"Expected exact X.Y.Z pin, got {pin!r}"
    policy = maintenance.load_policy(ROOT)
    parsed = maintenance.parse_exact_version(pin)
    assert parsed is not None
    major, minor, _patch = parsed
    assert major == policy["python"]["supported_major"] == 3
    assert policy["python"]["min_minor"] <= minor <= policy["python"]["max_validated_minor"]


def test_workflows_use_python_version_file_and_frozen_hash_installs() -> None:
    wf_dir = ROOT / ".github" / "workflows"
    workflows = sorted(wf_dir.glob("*.yml"))
    assert {w.name for w in workflows} == {
        "ci.yml",
        "maintenance_merge.yml",
        "monitor.yml",
        "python_version_bump.yml",
    }

    for wf in workflows:
        data = yaml.safe_load(wf.read_text(encoding="utf-8"))
        for job_name, job in (data.get("jobs") or {}).items():
            job_env = job.get("env") or {}
            for env_key, env_val in job_env.items():
                assert not re.search(r"\$\{\{[^}]*\b(runner|steps|job)\.", str(env_val)), (
                    f"{wf.name}:{job_name} env.{env_key} must not reference runner/steps/job context"
                )
            for step in job.get("steps") or []:
                uses = step.get("uses", "")
                if uses.startswith("actions/setup-python@"):
                    with_block = step.get("with") or {}
                    assert with_block.get("check-latest") is False, (
                        f"{wf.name}:{job_name} setup-python must set check-latest: false"
                    )
                    if wf.name == "python_version_bump.yml" and job_name in ("validate", "publish"):
                        assert (
                            with_block.get("python-version")
                            == "${{ needs.select.outputs.new_version }}"
                        )
                    else:
                        assert with_block.get("python-version-file") == ".python-version", (
                            f"{wf.name}:{job_name} must use python-version-file: .python-version"
                        )
                        assert "python-version" not in with_block, (
                            f"{wf.name}:{job_name} must not set floating python-version"
                        )
                run_cmd = step.get("run", "")
                if "pip install" in run_cmd:
                    assert "--require-hashes" in run_cmd, (
                        f"{wf.name}:{job_name} pip install must use --require-hashes"
                    )
                    assert "--only-binary" in run_cmd, (
                        f"{wf.name}:{job_name} pip install must use --only-binary"
                    )
                assert not re.search(r'(?<!")\$\{[A-Za-z0-9_]+:\+[^}]+\}', run_cmd), (
                    f"{wf.name}:{job_name} has unquoted ${{VAR:+...}} expansion"
                )
                assert "$PING_FLAG" not in run_cmd, (
                    f"{wf.name}:{job_name} has unquoted $PING_FLAG"
                )


def test_workflow_validator_catches_job_env_runner_and_unquoted_shell() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        shutil.copytree(ROOT / ".github", tmp_root / ".github")
        shutil.copy2(ROOT / ".python-version", tmp_root / ".python-version")
        mon_path = tmp_root / ".github" / "workflows" / "monitor.yml"
        orig = mon_path.read_text(encoding="utf-8")

        bad = orig.replace(
            "      GAME_ARG: ${{ inputs.game != 'all' && inputs.game || '' }}\n",
            "      GAME_ARG: ${{ inputs.game != 'all' && inputs.game || '' }}\n"
            "      BAD_REPORT: ${{ runner.temp }}/report.json\n",
        ) + "\n      - name: Bad shell\n        run: echo ${GAME_ARG:+--game \"$GAME_ARG\"}\n"
        mon_path.write_text(bad, encoding="utf-8")
        errs = maintenance.validate_workflow_python_pins(tmp_root, maintenance.load_policy(tmp_root))
        assert any("BAD_REPORT" in e for e in errs), errs
        assert any("SC2086" in e for e in errs), errs


def test_lockfiles_have_hashes_and_match_policy() -> None:
    policy = maintenance.load_policy(ROOT)
    assert maintenance.validate_workflow_python_pins(ROOT, policy) == []
    ok, errors = maintenance.verify_lockfiles(ROOT, policy, recompile=True)
    assert ok, errors
    for rel in ("requirements.txt", "requirements-dev.txt"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "--hash=sha256:" in text, f"{rel} must contain sha256 hashes"
        assert "pip-compile" in text, f"{rel} must preserve pip-compile header"

    sample = (
        "#\n"
        "# This file is autogenerated by pip-compile with Python 3.11\n"
        "# by the following command:\n"
        "#\n"
        "#    pip-compile --output-file=/tmp/x requirements.in\n"
    )
    norm = maintenance.normalize_lock_text(
        sample,
        "python -m piptools compile --generate-hashes --output-file=requirements.txt requirements.in",
    )
    assert "with Python 3.11" in norm
    assert "with Python 3.14" not in norm


def test_assert_target_interpreter_enforces_exact_match() -> None:
    running = platform.python_version()
    assert maintenance.assert_target_interpreter(ROOT, expected_version=running) == running
    try:
        maintenance.assert_target_interpreter(ROOT, expected_version="3.99.0")
    except RuntimeError as exc:
        assert "3.99.0" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError on mismatched interpreter")


def test_select_target_python_patch_soak_and_minor_bounds() -> None:
    manifest = json.loads(
        (FIXTURES / "actions_versions_manifest.json").read_text(encoding="utf-8")
    )
    release_dates = json.loads(
        (FIXTURES / "endoflife_python.json").read_text(encoding="utf-8")
    )
    policy = maintenance.load_policy(ROOT)

    sel_patch = maintenance.select_target_python(
        manifest, "3.14.8", policy, release_dates=release_dates
    )
    assert sel_patch.selected_version == "3.14.9"
    assert sel_patch.changed is True
    assert sel_patch.status == "proposed"
    assert sel_patch.update_kind == "patch"
    assert sel_patch.review_required is False
    assert sel_patch.auto_merge_eligible is True

    policy_315 = json.loads(json.dumps(policy))
    policy_315["python"]["max_validated_minor"] = 15
    policy_315["python"]["allow_minor_upgrades"] = True
    policy_315["python"]["minor_soak_days"] = 30

    sel_no_dates = maintenance.select_target_python(
        manifest, "3.14.9", policy_315, release_dates={}
    )
    assert sel_no_dates.changed is False
    assert sel_no_dates.status == "deferred"
    assert "release-date-unavailable" in sel_no_dates.reason
    assert sel_no_dates.deferred_candidate == "3.15.0"

    now_10d = datetime.datetime(2026, 10, 11, tzinfo=datetime.timezone.utc)
    sel_unsoaked = maintenance.select_target_python(
        manifest, "3.14.9", policy_315, release_dates=release_dates, now=now_10d
    )
    assert sel_unsoaked.changed is False
    assert sel_unsoaked.status == "deferred"
    assert "soak-period-incomplete" in sel_unsoaked.reason
    assert sel_unsoaked.deferred_candidate == "3.15.0"

    now_45d = datetime.datetime(2026, 11, 15, tzinfo=datetime.timezone.utc)
    sel_soaked = maintenance.select_target_python(
        manifest, "3.14.9", policy_315, release_dates=release_dates, now=now_45d
    )
    assert sel_soaked.changed is True
    assert sel_soaked.selected_version == "3.15.0"
    assert sel_soaked.status == "review-required"
    assert sel_soaked.update_kind == "minor"
    assert sel_soaked.review_required is True
    assert sel_soaked.auto_merge_eligible is False

    manifest_316 = [
        m for m in manifest if not str(m.get("version", "")).startswith("3.15.")
    ] + [
        {
            "version": "3.16.0",
            "stable": True,
            "files": [
                {
                    "platform": "linux",
                    "platform_version": "24.04",
                    "arch": "x64",
                    "filename": "python-3.16.0-linux-24.04-x64.tar.gz",
                }
            ],
        }
    ]
    policy_316 = json.loads(json.dumps(policy_315))
    policy_316["python"]["max_validated_minor"] = 16
    sel_skip = maintenance.select_target_python(
        manifest_316, "3.14.9", policy_316, release_dates={"3.16.0": "2026-01-01"}, now=now_45d
    )
    assert sel_skip.changed is False
    assert sel_skip.status == "deferred"
    assert "skipped-minor-series" in sel_skip.reason

    sel_ov_ok = maintenance.select_target_python(
        manifest, "3.14.8", policy, override_version="3.14.9"
    )
    assert sel_ov_ok.changed is True
    assert sel_ov_ok.status == "review-required"
    assert sel_ov_ok.update_kind == "override"
    assert sel_ov_ok.review_required is True
    assert sel_ov_ok.auto_merge_eligible is False

    sel_ov_down = maintenance.select_target_python(
        manifest, "3.14.8", policy, override_version="3.13.9"
    )
    assert sel_ov_down.changed is False
    assert sel_ov_down.status == "failed"
    assert "downgrade" in sel_ov_down.reason

    sel_ov_skip = maintenance.select_target_python(
        manifest_316, "3.14.8", policy_316, override_version="3.16.0"
    )
    assert sel_ov_skip.changed is False
    assert sel_ov_skip.status == "failed"
    assert "skipped-minor-series" in sel_ov_skip.reason

    target, clamped, _reason = maintenance.resolve_ruff_target(
        "3.15", policy=policy_315, probe_binary=False
    )
    assert target == "py314"
    assert clamped is True


def test_select_target_python_rejects_missing_runner_tarball() -> None:
    policy = maintenance.load_policy(ROOT)
    manifest = [
        {
            "version": "3.14.9",
            "stable": True,
            "files": [
                {
                    "platform": "darwin",
                    "platform_version": "14",
                    "arch": "arm64",
                    "filename": "python-3.14.9-darwin-arm64.tar.gz",
                }
            ],
        },
        {
            "version": "3.14.8",
            "stable": True,
            "files": [
                {
                    "platform": "linux",
                    "platform_version": "24.04",
                    "arch": "x64",
                    "filename": "python-3.14.8-linux-24.04-x64.tar.gz",
                }
            ],
        },
    ]
    sel = maintenance.select_target_python(manifest, "3.14.8", policy)
    assert sel.selected_version == "3.14.8"
    assert sel.changed is False
    assert sel.status == "up-to-date"


def test_apply_python_version_works_in_full_and_docless_clone() -> None:
    manifest = json.loads(
        (FIXTURES / "actions_versions_manifest.json").read_text(encoding="utf-8")
    )
    release_dates = json.loads(
        (FIXTURES / "endoflife_python.json").read_text(encoding="utf-8")
    )
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        shutil.copytree(ROOT / ".github", tmp_root / ".github")
        shutil.copy2(ROOT / ".python-version", tmp_root / ".python-version")
        shutil.copy2(ROOT / "ruff.toml", tmp_root / "ruff.toml")
        shutil.copy2(ROOT / "requirements.txt", tmp_root / "requirements.txt")
        shutil.copy2(ROOT / "requirements-dev.txt", tmp_root / "requirements-dev.txt")

        rc = maintenance.run_bump(
            tmp_root,
            manifest=manifest,
            policy=maintenance.load_policy(tmp_root),
            release_dates=release_dates,
        )
        assert rc == 0
        assert (tmp_root / ".python-version").read_text(encoding="utf-8") == "3.14.9\n"
        assert (
            maintenance.validate_workflow_python_pins(
                tmp_root,
                maintenance.load_policy(tmp_root),
                require_all_workflows=False,
            )
            == []
        )


def test_ci_gate_and_automerge_separation() -> None:
    ci_data = yaml.safe_load(
        (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    )
    assert "automerge" not in ci_data["jobs"], "ci.yml must not embed automerge"
    assert "maintenance-ci" in ci_data["jobs"], "ci.yml must expose maintenance-ci gate"
    gate_needs = set(ci_data["jobs"]["maintenance-ci"]["needs"])
    assert gate_needs == {"test", "lock-check", "ruff", "actionlint", "zizmor", "pip-audit"}
    assert ci_data["jobs"]["pip-audit"]["continue-on-error"] is True

    merge_raw = (ROOT / ".github" / "workflows" / "maintenance_merge.yml").read_text(encoding="utf-8")
    merge_data = yaml.safe_load(merge_raw)
    on_block = merge_data.get("on") or merge_data.get(True)
    assert "pull_request_target" in on_block
    assert "workflow_run" in on_block
    assert "pull_request_review" in on_block
    assert "workflow_dispatch" in on_block
    assert on_block["pull_request_target"]["branches"] == ["main"]

    assert 'checks["maintenance-ci"] = "SUCCESS"' not in merge_raw
    assert 'pr.mergeable === false ? "CONFLICTING" : "MERGEABLE"' not in merge_raw
    assert "verify-merge-result" in merge_raw
    assert "provenance" in merge_raw
    assert "security_scan" in merge_raw

    bump_raw = (ROOT / ".github" / "workflows" / "python_version_bump.yml").read_text(encoding="utf-8")
    bump_data = yaml.safe_load(bump_raw)
    assert set(bump_data["jobs"].keys()) == {"select", "validate", "publish", "report"}
    assert bump_data["jobs"]["select"]["permissions"] == {"contents": "read"}
    assert bump_data["jobs"]["validate"]["permissions"]["contents"] == "read"
    assert "BUMP_PAT" not in yaml.dump(bump_data["jobs"]["validate"])
    assert "secrets.BUMP_PAT || github.token" not in bump_raw
    assert "updatechore" not in bump_raw
    assert "compute-candidate-manifest" in bump_raw
    assert "verify-candidate-manifest" in bump_raw


def test_g1_complete_diff_classification_additions_deletions_metadata_and_hashes() -> None:
    policy = maintenance.load_policy(ROOT)

    def _base_snapshot(**extra: Any) -> dict[str, Any]:
        snap: dict[str, Any] = {
            "base_repo": "uesu/Game-Express",
            "head_repo": "uesu/Game-Express",
            "base_ref": "main",
            "head_ref": "dependabot/pip/aiohttp-3.14.6",
            "head_sha": "a" * 40,
            "author": "dependabot[bot]",
            "state": "OPEN",
            "is_draft": False,
            "mergeable": "MERGEABLE",
            "mergeable_state": "clean",
            "changed_files": ["requirements.txt", "requirements-dev.txt"],
            "file_diffs": {
                "requirements.txt": "-aiohttp==3.14.5 \\\n+aiohttp==3.14.6 \\\n --hash=sha256:1234",
                "requirements-dev.txt": "-aiohttp==3.14.5 \\\n+aiohttp==3.14.6 \\\n --hash=sha256:1234",
            },
            "check_runs": _full_ci_check_runs("a" * 40),
            "producer_evidence": _full_producer_evidence("a" * 40),
            "security_scan": _clean_security_scan("a" * 40),
            "provenance": _trusted_provenance("dependabot_pip"),
            "vars": {"AUTO_MERGE_DEPENDABOT": "yes", "AUTO_MERGE_PYTHON_BUMP": "no"},
        }
        snap.update(extra)
        return snap

    # 1. Safe patch + new package addition (+evil==99.0.0) -> rejected
    dec_addition = maintenance.evaluate_automerge(
        _base_snapshot(
            file_diffs={
                "requirements.txt": (
                    "-aiohttp==3.14.5 \\\n"
                    "+aiohttp==3.14.6 \\\n"
                    "+evil==99.0.0 \\\n"
                    " --hash=sha256:1234"
                ),
                "requirements-dev.txt": "-aiohttp==3.14.5 \\\n+aiohttp==3.14.6 \\\n --hash=sha256:1234",
            }
        ),
        policy,
    )
    assert dec_addition.eligible is False
    assert "Added new dependency" in dec_addition.reason and "evil" in dec_addition.reason
    assert any(u["name"] == "evil" and u["kind"] == "added" for u in dec_addition.updates)

    # 2. Safe patch + package deletion (-defusedxml==0.7.1) -> rejected
    dec_deletion = maintenance.evaluate_automerge(
        _base_snapshot(
            file_diffs={
                "requirements.txt": (
                    "-aiohttp==3.14.5 \\\n"
                    "+aiohttp==3.14.6 \\\n"
                    "-defusedxml==0.7.1 \\\n"
                    " --hash=sha256:1234"
                ),
                "requirements-dev.txt": "-aiohttp==3.14.5 \\\n+aiohttp==3.14.6 \\\n --hash=sha256:1234",
            }
        ),
        policy,
    )
    assert dec_deletion.eligible is False
    assert "Removed dependency" in dec_deletion.reason and "defusedxml" in dec_deletion.reason
    assert any(u["name"] == "defusedxml" and u["kind"] == "removed" for u in dec_deletion.updates)

    # 3. Conflicting metadata hiding a major upgrade in file_diffs -> rejected
    dec_conflict_meta = maintenance.evaluate_automerge(
        _base_snapshot(
            dependency_updates=[{"name": "aiohttp", "from": "3.14.5", "to": "3.14.6"}],
            file_diffs={
                "requirements.txt": "-aiohttp==3.14.5 \\\n+aiohttp==4.0.0 \\\n --hash=sha256:1234",
                "requirements-dev.txt": "-aiohttp==3.14.5 \\\n+aiohttp==4.0.0 \\\n --hash=sha256:1234",
            },
        ),
        policy,
    )
    assert dec_conflict_meta.eligible is False
    assert (
        "disagrees with authoritative diff content" in dec_conflict_meta.reason
        or "Major version upgrade" in dec_conflict_meta.reason
    )

    # 4. Opposite file/member orders across lockfiles -> allowed when all transitions are safe patch updates
    dec_opposite_order = maintenance.evaluate_automerge(
        _base_snapshot(
            file_diffs={
                "requirements.txt": (
                    "-aiohttp==3.14.5 \\\n+aiohttp==3.14.6 \\\n"
                    "-yarl==1.23.0 \\\n+yarl==1.23.1 \\\n"
                ),
                "requirements-dev.txt": (
                    "-yarl==1.23.0 \\\n+yarl==1.23.1 \\\n"
                    "-aiohttp==3.14.5 \\\n+aiohttp==3.14.6 \\\n"
                ),
            }
        ),
        policy,
    )
    assert dec_opposite_order.eligible is True, dec_opposite_order.reason

    # 5. Hash-only mutation without version transition -> rejected
    dec_hash_only = maintenance.evaluate_automerge(
        _base_snapshot(
            file_diffs={
                "requirements.txt": (
                    " aiohttp==3.14.5 \\\n"
                    "-    --hash=sha256:1111111111111111111111111111111111111111111111111111111111111111\n"
                    "+    --hash=sha256:2222222222222222222222222222222222222222222222222222222222222222\n"
                ),
                "requirements-dev.txt": (
                    " aiohttp==3.14.5 \\\n"
                    "-    --hash=sha256:1111111111111111111111111111111111111111111111111111111111111111\n"
                    "+    --hash=sha256:2222222222222222222222222222222222222222222222222222222222222222\n"
                ),
            }
        ),
        policy,
    )
    assert dec_hash_only.eligible is False
    assert "hash-only mutation" in dec_hash_only.reason

    # 6. Extras, markers, source/index directives, and unparseable lines -> rejected
    for bad_patch in (
        "-aiohttp==3.14.5\n+aiohttp[speedups]==3.14.6\n",
        "-aiohttp==3.14.5\n+aiohttp==3.14.6 ; python_version >= '3.14'\n",
        "--extra-index-url https://evil.example/simple\n-aiohttp==3.14.5\n+aiohttp==3.14.6\n",
        "+--find-links https://evil.example/wheels\n-aiohttp==3.14.5\n+aiohttp==3.14.6\n",
        "+git+https://github.com/evil/pkg.git@main\n-aiohttp==3.14.5\n+aiohttp==3.14.6\n",
    ):
        dec_bad_line = maintenance.evaluate_automerge(
            _base_snapshot(
                changed_files=["requirements.txt"],
                file_diffs={"requirements.txt": bad_patch},
            ),
            policy,
        )
        assert dec_bad_line.eligible is False, f"Expected rejection for patch: {bad_patch!r}"

    # 7. Truncated or missing file_diffs -> rejected
    dec_truncated = maintenance.evaluate_automerge(
        _base_snapshot(diff_truncated=True),
        policy,
    )
    assert dec_truncated.eligible is False
    assert "missing or truncated" in dec_truncated.reason


def test_automerge_lane_eligibility_and_g2_g3_hardening() -> None:
    policy = maintenance.load_policy(ROOT)

    # 1. Allowed Dependabot pip patch update with full G2 check set, provenance, and security evidence
    dec1 = maintenance.evaluate_automerge(
        {
            "base_repo": "uesu/Game-Express",
            "head_repo": "uesu/Game-Express",
            "base_ref": "main",
            "head_ref": "dependabot/pip/aiohttp-3.14.6",
            "head_sha": "a" * 40,
            "author": "dependabot[bot]",
            "state": "OPEN",
            "is_draft": False,
            "mergeable": "MERGEABLE",
            "mergeable_state": "clean",
            "changed_files": ["requirements.txt", "requirements-dev.txt"],
            "file_diffs": {
                "requirements.txt": "-aiohttp==3.14.5 \\\n+aiohttp==3.14.6 \\\n --hash=sha256:1234",
                "requirements-dev.txt": "-aiohttp==3.14.5 \\\n+aiohttp==3.14.6 \\\n --hash=sha256:1234",
            },
            "check_runs": _full_ci_check_runs("a" * 40),
            "producer_evidence": _full_producer_evidence("a" * 40),
            "security_scan": _clean_security_scan("a" * 40),
            "provenance": _trusted_provenance("dependabot_pip"),
            "vars": {"AUTO_MERGE_DEPENDABOT": "yes", "AUTO_MERGE_PYTHON_BUMP": "no"},
        },
        policy,
    )
    assert dec1.eligible is True, dec1.reason
    assert dec1.lane == "dependabot_pip"
    assert dec1.validated_head_sha == "a" * 40

    # 2. G2: Lone maintenance-ci check without full mandatory check set -> rejected
    dec_lone_gate = maintenance.evaluate_automerge(
        {
            "base_repo": "uesu/Game-Express",
            "head_repo": "uesu/Game-Express",
            "base_ref": "main",
            "head_ref": "dependabot/pip/aiohttp-3.14.6",
            "head_sha": "a" * 40,
            "author": "dependabot[bot]",
            "state": "OPEN",
            "is_draft": False,
            "mergeable": "MERGEABLE",
            "changed_files": ["requirements.txt"],
            "file_diffs": {"requirements.txt": "-aiohttp==3.14.5\n+aiohttp==3.14.6\n"},
            "check_runs": [
                {
                    "id": 100107,
                    "name": "maintenance-ci",
                    "head_sha": "a" * 40,
                    "status": "COMPLETED",
                    "conclusion": "SUCCESS",
                    "app_slug": "github-actions",
                    "workflow_name": "CI — compile + offline tests",
                    "workflow_path": ".github/workflows/ci.yml",
                    "run_id": 1001,
                    "run_attempt": 1,
                }
            ],
            "security_scan": _clean_security_scan("a" * 40),
            "provenance": _trusted_provenance("dependabot_pip"),
        },
        policy,
    )
    assert dec_lone_gate.eligible is False
    assert "incomplete mandatory CI check set" in dec_lone_gate.reason

    # 3. G2: Zero checks reported -> deferred (never manufactured as SUCCESS)
    dec_zero_checks = maintenance.evaluate_automerge(
        {
            "base_repo": "uesu/Game-Express",
            "head_repo": "uesu/Game-Express",
            "base_ref": "main",
            "head_ref": "dependabot/pip/aiohttp-3.14.6",
            "head_sha": "a" * 40,
            "author": "dependabot[bot]",
            "state": "OPEN",
            "is_draft": False,
            "mergeable": "MERGEABLE",
            "changed_files": ["requirements.txt"],
            "file_diffs": {"requirements.txt": "-aiohttp==3.14.5\n+aiohttp==3.14.6\n"},
            "check_runs": [],
            "checks": {},
            "security_scan": _clean_security_scan("a" * 40),
            "provenance": _trusted_provenance("dependabot_pip"),
        },
        policy,
    )
    assert dec_zero_checks.eligible is False
    assert dec_zero_checks.classification == "deferred"
    assert "zero checks" in dec_zero_checks.reason

    # 4. G2: Unknown/null mergeability -> deferred (never defaulted to MERGEABLE)
    dec_unknown_mergeable = maintenance.evaluate_automerge(
        {
            "base_repo": "uesu/Game-Express",
            "head_repo": "uesu/Game-Express",
            "base_ref": "main",
            "head_ref": "dependabot/pip/aiohttp-3.14.6",
            "head_sha": "a" * 40,
            "author": "dependabot[bot]",
            "state": "OPEN",
            "is_draft": False,
            "mergeable": None,
            "changed_files": ["requirements.txt"],
            "file_diffs": {"requirements.txt": "-aiohttp==3.14.5\n+aiohttp==3.14.6\n"},
            "check_runs": _full_ci_check_runs("a" * 40),
            "security_scan": _clean_security_scan("a" * 40),
            "provenance": _trusted_provenance("dependabot_pip"),
        },
        policy,
    )
    assert dec_unknown_mergeable.eligible is False
    assert dec_unknown_mergeable.classification == "deferred"

    # 5. G2: Stale-head check run, untrusted check app, or untrusted workflow path -> rejected
    dec_stale_check = maintenance.evaluate_automerge(
        {
            "base_repo": "uesu/Game-Express",
            "head_repo": "uesu/Game-Express",
            "base_ref": "main",
            "head_ref": "dependabot/pip/aiohttp-3.14.6",
            "head_sha": "a" * 40,
            "author": "dependabot[bot]",
            "state": "OPEN",
            "is_draft": False,
            "mergeable": "MERGEABLE",
            "changed_files": ["requirements.txt"],
            "file_diffs": {"requirements.txt": "-aiohttp==3.14.5\n+aiohttp==3.14.6\n"},
            "check_runs": _full_ci_check_runs("b" * 40),
            "security_scan": _clean_security_scan("a" * 40),
            "provenance": _trusted_provenance("dependabot_pip"),
        },
        policy,
    )
    assert dec_stale_check.eligible is False
    assert "stale head" in dec_stale_check.reason

    dec_untrusted_app = maintenance.evaluate_automerge(
        {
            "base_repo": "uesu/Game-Express",
            "head_repo": "uesu/Game-Express",
            "base_ref": "main",
            "head_ref": "dependabot/pip/aiohttp-3.14.6",
            "head_sha": "a" * 40,
            "author": "dependabot[bot]",
            "state": "OPEN",
            "is_draft": False,
            "mergeable": "MERGEABLE",
            "changed_files": ["requirements.txt"],
            "file_diffs": {"requirements.txt": "-aiohttp==3.14.5\n+aiohttp==3.14.6\n"},
            "check_runs": _full_ci_check_runs("a" * 40, app_slug="spoofed-ci-app"),
            "security_scan": _clean_security_scan("a" * 40),
            "provenance": _trusted_provenance("dependabot_pip"),
        },
        policy,
    )
    assert dec_untrusted_app.eligible is False
    assert "untrusted app" in dec_untrusted_app.reason

    dec_untrusted_wf = maintenance.evaluate_automerge(
        {
            "base_repo": "uesu/Game-Express",
            "head_repo": "uesu/Game-Express",
            "base_ref": "main",
            "head_ref": "dependabot/pip/aiohttp-3.14.6",
            "head_sha": "a" * 40,
            "author": "dependabot[bot]",
            "state": "OPEN",
            "is_draft": False,
            "mergeable": "MERGEABLE",
            "changed_files": ["requirements.txt"],
            "file_diffs": {"requirements.txt": "-aiohttp==3.14.5\n+aiohttp==3.14.6\n"},
            "check_runs": _full_ci_check_runs(
                "a" * 40,
                workflow_name="Spoofed Workflow",
                workflow_path=".github/workflows/spoofed.yml",
            ),
            "security_scan": _clean_security_scan("a" * 40),
            "provenance": _trusted_provenance("dependabot_pip"),
        },
        policy,
    )
    assert dec_untrusted_wf.eligible is False
    assert "untrusted producing workflow provenance" in dec_untrusted_wf.reason

    # 6. G2: Rerun ordering: older run_attempt=1 succeeded, newer run_attempt=2 failed -> rejected
    rerun_checks = _full_ci_check_runs("a" * 40, run_id=1001, run_attempt=1)
    rerun_checks.append(
        {
            "id": 999999,
            "name": "Ruff lint",
            "head_sha": "a" * 40,
            "status": "COMPLETED",
            "conclusion": "FAILURE",
            "app_slug": "github-actions",
            "workflow_name": "CI — compile + offline tests",
            "workflow_path": ".github/workflows/ci.yml",
            "run_id": 1001,
            "run_attempt": 2,
        }
    )
    dec_rerun_fail = maintenance.evaluate_automerge(
        {
            "base_repo": "uesu/Game-Express",
            "head_repo": "uesu/Game-Express",
            "base_ref": "main",
            "head_ref": "dependabot/pip/aiohttp-3.14.6",
            "head_sha": "a" * 40,
            "author": "dependabot[bot]",
            "state": "OPEN",
            "is_draft": False,
            "mergeable": "MERGEABLE",
            "changed_files": ["requirements.txt"],
            "file_diffs": {"requirements.txt": "-aiohttp==3.14.5\n+aiohttp==3.14.6\n"},
            "check_runs": rerun_checks,
            "security_scan": _clean_security_scan("a" * 40),
            "provenance": _trusted_provenance("dependabot_pip"),
        },
        policy,
    )
    assert dec_rerun_fail.eligible is False
    assert "Ruff lint" in dec_rerun_fail.reason

    # 7. G2: Security scan advisory wrapper exits SUCCESS while inner audit step reports vulnerability -> rejected
    vuln_checks = _full_ci_check_runs(
        "a" * 40,
        overrides={
            "Dependency CVE audit (pip-audit, advisory)": {
                "conclusion": "SUCCESS",
                "steps": [
                    {
                        "name": "Run pip-audit against runtime & dev lockfiles",
                        "status": "completed",
                        "conclusion": "failure",
                    }
                ],
                "output_summary": "Found 1 known vulnerability in 1 package (GHSA-xxxx-yyyy-zzzz)",
            }
        },
    )
    dec_vuln_wrapped = maintenance.evaluate_automerge(
        {
            "base_repo": "uesu/Game-Express",
            "head_repo": "uesu/Game-Express",
            "base_ref": "main",
            "head_ref": "dependabot/pip/aiohttp-3.14.6",
            "head_sha": "a" * 40,
            "author": "dependabot[bot]",
            "state": "OPEN",
            "is_draft": False,
            "mergeable": "MERGEABLE",
            "changed_files": ["requirements.txt"],
            "file_diffs": {"requirements.txt": "-aiohttp==3.14.5\n+aiohttp==3.14.6\n"},
            "check_runs": vuln_checks,
            "producer_evidence": _full_producer_evidence("a" * 40),
            "security_scan": {
                "check_name": "Dependency CVE audit (pip-audit, advisory)",
                "head_sha": "a" * 40,
                "app_slug": "github-actions",
                "workflow_name": "CI — compile + offline tests",
                "workflow_path": ".github/workflows/ci.yml",
                "status": "clean",
                "conclusion": "SUCCESS",
                "step_conclusion": "failure",
                "vulnerability_count": 1,
                "summary": "Found 1 known vulnerability in 1 package (GHSA-xxxx-yyyy-zzzz)",
            },
            "provenance": _trusted_provenance("dependabot_pip"),
        },
        policy,
    )
    assert dec_vuln_wrapped.eligible is False
    assert "advisory wrapper" in dec_vuln_wrapped.reason.lower()

    # 7b. G2: Both outer check and inner step conclude SUCCESS, but scan output reports a vulnerability -> rejected
    vuln_text_checks = _full_ci_check_runs(
        "a" * 40,
        overrides={
            "Dependency CVE audit (pip-audit, advisory)": {
                "conclusion": "SUCCESS",
                "output_summary": "Found 1 known vulnerability in 1 package (GHSA-xxxx-yyyy-zzzz)",
            }
        },
    )
    dec_vuln_text = maintenance.evaluate_automerge(
        {
            "base_repo": "uesu/Game-Express",
            "head_repo": "uesu/Game-Express",
            "base_ref": "main",
            "head_ref": "dependabot/pip/aiohttp-3.14.6",
            "head_sha": "a" * 40,
            "author": "dependabot[bot]",
            "state": "OPEN",
            "is_draft": False,
            "mergeable": "MERGEABLE",
            "changed_files": ["requirements.txt"],
            "file_diffs": {"requirements.txt": "-aiohttp==3.14.5\n+aiohttp==3.14.6\n"},
            "check_runs": vuln_text_checks,
            "producer_evidence": _full_producer_evidence("a" * 40),
            "security_scan": _clean_security_scan("a" * 40),
            "provenance": _trusted_provenance("dependabot_pip"),
        },
        policy,
    )
    assert dec_vuln_text.eligible is False
    assert "GHSA-xxxx-yyyy-zzzz" in dec_vuln_text.reason

    # 8. G2: Missing security_scan evidence or missing provenance -> rejected
    dec_no_sec = maintenance.evaluate_automerge(
        {
            "base_repo": "uesu/Game-Express",
            "head_repo": "uesu/Game-Express",
            "base_ref": "main",
            "head_ref": "dependabot/pip/aiohttp-3.14.6",
            "head_sha": "a" * 40,
            "author": "dependabot[bot]",
            "state": "OPEN",
            "is_draft": False,
            "mergeable": "MERGEABLE",
            "changed_files": ["requirements.txt"],
            "file_diffs": {"requirements.txt": "-aiohttp==3.14.5\n+aiohttp==3.14.6\n"},
            "check_runs": _full_ci_check_runs("a" * 40),
            "producer_evidence": _full_producer_evidence("a" * 40),
            "provenance": _trusted_provenance("dependabot_pip"),
        },
        policy,
    )
    assert dec_no_sec.eligible is False
    assert "security_scan evidence is missing" in dec_no_sec.reason

    dec_no_prov = maintenance.evaluate_automerge(
        {
            "base_repo": "uesu/Game-Express",
            "head_repo": "uesu/Game-Express",
            "base_ref": "main",
            "head_ref": "dependabot/pip/aiohttp-3.14.6",
            "head_sha": "a" * 40,
            "author": "dependabot[bot]",
            "state": "OPEN",
            "is_draft": False,
            "mergeable": "MERGEABLE",
            "changed_files": ["requirements.txt"],
            "file_diffs": {"requirements.txt": "-aiohttp==3.14.5\n+aiohttp==3.14.6\n"},
            "check_runs": _full_ci_check_runs("a" * 40),
            "security_scan": _clean_security_scan("a" * 40),
        },
        policy,
    )
    assert dec_no_prov.eligible is False
    assert "missing publisher/proposal provenance" in dec_no_prov.reason

    # 9. Independent opt-in variables per lane
    dec_py_disabled = maintenance.evaluate_automerge(
        {
            "base_repo": "uesu/Game-Express",
            "head_repo": "uesu/Game-Express",
            "base_ref": "main",
            "head_ref": "chore/python-bump",
            "head_sha": "a" * 40,
            "author": "uesu",
            "state": "OPEN",
            "is_draft": False,
            "mergeable": "MERGEABLE",
            "changed_files": [".python-version", "ruff.toml"],
            "file_diffs": {
                ".python-version": "-3.14.8\n+3.14.9\n",
                "ruff.toml": '# target = "py314"\n',
            },
            "python_update": {"from": "3.14.8", "to": "3.14.9"},
            "check_runs": _full_ci_check_runs("a" * 40),
            "security_scan": _clean_security_scan("a" * 40),
            "provenance": _trusted_provenance("python_bump"),
            "vars": {"AUTO_MERGE_DEPENDABOT": "yes", "AUTO_MERGE_PYTHON_BUMP": "no"},
        },
        policy,
    )
    assert dec_py_disabled.eligible is False
    assert "AUTO_MERGE_PYTHON_BUMP" in dec_py_disabled.reason

    # 10. Version risk rejection (major, 0.x minor, prerelease, downgrade)
    for bad_from, bad_to in (
        ("1.2.3", "2.0.0"),
        ("0.16.0", "0.17.0"),
        ("1.0.0", "1.0.1rc1"),
        ("1.2.0", "1.1.9"),
    ):
        dec_risk = maintenance.evaluate_automerge(
            {
                "base_repo": "uesu/Game-Express",
                "head_repo": "uesu/Game-Express",
                "base_ref": "main",
                "head_ref": "dependabot/pip/pkg",
                "head_sha": "a" * 40,
                "author": "dependabot[bot]",
                "state": "OPEN",
                "is_draft": False,
                "mergeable": "MERGEABLE",
                "changed_files": ["requirements.txt"],
                "file_diffs": {"requirements.txt": f"-pkg=={bad_from}\n+pkg=={bad_to}\n"},
                "check_runs": _full_ci_check_runs("a" * 40),
                "security_scan": _clean_security_scan("a" * 40),
                "provenance": _trusted_provenance("dependabot_pip"),
            },
            policy,
        )
        assert dec_risk.eligible is False, f"Expected {bad_from}->{bad_to} to be rejected"

    # 11. Review state resolution (CHANGES_REQUESTED followed by COMMENTED still blocks!)
    dec_review_block = maintenance.evaluate_automerge(
        {
            "base_repo": "uesu/Game-Express",
            "head_repo": "uesu/Game-Express",
            "base_ref": "main",
            "head_ref": "dependabot/pip/aiohttp-3.14.6",
            "head_sha": "a" * 40,
            "author": "dependabot[bot]",
            "state": "OPEN",
            "is_draft": False,
            "mergeable": "MERGEABLE",
            "changed_files": ["requirements.txt"],
            "file_diffs": {"requirements.txt": "-aiohttp==3.14.5\n+aiohttp==3.14.6\n"},
            "reviews": [
                {"author": "alice", "state": "CHANGES_REQUESTED"},
                {"author": "alice", "state": "COMMENTED"},
            ],
            "check_runs": _full_ci_check_runs("a" * 40),
            "security_scan": _clean_security_scan("a" * 40),
            "provenance": _trusted_provenance("dependabot_pip"),
        },
        policy,
    )
    assert dec_review_block.eligible is False
    assert "CHANGES_REQUESTED" in dec_review_block.reason

    # 12. Allowed chore/python-bump patch update vs rejected minor update
    dec_py_patch = maintenance.evaluate_automerge(
        {
            "pr_number": 50,
            "base_repo": "uesu/Game-Express",
            "head_repo": "uesu/Game-Express",
            "base_ref": "main",
            "head_ref": "chore/python-bump",
            "head_sha": "a" * 40,
            "author": "uesu",
            "state": "OPEN",
            "is_draft": False,
            "mergeable": "MERGEABLE",
            "changed_files": [".python-version", "ruff.toml"],
            "file_diffs": {
                ".python-version": "-3.14.8\n+3.14.9\n",
                "ruff.toml": '# target = "py314"\n',
            },
            "python_update": {"from": "3.14.8", "to": "3.14.9"},
            "check_runs": _full_ci_check_runs("a" * 40),
            "producer_evidence": _full_producer_evidence("a" * 40),
            "published_commit": _valid_published_commit("a" * 40),
            "publication_evidence": _valid_publication_evidence("a" * 40, pr_number=50, pr_author="uesu"),
            "security_scan": _clean_security_scan("a" * 40),
            "provenance": {**_trusted_provenance("python_bump"), "published_pr_number": 50},
            "vars": {"AUTO_MERGE_PYTHON_BUMP": "yes"},
        },
        policy,
    )
    assert dec_py_patch.eligible is True, dec_py_patch.reason
    assert dec_py_patch.lane == "python_bump"

    dec_py_minor = maintenance.evaluate_automerge(
        {
            "base_repo": "uesu/Game-Express",
            "head_repo": "uesu/Game-Express",
            "base_ref": "main",
            "head_ref": "chore/python-bump",
            "head_sha": "a" * 40,
            "author": "uesu",
            "state": "OPEN",
            "is_draft": False,
            "mergeable": "MERGEABLE",
            "changed_files": [".python-version", "ruff.toml"],
            "file_diffs": {
                ".python-version": "-3.14.9\n+3.15.0\n",
                "ruff.toml": '# target = "py314"\n',
            },
            "python_update": {"from": "3.14.9", "to": "3.15.0"},
            "check_runs": _full_ci_check_runs("a" * 40),
            "security_scan": _clean_security_scan("a" * 40),
            "provenance": _trusted_provenance("python_bump"),
            "vars": {"AUTO_MERGE_PYTHON_BUMP": "yes"},
        },
        policy,
    )
    assert dec_py_minor.eligible is False
    assert dec_py_minor.classification == "review-required"

    # 13. Head drift on pre-merge refresh and merge response verification
    dec_drift = maintenance.evaluate_automerge(
        {
            "base_repo": "uesu/Game-Express",
            "head_repo": "uesu/Game-Express",
            "base_ref": "main",
            "head_ref": "chore/python-bump",
            "head_sha": "a" * 40,
            "refreshed_head_sha": "c" * 40,
            "author": "uesu",
            "state": "OPEN",
            "is_draft": False,
            "mergeable": "MERGEABLE",
            "changed_files": [".python-version"],
            "file_diffs": {".python-version": "-3.14.8\n+3.14.9\n"},
            "python_update": {"from": "3.14.8", "to": "3.14.9"},
            "check_runs": _full_ci_check_runs("a" * 40),
            "security_scan": _clean_security_scan("a" * 40),
            "provenance": _trusted_provenance("python_bump"),
            "vars": {"AUTO_MERGE_PYTHON_BUMP": "yes"},
        },
        policy,
    )
    assert dec_drift.eligible is False
    assert "head SHA changed" in dec_drift.reason

    ok_merge, _ = maintenance.verify_merge_response(
        {"merged": True, "sha": "f" * 40, "message": "Pull Request successfully merged"},
        expected_head_sha="a" * 40,
    )
    assert ok_merge is True
    bad_merge, _ = maintenance.verify_merge_response(
        {"merged": False, "message": "Base branch was modified"},
        expected_head_sha="a" * 40,
    )
    assert bad_merge is False


def test_g3_candidate_validation_pipeline_and_manifest_equivalence() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        shutil.copytree(ROOT / ".github", tmp_root / ".github")
        shutil.copy2(ROOT / ".python-version", tmp_root / ".python-version")
        shutil.copy2(ROOT / "ruff.toml", tmp_root / "ruff.toml")
        shutil.copy2(ROOT / "requirements.in", tmp_root / "requirements.in")
        shutil.copy2(ROOT / "requirements-dev.in", tmp_root / "requirements-dev.in")
        shutil.copy2(ROOT / "requirements.txt", tmp_root / "requirements.txt")
        shutil.copy2(ROOT / "requirements-dev.txt", tmp_root / "requirements-dev.txt")
        subprocess.run(["git", "init", "-q"], cwd=tmp_root, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_root, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_root, check=True)
        subprocess.run(["git", "add", "."], cwd=tmp_root, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_root, check=True)

        policy = maintenance.load_policy(tmp_root)
        called_stages: list[str] = []
        published: list[str] = []

        def _passing_registry(stage: str) -> bool:
            called_stages.append(stage)
            return True

        def _noop_lock_compiler(_root: Path, _ver: str) -> None:
            pass

        def _publisher(_root: Path, manifest_obj: dict[str, Any]) -> None:
            published.append(str(manifest_obj["python_version"]))

        res = maintenance.run_candidate_validation_pipeline(
            tmp_root,
            "3.14.9",
            "3.14.8",
            policy=policy,
            registry_runner=_passing_registry,
            lock_compiler=_noop_lock_compiler,
            publisher=_publisher,
        )
        assert res["ok"] is True, res
        assert res["published"] is True
        assert called_stages == ["pre-rewrite", "post-rewrite"]
        assert res["invocations"] == [
            "pre-rewrite-registry",
            "rewrite-candidate",
            "post-rewrite-registry",
            "publish",
        ]
        assert published == ["3.14.9"]
        cand_manifest = res["manifest"]
        assert cand_manifest["python_version"] == "3.14.9"

        # Verify published tree matches validated candidate manifest before publication
        v_ok, v_errs = maintenance.verify_candidate_manifest(
            tmp_root, cand_manifest, policy=policy
        )
        assert v_ok is True, v_errs

        # Tampering with a regenerated lockfile or pin in publish job must block publication
        (tmp_root / "requirements.txt").write_text("# tampered\n", encoding="utf-8")
        v_tampered, v_tampered_errs = maintenance.verify_candidate_manifest(
            tmp_root, cand_manifest, policy=policy
        )
        assert v_tampered is False
        assert any("mismatch" in e for e in v_tampered_errs)

        # Candidate rejection in post-rewrite validation must NEVER invoke publisher
        (tmp_root / ".python-version").write_text("3.14.8\n", encoding="utf-8")
        shutil.copy2(ROOT / "requirements.txt", tmp_root / "requirements.txt")
        published_after_reject: list[str] = []

        def _failing_post_registry(stage: str) -> bool:
            return stage != "post-rewrite"

        res_rej = maintenance.run_candidate_validation_pipeline(
            tmp_root,
            "3.14.9",
            "3.14.8",
            policy=policy,
            registry_runner=_failing_post_registry,
            lock_compiler=_noop_lock_compiler,
            publisher=lambda _r, m: published_after_reject.append(str(m["python_version"])),
        )
        assert res_rej["ok"] is False
        assert res_rej["published"] is False
        assert "publish" not in res_rej["invocations"]
        assert published_after_reject == []


def test_ci_adapter_gate_logic_and_registered_tests() -> None:
    policy = maintenance.load_policy(ROOT)
    registered = set(policy["ci"]["registered_tests"])
    discovered = {f"tests/{p.name}" for p in (ROOT / "tests").glob("test_*.py")}
    assert registered == discovered, f"Mismatch between registered and discovered tests: {registered ^ discovered}"

    rc = subprocess.run(
        [
            sys.executable,
            str(ROOT / ".github" / "scripts" / "ci.py"),
            "gate",
            "--results-json",
            '{"verify":"success","lock-check":"success","ruff":"success","actionlint":"success","zizmor":"success"}',
            "--advisory-json",
            '{"pip-audit":"failure"}',
        ],
        check=False,
        capture_output=True,
        text=True,
    ).returncode
    assert rc == 0

    rc_fail = subprocess.run(
        [
            sys.executable,
            str(ROOT / ".github" / "scripts" / "ci.py"),
            "gate",
            "--results-json",
            '{"verify":"success","lock-check":"failure","ruff":"success","actionlint":"success","zizmor":"success"}',
            "--advisory-json",
            '{"pip-audit":"success"}',
        ],
        check=False,
        capture_output=True,
        text=True,
    ).returncode
    assert rc_fail == 1


def test_g1_live_maintenance_merge_adapter_proposer_provenance_binding() -> None:
    """Execute the actual JavaScript adapter from `.github/workflows/maintenance_merge.yml` via `node`
    against mocked GitHub API responses and the real `maintenance.py` subprocess."""
    node_bin = shutil.which("node")
    assert node_bin, "node is required to execute the live maintenance_merge.yml github-script adapter"

    merge_wf = yaml.safe_load(
        (ROOT / ".github" / "workflows" / "maintenance_merge.yml").read_text(encoding="utf-8")
    )
    adapter_script = merge_wf["jobs"]["automerge"]["steps"][0]["with"]["script"]

    # Compute the real candidate manifest for a 3.14.8 -> 3.14.9 bump tree
    with tempfile.TemporaryDirectory() as tmp_cand:
        cand_root = Path(tmp_cand)
        shutil.copytree(ROOT / ".github", cand_root / ".github")
        for fname in (".python-version", "ruff.toml", "requirements.txt", "requirements-dev.txt"):
            shutil.copy2(ROOT / fname, cand_root / fname)
        (cand_root / ".python-version").write_text("3.14.9\n", encoding="utf-8")
        real_manifest = maintenance.compute_candidate_manifest(cand_root)
        real_tree_sha = real_manifest["tree_sha256"]
        cand_contents = {
            fname: (cand_root / fname).read_text(encoding="utf-8")
            for fname in (".python-version", "ruff.toml", "requirements.txt", "requirements-dev.txt")
        }
        valid_val_msg = maintenance.emit_validation_notice(
            cand_root,
            candidate="3.14.9",
            source_head="b" * 40,
            run_id=501,
            run_attempt=1,
            interpreter="3.14.9",
            pip_version="26.1.1",
            pip_tools_version="7.5.3",
        )
        valid_pub_msg = maintenance.emit_publication_notice(
            cand_root,
            pull_number=50,
            published_head="a" * 40,
            branch="chore/python-bump",
            pr_author="uesu",
            run_actor="github-actions[bot]",
            run_id=501,
            run_attempt=1,
        )

    def _run_live_adapter(scenario: dict[str, Any]) -> dict[str, Any]:
        with tempfile.TemporaryDirectory() as run_tmp:
            scenario_path = Path(run_tmp) / "scenario.json"
            scenario_path.write_text(json.dumps(scenario), encoding="utf-8")
            harness_path = Path(run_tmp) / "run_adapter.js"
            harness_code = """
const fs = require("fs");
const path = require("path");
const scenario = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const repoRoot = scenario.repoRoot;
let pullGetCount = 0;

function activeScenario() {
  if (pullGetCount >= 2 && scenario.refreshOverride) {
    return Object.assign({}, scenario, scenario.refreshOverride);
  }
  return scenario;
}

const summaryChunks = [];
const failedReasons = [];
const mergedCalls = [];

const core = {
  summary: {
    addRaw(txt) { summaryChunks.push(txt); return this; },
    async write() { return; }
  },
  setFailed(msg) { failedReasons.push(String(msg)); }
};

const context = {
  repo: { owner: "uesu", repo: "Game-Express" },
  actor: scenario.actor || "uesu",
  payload: { pull_request: { number: scenario.pr.number } }
};

const github = {
  async paginate(fn, args) {
    const res = await fn(args);
    if (Array.isArray(res)) return res;
    if (res && Array.isArray(res.data)) return res.data;
    if (res && res.data && Array.isArray(res.data.check_runs)) return res.data.check_runs;
    if (res && res.data && Array.isArray(res.data.workflow_runs)) return res.data.workflow_runs;
    if (res && res.data && Array.isArray(res.data.jobs)) return res.data.jobs;
    return [];
  },
  rest: {
    repos: {
      async getContent({ path: relPath, ref }) {
        if (ref === "heads/main") {
          const full = path.join(repoRoot, relPath);
          const raw = fs.readFileSync(full);
          return { data: { content: raw.toString("base64"), encoding: "base64" } };
        }
        const cur = activeScenario();
        const headFiles = cur.headFiles;
        if (headFiles && Object.prototype.hasOwnProperty.call(headFiles, relPath)) {
          const raw = Buffer.from(headFiles[relPath], "utf8");
          return { data: { content: raw.toString("base64"), encoding: "base64" } };
        }
        const err = new Error("Missing file: " + relPath + " at " + ref);
        err.status = 404;
        throw err;
      },
      async getCommit({ ref }) {
        const cur = activeScenario();
        if (cur.getCommitError) {
          const err = new Error("getCommit failed");
          err.status = Number(cur.getCommitError);
          throw err;
        }
        if (cur.publishedCommit !== undefined) {
          return cur.rawEnvelope ? cur.publishedCommit : { data: cur.publishedCommit };
        }
        const found = (cur.commits || []).find((c) => c && c.sha === ref) || null;
        if (!found) {
          const err = new Error("Commit not found");
          err.status = 404;
          throw err;
        }
        return cur.rawEnvelope ? found : { data: found };
      },
      async getCombinedStatusForRef() {
        return { data: { total_count: 0, state: "success", statuses: [] } };
      }
    },
    pulls: {
      async get() {
        pullGetCount += 1;
        const cur = activeScenario();
        return cur.rawEnvelope ? cur.pr : { data: cur.pr };
      },
      async listFiles() { return { data: activeScenario().files }; },
      async listCommits() { return { data: activeScenario().commits }; },
      async listReviews() { return { data: activeScenario().reviews || [] }; },
      async merge(params) {
        mergedCalls.push(params);
        return { data: { merged: true, sha: "f".repeat(40), message: "Pull Request successfully merged" } };
      }
    },
    checks: {
      async listForRef() {
        const cur = activeScenario();
        return { data: { total_count: cur.checkRuns.length, check_runs: cur.checkRuns } };
      },
      async listAnnotations({ check_run_id }) {
        const cur = activeScenario();
        const anns = (cur.annotationsByCheckRunId && cur.annotationsByCheckRunId[String(check_run_id)]) || [];
        return { data: anns };
      }
    },
    actions: {
      async listWorkflowRunsForRepo() {
        return { data: { workflow_runs: activeScenario().ciWorkflowRuns } };
      },
      async listWorkflowRuns() {
        const cur = activeScenario();
        return cur.rawEnvelope
          ? { workflow_runs: cur.proposerRuns }
          : { data: { workflow_runs: cur.proposerRuns } };
      },
      async getWorkflowRunAttempt({ run_id, attempt_number }) {
        const cur = activeScenario();
        if (cur.attemptsByRunId && cur.attemptsByRunId[String(run_id)]) {
          const att = cur.attemptsByRunId[String(run_id)];
          return cur.rawEnvelope ? att : { data: att };
        }
        const run = (cur.proposerRuns || []).find((r) => r && Number(r.id) === Number(run_id));
        if (!run) {
          const err = new Error("Run attempt not found");
          err.status = 404;
          throw err;
        }
        const att = {
          id: run.id,
          run_attempt: Number(run.run_attempt || attempt_number || 1),
          status: run.status || "completed",
          conclusion: run.conclusion || "success",
          head_sha: run.head_sha || "",
        };
        return cur.rawEnvelope ? att : { data: att };
      },
      async listJobsForWorkflowRun({ run_id }) {
        const cur = activeScenario();
        const jobs = (cur.jobsByRunId && cur.jobsByRunId[String(run_id)]) || [];
        return { data: { jobs } };
      },
      async getJobForWorkflowRun({ job_id }) {
        const cur = activeScenario();
        for (const jobs of Object.values(cur.jobsByRunId || {})) {
          const match = (jobs || []).find((j) => j && Number(j.id) === Number(job_id));
          if (match) return cur.rawEnvelope ? match : { data: match };
        }
        const err = new Error("Job not found: " + job_id);
        err.status = 404;
        throw err;
      },
      async getWorkflowRun({ run_id }) {
        const cur = activeScenario();
        const match = (cur.ciWorkflowRuns || []).find((r) => r && Number(r.id) === Number(run_id));
        if (match) return cur.rawEnvelope ? match : { data: match };
        const err = new Error("Workflow run not found: " + run_id);
        err.status = 404;
        throw err;
      }
    }
  }
};

(async () => {
""" + adapter_script + """
  fs.writeFileSync(process.argv[3], JSON.stringify({
    summary: summaryChunks.join(""),
    failedReasons,
    mergedCalls
  }), "utf8");
})().catch((err) => {
  fs.writeFileSync(process.argv[3], JSON.stringify({
    error: String(err && err.stack ? err.stack : err),
    summary: summaryChunks.join(""),
    failedReasons,
    mergedCalls
  }), "utf8");
  process.exit(1);
});
"""
            harness_path.write_text(harness_code, encoding="utf-8")
            out_path = Path(run_tmp) / "out.json"
            env = {
                "PATH": f"{Path(sys.executable).parent}:{ROOT / '.venv' / 'bin'}:/usr/local/bin:/usr/bin:/bin",
                "RUNNER_TEMP": run_tmp,
                "AUTO_MERGE_PYTHON_BUMP": "yes",
                "AUTO_MERGE_DEPENDABOT": "yes",
            }
            res = subprocess.run(
                [node_bin, str(harness_path), str(scenario_path), str(out_path)],
                cwd=str(ROOT),
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            assert res.returncode == 0, f"Adapter crashed: {res.stderr}\n{res.stdout}"
            return json.loads(out_path.read_text(encoding="utf-8"))

    head_sha = "a" * 40
    base_sha = "b" * 40
    ci_checks = _full_ci_check_runs(head_sha, run_id=1001, run_attempt=1)

    def _make_ci_jobs(
        sha: str = head_sha,
        *,
        run_id: int = 1001,
        run_attempt: int = 1,
        check_run_id_override: int | None = None,
    ) -> list[dict[str, Any]]:
        checks_for_sha = _full_ci_check_runs(sha, run_id=run_id, run_attempt=run_attempt)
        return [
            {
                "id": c["id"],
                "run_id": run_id,
                "run_attempt": run_attempt,
                "head_sha": sha,
                "name": c["name"],
                "status": "completed",
                "conclusion": "success",
                "check_run_url": f"https://api.github.com/repos/uesu/Game-Express/check-runs/{check_run_id_override or c['id']}",
                "steps": c["steps"],
            }
            for c in checks_for_sha
        ]

    def _make_proposer_jobs(
        *,
        pr_num: str = "50",
        pub_head: str = head_sha,
        src_sha: str = base_sha,
        old_v: str = "3.14.8",
        new_v: str = "3.14.9",
        kind: str = "patch",
        review: str = "false",
        eligible: str = "true",
        tree: str = real_tree_sha,
        dry_run: str = "false",
        publish_conclusion: str = "success",
    ) -> list[dict[str, Any]]:
        step_name = (
            f"PROVENANCE pr={pr_num} head={pub_head} source={src_sha} "
            f"old={old_v} new={new_v} kind={kind} review={review} "
            f"eligible={eligible} tree={tree} dry_run={dry_run}"
        )
        return [
            {"id": 50101, "name": "Select policy-bounded Python candidate", "conclusion": "success", "steps": []},
            {"id": 50102, "name": "Validate candidate Python runtime & locks (secret-free)", "conclusion": "success", "steps": []},
            {"id": 50103, "name": "Publish chore/python-bump Pull Request", "conclusion": publish_conclusion, "steps": []},
            {
                "id": 50104,
                "name": "Record runtime proposer summary",
                "conclusion": "success",
                "steps": [{"name": step_name, "status": "completed", "conclusion": "success"}],
            },
        ]

    base_pr_body = (
        "| Field | Value |\n| --- | --- |\n"
        "| Update classification | `patch` |\n"
        "| Review required | `false` |\n"
        "| Auto-merge eligible | `true` |\n"
    )

    def _make_scenario(
        *,
        pr_num: int = 50,
        pr_head_sha: str = head_sha,
        pr_body: str = base_pr_body,
        proposer_runs: list[dict[str, Any]] | None = None,
        proposer_jobs: dict[str, list[dict[str, Any]]] | None = None,
        head_files: dict[str, str] | None = None,
        published_commit: dict[str, Any] | None = None,
        get_commit_error: int | None = None,
        check_runs_override: list[dict[str, Any]] | None = None,
        ci_workflow_runs_override: list[dict[str, Any]] | None = None,
        ci_jobs_override: list[dict[str, Any]] | None = None,
        refresh_override: dict[str, Any] | None = None,
        raw_envelope: bool = False,
    ) -> dict[str, Any]:
        default_commit = _valid_published_commit(pr_head_sha)
        scen: dict[str, Any] = {
            "repoRoot": str(ROOT),
            "rawEnvelope": raw_envelope,
            "headFiles": head_files if head_files is not None else cand_contents,
            "pr": {
                "number": pr_num,
                "title": "chore(python): bump pinned Python from 3.14.8 to 3.14.9",
                "state": "open",
                "draft": False,
                "mergeable": True,
                "mergeable_state": "clean",
                "changed_files": 1,
                "body": pr_body,
                "user": {"login": "uesu", "type": "User"},
                "base": {"ref": "main", "sha": base_sha, "repo": {"full_name": "uesu/Game-Express"}},
                "head": {
                    "ref": "chore/python-bump",
                    "sha": pr_head_sha,
                    "repo": {"full_name": "uesu/Game-Express", "fork": False},
                },
                "labels": [],
            },
            "files": [{"filename": ".python-version", "patch": "-3.14.8\n+3.14.9\n"}],
            "commits": [default_commit],
            "publishedCommit": published_commit if published_commit is not None else default_commit,
            "checkRuns": (
                check_runs_override
                if check_runs_override is not None
                else (ci_checks if pr_head_sha == head_sha else _full_ci_check_runs(pr_head_sha, run_id=1001, run_attempt=1))
            ),
            "ciWorkflowRuns": (
                ci_workflow_runs_override
                if ci_workflow_runs_override is not None
                else [
                    {
                        "id": 1001,
                        "name": "CI",
                        "path": ".github/workflows/ci.yml",
                        "workflow_id": 42,
                        "run_attempt": 1,
                        "head_sha": pr_head_sha,
                        "status": "completed",
                        "conclusion": "success",
                    }
                ]
            ),
            "proposerRuns": proposer_runs
            if proposer_runs is not None
            else [
                {
                    "id": 501,
                    "workflow_id": 77,
                    "name": "Python Version Bump",
                    "path": ".github/workflows/python_version_bump.yml",
                    "head_branch": "main",
                    "head_sha": base_sha,
                    "run_attempt": 1,
                    "event": "schedule",
                    "status": "completed",
                    "conclusion": "success",
                    "actor": {"login": "github-actions[bot]"},
                    "repository": {"full_name": "uesu/Game-Express"},
                    "head_repository": {"full_name": "uesu/Game-Express"},
                }
            ],
            "jobsByRunId": {
                "1001": ci_jobs_override if ci_jobs_override is not None else _make_ci_jobs(pr_head_sha),
                **(
                    proposer_jobs
                    if proposer_jobs is not None
                    else {"501": _make_proposer_jobs()}
                ),
            },
        }
        if get_commit_error is not None:
            scen["getCommitError"] = get_commit_error
        if refresh_override is not None:
            scen["refreshOverride"] = refresh_override
        return scen

    # 1. Valid PAT-published patch bump bound to this PR/head/manifest -> merged
    out_ok = _run_live_adapter(_make_scenario())
    assert len(out_ok["mergedCalls"]) == 1, out_ok
    assert out_ok["mergedCalls"][0]["sha"] == head_sha
    assert "merged" in out_ok["summary"]

    # 2. Successful old proposer run (for PR #40) + a new unrelated Python PR (#55) -> rejected
    out_old_run = _run_live_adapter(
        _make_scenario(
            pr_num=55,
            proposer_jobs={"501": _make_proposer_jobs(pr_num="40", pub_head="1" * 40)},
        )
    )
    assert out_old_run["mergedCalls"] == [], out_old_run
    assert "proposer run published PR #40, which does not match current PR #55" in out_old_run["summary"]

    # 3. Dry-run proposer success (workflow conclusion=success, publish job=skipped, dry_run=true) -> rejected
    out_dry_run = _run_live_adapter(
        _make_scenario(
            proposer_jobs={
                "501": _make_proposer_jobs(
                    pr_num="none",
                    pub_head="none",
                    dry_run="true",
                    publish_conclusion="skipped",
                )
            }
        )
    )
    assert out_dry_run["mergedCalls"] == [], out_dry_run
    assert "dry_run" in out_dry_run["summary"]

    # 4. Later manually edited head (proposer run published "1"*40 on PR #50, current PR head is "a"*40) -> rejected
    out_edited_head = _run_live_adapter(
        _make_scenario(
            pr_num=50,
            pr_head_sha=head_sha,
            proposer_jobs={"501": _make_proposer_jobs(pr_num="50", pub_head="1" * 40)},
        )
    )
    assert out_edited_head["mergedCalls"] == [], out_edited_head
    assert "does not match current PR head" in out_edited_head["summary"]

    # 5. Mismatched manifest (proposer run recorded a different candidate_tree_sha256 than actual PR files) -> rejected
    out_bad_manifest = _run_live_adapter(
        _make_scenario(
            proposer_jobs={"501": _make_proposer_jobs(tree="d" * 64)},
        )
    )
    assert out_bad_manifest["mergedCalls"] == [], out_bad_manifest
    assert "does not match validated candidate manifest" in out_bad_manifest["summary"]

    # 6. Editable PR body spoofing (proposer run marked review_required=true / override, PR body edited to claim false/patch) -> rejected
    out_spoofed_body = _run_live_adapter(
        _make_scenario(
            pr_body=base_pr_body,
            proposer_jobs={
                "501": _make_proposer_jobs(
                    kind="override",
                    review="true",
                    eligible="false",
                )
            },
        )
    )
    assert out_spoofed_body["mergedCalls"] == [], out_spoofed_body
    assert "review-required" in out_spoofed_body["summary"]

    # 7. Real API-shaped workflow/jobs fixture (`proposer_workflow_jobs_api.json`) proving PROVENANCE step transport
    # across both the live JS adapter and direct Python `evaluate_auto_merge` (no injected `publication_provenance` dicts)
    api_fixture_raw = (FIXTURES / "proposer_workflow_jobs_api.json").read_text(encoding="utf-8")
    api_fixture = json.loads(api_fixture_raw.replace("__CANDIDATE_TREE_SHA256__", real_tree_sha))["scenarios"]

    for scen_name, expected_merge, expected_sub in (
        ("valid_patch_publication", True, "merged"),
        ("dry_run_skipped_publication", False, "dry_run"),
        ("stale_run_and_head", False, "does not match current PR"),
        ("changed_base_sha", False, "source_sha"),
        ("rerun_attempt_stale_attempt1_failed_attempt2", False, "validate_conclusion='failure'"),
        ("rerun_attempt_succeeded_attempt2", True, "merged"),
        ("missing_provenance_step", False, "does not match current PR"),
        ("manifest_mismatch", False, "does not match validated candidate manifest"),
    ):
        fx = api_fixture[scen_name]
        out_fx = _run_live_adapter(
            _make_scenario(
                pr_num=50,
                pr_head_sha=head_sha,
                proposer_runs=fx["workflow_runs"],
                proposer_jobs=fx["jobs_by_run_id"],
            )
        )
        if expected_merge:
            assert len(out_fx["mergedCalls"]) == 1, (scen_name, out_fx)
            assert out_fx["mergedCalls"][0]["sha"] == head_sha
        else:
            assert out_fx["mergedCalls"] == [], (scen_name, out_fx)
        assert expected_sub in out_fx["summary"], (scen_name, expected_sub, out_fx["summary"])

        # Also prove direct Python `evaluate_automerge` resolves the same raw API-shaped `proposer_workflow_runs` + `proposer_jobs_by_run`
        py_dec = maintenance.evaluate_automerge(
            {
                "pr_number": 50,
                "title": "chore(python): bump pinned Python from 3.14.8 to 3.14.9",
                "base_repo": "uesu/Game-Express",
                "head_repo": "uesu/Game-Express",
                "base_ref": "main",
                "base_sha": base_sha,
                "head_ref": "chore/python-bump",
                "head_sha": head_sha,
                "author": "uesu",
                "author_type": "User",
                "state": "OPEN",
                "is_draft": False,
                "mergeable": "MERGEABLE",
                "mergeable_state": "clean",
                "changed_files": [".python-version"],
                "file_diffs": {".python-version": "-3.14.8\n+3.14.9\n"},
                "commits": [{"sha": head_sha, "author": "github-actions[bot]"}],
                "published_commit": _valid_published_commit(head_sha),
                "check_runs": ci_checks,
                "producer_evidence": _full_producer_evidence(head_sha),
                "security_scan": _clean_security_scan(head_sha),
                "actual_candidate_manifest": real_manifest,
                "actual_candidate_tree_sha256": real_tree_sha,
                "proposer_workflow_runs": fx["workflow_runs"],
                "proposer_jobs_by_run": fx["jobs_by_run_id"],
                "provenance": {
                    "proposer_workflow_runs": fx["workflow_runs"],
                    "proposer_jobs_by_run": fx["jobs_by_run_id"],
                },
                "vars": {"AUTO_MERGE_DEPENDABOT": "yes", "AUTO_MERGE_PYTHON_BUMP": "yes"},
            }
        )
        assert py_dec.eligible is expected_merge, (scen_name, py_dec)
        if scen_name == "changed_base_sha":
            assert py_dec.classification == "deferred", (scen_name, py_dec)

    # 8. G3 collector-to-decision tests: raw envelope support, missing/null/malformed evidence,
    # wrong commit author/committer, wrong producer backlink/run/attempt, stale digest/head, and final refresh changes
    out_raw_env = _run_live_adapter(_make_scenario(raw_envelope=True))
    assert len(out_raw_env["mergedCalls"]) == 1, out_raw_env

    # 8a. Missing/failed getCommit (404) -> rejected (published-head-not-a-commit)
    out_no_commit = _run_live_adapter(_make_scenario(get_commit_error=404))
    assert out_no_commit["mergedCalls"] == [], out_no_commit
    assert "published-head-not-a-commit" in out_no_commit["summary"]

    # 8b. Wrong commit author login -> rejected (published-commit-author-login-mismatch)
    out_bad_author = _run_live_adapter(
        _make_scenario(published_commit=_valid_published_commit(head_sha, login="alice"))
    )
    assert out_bad_author["mergedCalls"] == [], out_bad_author
    assert "published-commit-author-login-mismatch" in out_bad_author["summary"]

    # 8c. Wrong commit committer login -> rejected (published-commit-committer-login-mismatch)
    out_bad_committer = _run_live_adapter(
        _make_scenario(published_commit=_valid_published_commit(head_sha, committer_login="mallory"))
    )
    assert out_bad_committer["mergedCalls"] == [], out_bad_committer
    assert "published-commit-committer-login-mismatch" in out_bad_committer["summary"]

    # 8d. Wrong commit git email -> rejected (published-commit-author-email-mismatch)
    out_bad_email = _run_live_adapter(
        _make_scenario(published_commit=_valid_published_commit(head_sha, email="wrong@example.com"))
    )
    assert out_bad_email["mergedCalls"] == [], out_bad_email
    assert "published-commit-author-email-mismatch" in out_bad_email["summary"]

    # 8e. Foreign/unresolvable check-run details_url -> rejected (unresolvable-details-url)
    foreign_checks = _full_ci_check_runs(
        head_sha,
        overrides={
            "Ruff lint": {
                "details_url": "https://github.com/evil/fork/actions/runs/1001/job/100103",
                "html_url": "https://github.com/evil/fork/actions/runs/1001/job/100103",
            }
        },
    )
    out_foreign_url = _run_live_adapter(_make_scenario(check_runs_override=foreign_checks))
    assert out_foreign_url["mergedCalls"] == [], out_foreign_url
    assert "unresolvable-details-url" in out_foreign_url["summary"]

    # 8f. Wrong producer backlink (job.check_run_url ID mismatch) -> rejected (producer-check-run-id-mismatch)
    out_bad_backlink = _run_live_adapter(
        _make_scenario(ci_jobs_override=_make_ci_jobs(head_sha, check_run_id_override=999999))
    )
    assert out_bad_backlink["mergedCalls"] == [], out_bad_backlink
    assert "producer-check-run-id-mismatch" in out_bad_backlink["summary"]

    # 8g. Wrong producer attempt (wfRun.run_attempt=2, job.run_attempt=1) -> rejected (producer-attempt-mismatch)
    out_bad_attempt = _run_live_adapter(
        _make_scenario(
            ci_workflow_runs_override=[
                {
                    "id": 1001,
                    "name": "CI",
                    "path": ".github/workflows/ci.yml",
                    "workflow_id": 42,
                    "run_attempt": 2,
                    "head_sha": head_sha,
                    "status": "completed",
                    "conclusion": "success",
                }
            ],
            ci_jobs_override=_make_ci_jobs(head_sha, run_attempt=1),
        )
    )
    assert out_bad_attempt["mergedCalls"] == [], out_bad_attempt
    assert "producer-attempt-mismatch" in out_bad_attempt["summary"]

    # 8h. Stale/tampered published file content -> rejected
    tampered_files = {**cand_contents, "requirements.txt": "# tampered content\n"}
    out_tampered_file = _run_live_adapter(_make_scenario(head_files=tampered_files))
    assert out_tampered_file["mergedCalls"] == [], out_tampered_file
    assert "does not match validated candidate manifest" in out_tampered_file["summary"]

    # 8i. Phase 2 pre-merge refresh: commit identity or producer backlink changes on refresh -> blocked before merge
    out_refresh_bad_commit = _run_live_adapter(
        _make_scenario(
            refresh_override={
                "publishedCommit": _valid_published_commit(head_sha, login="intruder")
            }
        )
    )
    assert out_refresh_bad_commit["mergedCalls"] == [], out_refresh_bad_commit
    assert "blocked on pre-merge refresh" in out_refresh_bad_commit["summary"]
    assert "published-commit-author-login-mismatch" in out_refresh_bad_commit["summary"]

    out_refresh_bad_producer = _run_live_adapter(
        _make_scenario(
            refresh_override={
                "jobsByRunId": {
                    "1001": _make_ci_jobs(head_sha, check_run_id_override=888888),
                    "501": _make_proposer_jobs(),
                }
            }
        )
    )
    assert out_refresh_bad_producer["mergedCalls"] == [], out_refresh_bad_producer
    assert "blocked on pre-merge refresh" in out_refresh_bad_producer["summary"]
    assert "producer-check-run-id-mismatch" in out_refresh_bad_producer["summary"]

    # 8j. Notice annotations path (`checks.listAnnotations` with `proposal-validation` and `proposal-publication`):
    # valid notices merge, tampered compiler pin in `proposal-validation` notice blocks with `validation-pip-mismatch`
    scen_good_notice = _make_scenario()
    scen_good_notice["annotationsByCheckRunId"] = {
        "50102": [{"message": valid_val_msg}],
        "50103": [{"message": valid_pub_msg}],
    }
    out_good_notice = _run_live_adapter(scen_good_notice)
    assert len(out_good_notice["mergedCalls"]) == 1, out_good_notice

    scen_bad_notice = _make_scenario()
    scen_bad_notice["annotationsByCheckRunId"] = {
        "50102": [{"message": valid_val_msg.replace('"26.1.1"', '"25.0.0"')}],
        "50103": [{"message": valid_pub_msg}],
    }
    out_bad_notice = _run_live_adapter(scen_bad_notice)
    assert out_bad_notice["mergedCalls"] == [], out_bad_notice
    assert "validation-compiler-mismatch" in out_bad_notice["summary"]


def test_g2_live_python_version_bump_workflow_registry_and_cli_subprocesses() -> None:
    """Verify `python_version_bump.yml` executes the same complete registry before and after rewrite,
    and test the actual CLI subprocess commands for missing security tools, candidate failure, and publish drift."""
    bump_wf = yaml.safe_load(
        (ROOT / ".github" / "workflows" / "python_version_bump.yml").read_text(encoding="utf-8")
    )
    validate_steps = bump_wf["jobs"]["validate"]["steps"]
    step_names = [s.get("name", "") for s in validate_steps]
    run_scripts = [s.get("run", "") for s in validate_steps if "run" in s]
    uses_steps = [s.get("uses", "") for s in validate_steps if "uses" in s]

    # Pre-rewrite and post-rewrite must both invoke `ci.py run-all` with explicit `--phase`, `--expected-python`,
    # `--with-security --require-security-tools --require-actionlint`, and external Action step outcome reporting
    assert any(
        "ci.py run-all --phase pre-rewrite --expected-python" in r
        and "--with-security" in r
        and "--require-security-tools" in r
        and "--require-actionlint" in r
        and "--external-security-result" in r
        for r in run_scripts
    ), run_scripts
    assert any(
        "ci.py run-all --phase post-rewrite --expected-python" in r
        and "--require-exact-python" in r
        and "--with-security" in r
        and "--require-security-tools" in r
        and "--require-actionlint" in r
        and "--external-security-result" in r
        for r in run_scripts
    ), run_scripts
    # Action-based workflow & security audits (actionlint, zizmor, pip-audit) must run in both phases
    assert sum(1 for u in uses_steps if "reviewdog/action-actionlint@" in u) == 2, step_names
    assert sum(1 for u in uses_steps if "zizmorcore/zizmor-action@" in u) == 2, step_names
    assert sum(1 for u in uses_steps if "pypa/gh-action-pip-audit@" in u) == 2, step_names

    # Publish job must assert candidate interpreter, verify manifest before create-pull-request, and record publication provenance
    publish_steps = bump_wf["jobs"]["publish"]["steps"]
    pub_runs = [s.get("run", "") for s in publish_steps if "run" in s]
    assert any(
        "assert-interpreter --expected" in r
        and "lock-compile --require-exact-python --expected" in r
        and "verify-candidate-manifest" in r
        for r in pub_runs
    )
    assert any("emit-validation-notice" in r for r in run_scripts), run_scripts
    assert any("record-publication-provenance" in r and "emit-publication-notice" in r for r in pub_runs), pub_runs

    running_py = platform.python_version()

    # Direct isolated probe: `ci.run_security_audit(ROOT)` with `shutil.which` returning None MUST fail closed (return != 0)
    ci_spec = importlib.util.spec_from_file_location("_gamexpress_ci_test", ROOT / ".github" / "scripts" / "ci.py")
    assert ci_spec and ci_spec.loader
    ci_mod = importlib.util.module_from_spec(ci_spec)
    sys.modules[ci_spec.name] = ci_mod
    ci_spec.loader.exec_module(ci_mod)
    captured_err = io.StringIO()
    with mock.patch.object(ci_mod.shutil, "which", return_value=None), contextlib.redirect_stderr(captured_err):
        assert ci_mod.run_security_audit(ROOT) == 1
    err_txt = captured_err.getvalue()
    assert "actionlint" in err_txt and "zizmor" in err_txt and "pip-audit" in err_txt

    # Subprocess test 1: `ci.py security-audit` (default, no extra flags) with empty PATH -> fails closed
    res_no_sec = subprocess.run(
        [
            sys.executable,
            str(ROOT / ".github" / "scripts" / "ci.py"),
            "security-audit",
        ],
        cwd=str(ROOT),
        env={"PATH": ""},
        capture_output=True,
        text=True,
        check=False,
    )
    assert res_no_sec.returncode != 0
    assert "required workflow linter 'actionlint' is not installed" in res_no_sec.stderr
    assert "required security tool 'zizmor' is not installed" in res_no_sec.stderr
    assert "required security tool 'pip-audit' is not installed" in res_no_sec.stderr

    # Subprocess test 2: Candidate interpreter mismatch on `ci.py run-all --phase pre-rewrite` -> fails closed before tests
    res_bad_py = subprocess.run(
        [
            sys.executable,
            str(ROOT / ".github" / "scripts" / "ci.py"),
            "run-all",
            "--phase",
            "pre-rewrite",
            "--expected-python",
            "3.99.0",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert res_bad_py.returncode != 0
    assert "3.99.0" in res_bad_py.stderr

    # Subprocess test 3: Pre-rewrite vs post-rewrite lock-check and publish drift via real CLI commands
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_repo = Path(tmp_dir)
        shutil.copytree(ROOT / ".github", tmp_repo / ".github")
        for fname in (
            ".python-version",
            "ruff.toml",
            "requirements.in",
            "requirements-dev.in",
            "requirements.txt",
            "requirements-dev.txt",
        ):
            shutil.copy2(ROOT / fname, tmp_repo / fname)
        subprocess.run(["git", "init", "-q"], cwd=tmp_repo, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_repo, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_repo, check=True)
        subprocess.run(["git", "add", "."], cwd=tmp_repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_repo, check=True)

        # Compute validated manifest via CLI subprocess
        out_file = tmp_repo / "gh_out.txt"
        res_cm = subprocess.run(
            [sys.executable, str(tmp_repo / ".github" / "scripts" / "maintenance.py"), "compute-candidate-manifest"],
            cwd=str(tmp_repo),
            env={**os.environ, "GITHUB_OUTPUT": str(out_file)},
            capture_output=True,
            text=True,
            check=False,
        )
        assert res_cm.returncode == 0, res_cm.stderr
        out_lines = dict(
            line.split("=", 1)
            for line in out_file.read_text(encoding="utf-8").strip().splitlines()
            if "=" in line
        )
        tree_sha = out_lines["candidate_tree_sha256"]
        manifest_json = out_lines["candidate_manifest_json"]

        # Record publication provenance via CLI subprocess
        rpp_out = tmp_repo / "rpp_out.txt"
        res_rpp = subprocess.run(
            [
                sys.executable,
                str(tmp_repo / ".github" / "scripts" / "maintenance.py"),
                "record-publication-provenance",
                "--run-id",
                "777",
                "--run-attempt",
                "1",
                "--source-sha",
                "b" * 40,
                "--pr-number",
                "50",
                "--published-head-sha",
                "a" * 40,
                "--old-version",
                "3.14.8",
                "--new-version",
                running_py,
                "--update-kind",
                "patch",
                "--review-required",
                "false",
                "--auto-merge-eligible",
                "true",
                "--candidate-tree-sha256",
                tree_sha,
                "--candidate-manifest-json",
                manifest_json,
            ],
            cwd=str(tmp_repo),
            env={**os.environ, "GITHUB_OUTPUT": str(rpp_out)},
            capture_output=True,
            text=True,
            check=False,
        )
        assert res_rpp.returncode == 0, res_rpp.stderr
        rpp_lines = dict(
            line.split("=", 1)
            for line in rpp_out.read_text(encoding="utf-8").strip().splitlines()
            if "=" in line
        )
        rec_data = json.loads(rpp_lines["publication_provenance_json"])
        assert rec_data["published_pr_number"] == 50
        assert rec_data["published_head_sha"] == "a" * 40
        assert rec_data["candidate_tree_sha256"] == tree_sha

        # Simulate publish drift: modify requirements.txt before verify-candidate-manifest / record-publication-provenance
        (tmp_repo / "requirements.txt").write_text("# drifted\n", encoding="utf-8")
        res_drift = subprocess.run(
            [
                sys.executable,
                str(tmp_repo / ".github" / "scripts" / "maintenance.py"),
                "verify-candidate-manifest",
                "--expected-json",
                manifest_json,
            ],
            cwd=str(tmp_repo),
            capture_output=True,
            text=True,
            check=False,
        )
        assert res_drift.returncode != 0
        assert "mismatch" in res_drift.stderr

        # Restore requirements.txt and set up a minimal test suite in tmp_repo so `ci.py run-all --with-security`
        # can be exercised as a full CLI subprocess across all missing/failing/passing tool combinations
        shutil.copy2(ROOT / "requirements.txt", tmp_repo / "requirements.txt")
        (tmp_repo / "tests").mkdir(exist_ok=True)
        (tmp_repo / "tests" / "test_unit.py").write_text("print('ok')\n", encoding="utf-8")
        pol_obj = json.loads((tmp_repo / ".github" / "maintenance.json").read_text(encoding="utf-8"))
        pol_obj["ci"]["registered_tests"] = ["tests/test_unit.py"]
        (tmp_repo / ".github" / "maintenance.json").write_text(
            json.dumps(pol_obj, indent=2) + "\n",
            encoding="utf-8",
        )

        def _make_tool_dir(base: Path, name: str, tools: dict[str, int]) -> Path:
            d = base / name
            d.mkdir(parents=True, exist_ok=True)
            # Always provide a fast ruff stub so `run_ruff` passes and `run-all --with-security` reaches `run_security_audit`
            ruff_sh = d / "ruff"
            ruff_sh.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            ruff_sh.chmod(0o755)
            for t_name, exit_code in tools.items():
                t_path = d / t_name
                t_path.write_text(f"#!/bin/sh\nexit {exit_code}\n", encoding="utf-8")
                t_path.chmod(0o755)
            return d

        # (a) `run-all --with-security` (no extra flags) with ALL security tools absent -> fails closed (returncode != 0)
        bin_none = _make_tool_dir(tmp_repo, "bin_none", {})
        res_all_absent = subprocess.run(
            [
                sys.executable,
                str(tmp_repo / ".github" / "scripts" / "ci.py"),
                "--profile",
                "production",
                "run-all",
                "--with-security",
            ],
            cwd=str(tmp_repo),
            env={"PATH": str(bin_none)},
            capture_output=True,
            text=True,
            check=False,
        )
        assert res_all_absent.returncode != 0, res_all_absent.stdout + res_all_absent.stderr
        assert "required workflow linter 'actionlint' is not installed" in res_all_absent.stderr
        assert "required security tool 'zizmor' is not installed" in res_all_absent.stderr
        assert "required security tool 'pip-audit' is not installed" in res_all_absent.stderr

        # (b) `run-all --with-security` (no extra flags) with ONE tool absent (each of actionlint, zizmor, pip-audit) -> fails closed
        for missing_tool, present_tools in (
            ("actionlint", {"zizmor": 0, "pip-audit": 0}),
            ("zizmor", {"actionlint": 0, "pip-audit": 0}),
            ("pip-audit", {"actionlint": 0, "zizmor": 0}),
        ):
            bin_one_missing = _make_tool_dir(tmp_repo, f"bin_missing_{missing_tool}", present_tools)
            res_one_missing = subprocess.run(
                [
                    sys.executable,
                    str(tmp_repo / ".github" / "scripts" / "ci.py"),
                    "--profile",
                    "production",
                    "run-all",
                    "--with-security",
                ],
                cwd=str(tmp_repo),
                env={"PATH": str(bin_one_missing)},
                capture_output=True,
                text=True,
                check=False,
            )
            assert res_one_missing.returncode != 0, (missing_tool, res_one_missing.stderr)
            assert f"'{missing_tool}' is not installed" in res_one_missing.stderr

        # (c) `run-all --with-security` (no extra flags) with all tools present and ONE failing -> fails closed
        for failing_tool in ("actionlint", "zizmor", "pip-audit"):
            tool_map = {"actionlint": 0, "zizmor": 0, "pip-audit": 0}
            tool_map[failing_tool] = 1
            bin_one_fail = _make_tool_dir(tmp_repo, f"bin_fail_{failing_tool}", tool_map)
            res_one_fail = subprocess.run(
                [
                    sys.executable,
                    str(tmp_repo / ".github" / "scripts" / "ci.py"),
                    "--profile",
                    "production",
                    "run-all",
                    "--with-security",
                ],
                cwd=str(tmp_repo),
                env={"PATH": str(bin_one_fail)},
                capture_output=True,
                text=True,
                check=False,
            )
            assert res_one_fail.returncode != 0, (failing_tool, res_one_fail.stdout, res_one_fail.stderr)

        # (d) `run-all --with-security` with all 3 tools present and succeeding -> exits 0
        bin_all_ok = _make_tool_dir(tmp_repo, "bin_all_ok", {"actionlint": 0, "zizmor": 0, "pip-audit": 0})
        res_all_ok = subprocess.run(
            [
                sys.executable,
                str(tmp_repo / ".github" / "scripts" / "ci.py"),
                "--profile",
                "production",
                "run-all",
                "--with-security",
            ],
            cwd=str(tmp_repo),
            env={"PATH": str(bin_all_ok)},
            capture_output=True,
            text=True,
            check=False,
        )
        assert res_all_ok.returncode == 0, res_all_ok.stderr

        # (e) External Action result reporting (`--external-security-result`) when local binaries are absent:
        #     succeeds and reports external results when all 3 are `success`, fails closed when any is `failure` or `skipped`
        res_ext_ok = subprocess.run(
            [
                sys.executable,
                str(tmp_repo / ".github" / "scripts" / "ci.py"),
                "--profile",
                "production",
                "run-all",
                "--with-security",
                "--external-security-result",
                "actionlint=success",
                "--external-security-result",
                "zizmor=success",
                "--external-security-result",
                "pip-audit=success",
            ],
            cwd=str(tmp_repo),
            env={"PATH": str(bin_none)},
            capture_output=True,
            text=True,
            check=False,
        )
        assert res_ext_ok.returncode == 0, res_ext_ok.stderr
        assert "EXTERNAL ACTION RESULT: actionlint=success" in res_ext_ok.stdout
        assert "EXTERNAL ACTION RESULT: zizmor=success" in res_ext_ok.stdout
        assert "EXTERNAL ACTION RESULT: pip-audit=success" in res_ext_ok.stdout

        res_ext_fail = subprocess.run(
            [
                sys.executable,
                str(tmp_repo / ".github" / "scripts" / "ci.py"),
                "--profile",
                "production",
                "run-all",
                "--with-security",
                "--external-security-result",
                "actionlint=success",
                "--external-security-result",
                "zizmor=skipped",
                "--external-security-result",
                "pip-audit=success",
            ],
            cwd=str(tmp_repo),
            env={"PATH": str(bin_none)},
            capture_output=True,
            text=True,
            check=False,
        )
        assert res_ext_fail.returncode != 0
        assert "external Action check 'zizmor' did not succeed" in res_ext_fail.stderr

        # (f) CLI subprocesses `emit-validation-notice` and `emit-publication-notice` emit parseable records
        res_val_notice = subprocess.run(
            [
                sys.executable,
                str(tmp_repo / ".github" / "scripts" / "maintenance.py"),
                "emit-validation-notice",
                "--candidate",
                "3.14.9",
                "--source-head",
                "b" * 40,
                "--run-id",
                "501",
                "--run-attempt",
                "1",
            ],
            cwd=str(tmp_repo),
            capture_output=True,
            text=True,
            check=False,
        )
        assert res_val_notice.returncode == 0, res_val_notice.stderr
        parsed_val = maintenance.maintenance_common.parse_notice(
            res_val_notice.stdout.strip(), "proposal-validation"
        )
        assert parsed_val is not None
        assert parsed_val["candidate_version"] == "3.14.9"
        assert parsed_val["source_head"] == "b" * 40

        res_pub_notice = subprocess.run(
            [
                sys.executable,
                str(tmp_repo / ".github" / "scripts" / "maintenance.py"),
                "emit-publication-notice",
                "--pull-number",
                "50",
                "--published-head",
                "a" * 40,
                "--branch",
                "chore/python-bump",
                "--pr-author",
                "uesu",
                "--run-actor",
                "github-actions[bot]",
                "--run-id",
                "501",
                "--run-attempt",
                "1",
            ],
            cwd=str(tmp_repo),
            capture_output=True,
            text=True,
            check=False,
        )
        assert res_pub_notice.returncode == 0, res_pub_notice.stderr
        parsed_pub = maintenance.maintenance_common.parse_notice(
            res_pub_notice.stdout.strip(), "proposal-publication"
        )
        assert parsed_pub is not None
        assert parsed_pub["pull_number"] == 50
        assert parsed_pub["published_head"] == "a" * 40


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
