"""Offline tests for the unified maintenance system, runtime pinning, and auto-merge lanes."""

from __future__ import annotations

import importlib.util
import json
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
        for job_name, job in (data.get("jobs") or {}).items():
            for step in job.get("steps") or []:
                uses = step.get("uses", "")
                if uses.startswith("actions/setup-python@"):
                    with_block = step.get("with") or {}
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


def test_lockfiles_have_hashes_and_match_policy() -> None:
    policy = maintenance.load_policy(ROOT)
    assert maintenance.validate_workflow_python_pins(ROOT, policy) == []
    ok, errors = maintenance.verify_lockfiles(ROOT, policy, recompile=True)
    assert ok, errors
    for rel in ("requirements.txt", "requirements-dev.txt"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "--hash=sha256:" in text, f"{rel} must contain sha256 hashes"
        assert "pip-compile" in text, f"{rel} must preserve pip-compile header"


def test_select_target_python_patch_and_minor_bounds() -> None:
    manifest = json.loads(
        (FIXTURES / "actions_versions_manifest.json").read_text(encoding="utf-8")
    )
    policy = maintenance.load_policy(ROOT)

    # With allow_minor_upgrades=False and max_validated_minor=14, 3.14.9 is selected.
    sel_314 = maintenance.select_target_python(manifest, "3.14.8", policy)
    assert sel_314.selected_version == "3.14.9"
    assert sel_314.changed is True
    assert sel_314.clamped_by_policy is True

    # When minor upgrades to 3.15 are enabled, stable 3.15.0 is selected while 3.15.0-alpha.4 is ignored.
    policy_315 = json.loads(json.dumps(policy))
    policy_315["python"]["max_validated_minor"] = 15
    policy_315["python"]["allow_minor_upgrades"] = True
    sel_315 = maintenance.select_target_python(manifest, "3.14.8", policy_315)
    assert sel_315.selected_version == "3.15.0"
    assert sel_315.selected_minor == "3.15"

    # Ruff target clamping: when 3.15 is selected and known_ruff_targets stops at py314, clamp to py314.
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


def test_apply_python_version_works_in_full_and_docless_clone() -> None:
    manifest = json.loads(
        (FIXTURES / "actions_versions_manifest.json").read_text(encoding="utf-8")
    )
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        shutil.copytree(ROOT / ".github", tmp_root / ".github")
        shutil.copy2(ROOT / ".python-version", tmp_root / ".python-version")
        shutil.copy2(ROOT / "ruff.toml", tmp_root / "ruff.toml")
        shutil.copy2(ROOT / "requirements.txt", tmp_root / "requirements.txt")
        shutil.copy2(ROOT / "requirements-dev.txt", tmp_root / "requirements-dev.txt")

        # Docless production clone: no README.md, no AGENTS.md, no docs/
        rc = maintenance.run_bump(tmp_root, manifest=manifest, policy=maintenance.load_policy(tmp_root))
        assert rc == 0
        assert (tmp_root / ".python-version").read_text(encoding="utf-8") == "3.14.9\n"
        assert (
            maintenance.validate_workflow_python_pins(
                tmp_root, maintenance.load_policy(tmp_root)
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

    merge_data = yaml.safe_load(
        (ROOT / ".github" / "workflows" / "maintenance_merge.yml").read_text(encoding="utf-8")
    )
    on_block = merge_data.get("on") or merge_data.get(True)
    assert "pull_request_target" in on_block
    assert on_block["pull_request_target"]["branches"] == ["main"]


def test_automerge_lane_eligibility_rules() -> None:
    policy = maintenance.load_policy(ROOT)

    # 1. Allowed Dependabot pip update
    dec1 = maintenance.evaluate_automerge(
        {
            "base_repo": "uesu/Game-Express",
            "head_repo": "uesu/Game-Express",
            "base_ref": "main",
            "head_ref": "dependabot/pip/aiohttp-3.14.6",
            "actor": "dependabot[bot]",
            "state": "OPEN",
            "is_draft": False,
            "mergeable": "MERGEABLE",
            "changed_files": ["requirements.txt", "requirements-dev.txt"],
            "checks": {"maintenance-ci": "SUCCESS"},
        },
        policy,
    )
    assert dec1.eligible is True
    assert dec1.lane == "dependabot_pip"

    # 2. Rejected workflow file change
    dec2 = maintenance.evaluate_automerge(
        {
            "base_repo": "uesu/Game-Express",
            "head_repo": "uesu/Game-Express",
            "base_ref": "main",
            "head_ref": "dependabot/github_actions/actions/checkout-7",
            "actor": "dependabot[bot]",
            "state": "OPEN",
            "is_draft": False,
            "mergeable": "MERGEABLE",
            "changed_files": [".github/workflows/ci.yml"],
            "checks": {"maintenance-ci": "SUCCESS"},
        },
        policy,
    )
    assert dec2.eligible is False
    assert "forbidden workflow path" in dec2.reason

    # 3. Allowed chore/python-bump update
    dec3 = maintenance.evaluate_automerge(
        {
            "base_repo": "uesu/Game-Express",
            "head_repo": "uesu/Game-Express",
            "base_ref": "main",
            "head_ref": "chore/python-bump",
            "actor": "github-actions[bot]",
            "state": "OPEN",
            "is_draft": False,
            "mergeable": "MERGEABLE",
            "changed_files": [".python-version", "ruff.toml", "docs/PYTHON_VERSION.md"],
            "checks": {"maintenance-ci": "SUCCESS"},
        },
        policy,
    )
    assert dec3.eligible is True
    assert dec3.lane == "python_bump"

    # 4. Rejected when chore/python-bump touches application code
    dec4 = maintenance.evaluate_automerge(
        {
            "base_repo": "uesu/Game-Express",
            "head_repo": "uesu/Game-Express",
            "base_ref": "main",
            "head_ref": "chore/python-bump",
            "actor": "github-actions[bot]",
            "state": "OPEN",
            "is_draft": False,
            "mergeable": "MERGEABLE",
            "changed_files": [".python-version", "gamexpress/runner.py"],
            "checks": {"maintenance-ci": "SUCCESS"},
        },
        policy,
    )
    assert dec4.eligible is False
    assert "does not allow file" in dec4.reason

    # 5. Rejected when maintenance-ci did not succeed
    dec5 = maintenance.evaluate_automerge(
        {
            "base_repo": "uesu/Game-Express",
            "head_repo": "uesu/Game-Express",
            "base_ref": "main",
            "head_ref": "dependabot/pip/aiohttp-3.14.6",
            "actor": "dependabot[bot]",
            "state": "OPEN",
            "is_draft": False,
            "mergeable": "MERGEABLE",
            "changed_files": ["requirements.txt"],
            "checks": {"maintenance-ci": "FAILURE"},
        },
        policy,
    )
    assert dec5.eligible is False
    assert "non-passing" in dec5.reason


def test_ci_adapter_gate_logic() -> None:
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
