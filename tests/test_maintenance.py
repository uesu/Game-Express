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
        # Verify job-level env never references runner., steps., or job. contexts (G1)
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
                # Verify no unquoted ${VAR:+...} or $PING_FLAG shell expansions (G1)
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

        # Inject forbidden runner.temp in job-level env and unquoted ${GAME_ARG:+...}
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

    # Verify normalize_lock_text never rewrites or fabricates the interpreter header (G4)
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

    # 1. Current-series patch is selected first (3.14.8 -> 3.14.9) and is auto-merge eligible (G4)
    sel_patch = maintenance.select_target_python(
        manifest, "3.14.8", policy, release_dates=release_dates
    )
    assert sel_patch.selected_version == "3.14.9"
    assert sel_patch.changed is True
    assert sel_patch.status == "proposed"
    assert sel_patch.update_kind == "patch"
    assert sel_patch.review_required is False
    assert sel_patch.auto_merge_eligible is True

    # 2. When already at 3.14.9 and minor upgrades to 3.15 are allowed:
    policy_315 = json.loads(json.dumps(policy))
    policy_315["python"]["max_validated_minor"] = 15
    policy_315["python"]["allow_minor_upgrades"] = True
    policy_315["python"]["minor_soak_days"] = 30

    # 2a. Missing release dates -> defer (never treat unknown age as 0 days soaked)
    sel_no_dates = maintenance.select_target_python(
        manifest, "3.14.9", policy_315, release_dates={}
    )
    assert sel_no_dates.changed is False
    assert sel_no_dates.status == "deferred"
    assert "release-date-unavailable" in sel_no_dates.reason
    assert sel_no_dates.deferred_candidate == "3.15.0"

    # 2b. Soak incomplete (e.g. 10 days after 2026-10-01 release) -> defer
    now_10d = datetime.datetime(2026, 10, 11, tzinfo=datetime.timezone.utc)
    sel_unsoaked = maintenance.select_target_python(
        manifest, "3.14.9", policy_315, release_dates=release_dates, now=now_10d
    )
    assert sel_unsoaked.changed is False
    assert sel_unsoaked.status == "deferred"
    assert "soak-period-incomplete" in sel_unsoaked.reason
    assert sel_unsoaked.deferred_candidate == "3.15.0"

    # 2c. Soak complete (45 days after 2026-10-01 release) -> review-required (never auto-merged)
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

    # 3. Skipped minor series (3.16.0 when pinned on 3.14.9) is deferred
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

    # 4. Manual override validation:
    # 4a. Valid override -> review-required
    sel_ov_ok = maintenance.select_target_python(
        manifest, "3.14.8", policy, override_version="3.14.9"
    )
    assert sel_ov_ok.changed is True
    assert sel_ov_ok.status == "review-required"
    assert sel_ov_ok.update_kind == "override"
    assert sel_ov_ok.review_required is True
    assert sel_ov_ok.auto_merge_eligible is False

    # 4b. Downgrade override -> failed
    sel_ov_down = maintenance.select_target_python(
        manifest, "3.14.8", policy, override_version="3.13.9"
    )
    assert sel_ov_down.changed is False
    assert sel_ov_down.status == "failed"
    assert "downgrade" in sel_ov_down.reason

    # 4c. Skipped-minor override -> failed
    sel_ov_skip = maintenance.select_target_python(
        manifest_316, "3.14.8", policy_316, override_version="3.16.0"
    )
    assert sel_ov_skip.changed is False
    assert sel_ov_skip.status == "failed"
    assert "skipped-minor-series" in sel_ov_skip.reason

    # 5. Ruff target clamping: when 3.15 is selected and known_ruff_targets stops at py314, clamp to py314.
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

        # Docless production clone: no README.md, no AGENTS.md, no docs/
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

    merge_raw = (ROOT / ".github" / "workflows" / "maintenance_merge.yml").read_text(encoding="utf-8")
    merge_data = yaml.safe_load(merge_raw)
    on_block = merge_data.get("on") or merge_data.get(True)
    assert "pull_request_target" in on_block
    assert "workflow_run" in on_block
    assert "pull_request_review" in on_block
    assert "workflow_dispatch" in on_block
    assert on_block["pull_request_target"]["branches"] == ["main"]

    # G2: Ensure maintenance_merge.yml never manufactures passing checks or MERGEABLE defaults
    assert 'checks["maintenance-ci"] = "SUCCESS"' not in merge_raw
    assert 'pr.mergeable === false ? "CONFLICTING" : "MERGEABLE"' not in merge_raw
    assert "verify-merge-result" in merge_raw

    # G4: Ensure python_version_bump.yml separates read-only select/validate from publish and requires BUMP_PAT
    bump_raw = (ROOT / ".github" / "workflows" / "python_version_bump.yml").read_text(encoding="utf-8")
    bump_data = yaml.safe_load(bump_raw)
    assert set(bump_data["jobs"].keys()) == {"select", "validate", "publish", "report"}
    assert bump_data["jobs"]["select"]["permissions"] == {"contents": "read"}
    assert bump_data["jobs"]["validate"]["permissions"]["contents"] == "read"
    assert "BUMP_PAT" not in yaml.dump(bump_data["jobs"]["validate"])
    assert "secrets.BUMP_PAT || github.token" not in bump_raw
    assert "updatechore" not in bump_raw


def test_automerge_lane_eligibility_and_g2_g3_hardening() -> None:
    policy = maintenance.load_policy(ROOT)

    # 1. Allowed Dependabot pip patch update
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
            "check_runs": [
                {
                    "name": "maintenance-ci",
                    "head_sha": "a" * 40,
                    "status": "COMPLETED",
                    "conclusion": "SUCCESS",
                    "app_slug": "github-actions",
                }
            ],
            "vars": {"AUTO_MERGE_DEPENDABOT": "yes", "AUTO_MERGE_PYTHON_BUMP": "no"},
        },
        policy,
    )
    assert dec1.eligible is True, dec1.reason
    assert dec1.lane == "dependabot_pip"
    assert dec1.validated_head_sha == "a" * 40

    # 2. G2: Zero checks reported -> deferred (never manufactured as SUCCESS)
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
            "dependency_updates": [{"name": "aiohttp", "from": "3.14.5", "to": "3.14.6"}],
            "check_runs": [],
            "checks": {},
        },
        policy,
    )
    assert dec_zero_checks.eligible is False
    assert dec_zero_checks.classification == "deferred"
    assert "zero checks" in dec_zero_checks.reason

    # 3. G2: Unknown/null mergeability -> deferred (never defaulted to MERGEABLE)
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
            "dependency_updates": [{"name": "aiohttp", "from": "3.14.5", "to": "3.14.6"}],
            "checks": {"maintenance-ci": "SUCCESS"},
        },
        policy,
    )
    assert dec_unknown_mergeable.eligible is False
    assert dec_unknown_mergeable.classification == "deferred"

    # 4. G2: Stale-head check run or untrusted check app -> rejected
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
            "dependency_updates": [{"name": "aiohttp", "from": "3.14.5", "to": "3.14.6"}],
            "check_runs": [
                {
                    "name": "maintenance-ci",
                    "head_sha": "b" * 40,
                    "status": "COMPLETED",
                    "conclusion": "SUCCESS",
                    "app_slug": "github-actions",
                }
            ],
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
            "dependency_updates": [{"name": "aiohttp", "from": "3.14.5", "to": "3.14.6"}],
            "check_runs": [
                {
                    "name": "maintenance-ci",
                    "head_sha": "a" * 40,
                    "status": "COMPLETED",
                    "conclusion": "SUCCESS",
                    "app_slug": "spoofed-ci-app",
                }
            ],
        },
        policy,
    )
    assert dec_untrusted_app.eligible is False
    assert "untrusted app" in dec_untrusted_app.reason

    # 5. G3: Independent opt-in variables per lane
    dec_py_disabled = maintenance.evaluate_automerge(
        {
            "base_repo": "uesu/Game-Express",
            "head_repo": "uesu/Game-Express",
            "base_ref": "main",
            "head_ref": "chore/python-bump",
            "author": "uesu",
            "state": "OPEN",
            "is_draft": False,
            "mergeable": "MERGEABLE",
            "changed_files": [".python-version", "ruff.toml"],
            "python_update": {"from": "3.14.8", "to": "3.14.9"},
            "checks": {"maintenance-ci": "SUCCESS"},
            "vars": {"AUTO_MERGE_DEPENDABOT": "yes", "AUTO_MERGE_PYTHON_BUMP": "no"},
        },
        policy,
    )
    assert dec_py_disabled.eligible is False
    assert "AUTO_MERGE_PYTHON_BUMP" in dec_py_disabled.reason

    # 6. G3: Version risk rejection (major, 0.x minor, prerelease, downgrade)
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
                "author": "dependabot[bot]",
                "state": "OPEN",
                "is_draft": False,
                "mergeable": "MERGEABLE",
                "changed_files": ["requirements.txt"],
                "dependency_updates": [{"name": "pkg", "from": bad_from, "to": bad_to}],
                "checks": {"maintenance-ci": "SUCCESS"},
            },
            policy,
        )
        assert dec_risk.eligible is False, f"Expected {bad_from}->{bad_to} to be rejected"

    # 7. G3: Review state resolution (CHANGES_REQUESTED followed by COMMENTED still blocks!)
    dec_review_block = maintenance.evaluate_automerge(
        {
            "base_repo": "uesu/Game-Express",
            "head_repo": "uesu/Game-Express",
            "base_ref": "main",
            "head_ref": "dependabot/pip/aiohttp-3.14.6",
            "author": "dependabot[bot]",
            "state": "OPEN",
            "is_draft": False,
            "mergeable": "MERGEABLE",
            "changed_files": ["requirements.txt"],
            "dependency_updates": [{"name": "aiohttp", "from": "3.14.5", "to": "3.14.6"}],
            "reviews": [
                {"author": "alice", "state": "CHANGES_REQUESTED"},
                {"author": "alice", "state": "COMMENTED"},
            ],
            "checks": {"maintenance-ci": "SUCCESS"},
        },
        policy,
    )
    assert dec_review_block.eligible is False
    assert "CHANGES_REQUESTED" in dec_review_block.reason

    # 8. G3: Allowed chore/python-bump patch update vs rejected minor update
    dec_py_patch = maintenance.evaluate_automerge(
        {
            "base_repo": "uesu/Game-Express",
            "head_repo": "uesu/Game-Express",
            "base_ref": "main",
            "head_ref": "chore/python-bump",
            "author": "uesu",
            "state": "OPEN",
            "is_draft": False,
            "mergeable": "MERGEABLE",
            "changed_files": [".python-version", "ruff.toml"],
            "python_update": {"from": "3.14.8", "to": "3.14.9"},
            "checks": {"maintenance-ci": "SUCCESS"},
            "vars": {"AUTO_MERGE_PYTHON_BUMP": "yes"},
        },
        policy,
    )
    assert dec_py_patch.eligible is True
    assert dec_py_patch.lane == "python_bump"

    dec_py_minor = maintenance.evaluate_automerge(
        {
            "base_repo": "uesu/Game-Express",
            "head_repo": "uesu/Game-Express",
            "base_ref": "main",
            "head_ref": "chore/python-bump",
            "author": "uesu",
            "state": "OPEN",
            "is_draft": False,
            "mergeable": "MERGEABLE",
            "changed_files": [".python-version", "ruff.toml"],
            "python_update": {"from": "3.14.9", "to": "3.15.0"},
            "checks": {"maintenance-ci": "SUCCESS"},
            "vars": {"AUTO_MERGE_PYTHON_BUMP": "yes"},
        },
        policy,
    )
    assert dec_py_minor.eligible is False
    assert dec_py_minor.classification == "review-required"

    # 9. G3: Head drift on pre-merge refresh and merge response verification
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
            "python_update": {"from": "3.14.8", "to": "3.14.9"},
            "checks": {"maintenance-ci": "SUCCESS"},
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
