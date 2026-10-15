"""Offline tests for the unified maintenance system, runtime pinning, and auto-merge lanes."""

from __future__ import annotations

import datetime
import importlib.util
import json
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

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
            "workflow_conclusion": "success",
            "update_kind": "patch",
            "review_required": False,
            "auto_merge_eligible": True,
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
