#!/usr/bin/env python3
"""Offline tests for the shared `.github/scripts/maintenance_common.py` module and Game-Express adapter integration."""

from __future__ import annotations

import base64
import datetime
import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SCRIPTS = ROOT / ".github" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import maintenance_common  # noqa: E402


def _load_script(name: str):
    path = SCRIPTS / name
    spec = importlib.util.spec_from_file_location(f"_ge_{name.replace('.', '_')}", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


maintenance = _load_script("maintenance.py")
ci_mod = _load_script("ci.py")

SHA = "a" * 40
REPO = "uesu/Game-Express"
BOT = "github-actions[bot]"
BOT_EMAIL = "41898282+github-actions[bot]@users.noreply.github.com"
EXPECTED_MAINTENANCE_COMMON_SHA256 = (
    "67e5b379c5de0a4a86fa78a3af4a8389a39155c88d6f08679eb963ffe2ae1d2a"
)
EXPECTED_PYTHON_VERSION_SHA256 = (
    "5abd4dc1efa09469b88916c8e4e027a8c266a9b6d06f43ac9da3e30cd00b4ab5"
)


def _published_commit(
    sha: str = SHA,
    *,
    login: str = BOT,
    name: str = BOT,
    email: str = BOT_EMAIL,
) -> dict[str, Any]:
    return {
        "sha": sha,
        "author": {"login": login},
        "committer": {"login": login},
        "commit": {
            "author": {"name": name, "email": email},
            "committer": {"name": name, "email": email},
        },
    }


class CommonFileDigestTests(unittest.TestCase):
    def test_common_files_match_immutable_candidate_sha256(self) -> None:
        common_bytes = (SCRIPTS / "maintenance_common.py").read_bytes()
        self.assertEqual(
            hashlib.sha256(common_bytes).hexdigest(),
            EXPECTED_MAINTENANCE_COMMON_SHA256,
        )
        py_bytes = (ROOT / ".python-version").read_bytes()
        self.assertEqual(
            hashlib.sha256(py_bytes).hexdigest(),
            EXPECTED_PYTHON_VERSION_SHA256,
        )


class RepoAssociationTests(unittest.TestCase):
    def test_missing_and_fork(self) -> None:
        pr: dict[str, Any] = {"head": {"sha": SHA, "ref": "x"}, "base": {"ref": "main"}}
        self.assertEqual(
            maintenance_common.repo_association_failure(pr, REPO),
            "missing-repo-association",
        )
        pr = {
            "head": {"repo": {"full_name": "alice/fork"}},
            "base": {"repo": {"full_name": REPO}},
        }
        self.assertEqual(
            maintenance_common.repo_association_failure(pr, REPO),
            "cross-fork-head",
        )
        pr = {
            "head": {"repo": {"full_name": REPO}},
            "base": {"repo": {"full_name": REPO}},
        }
        self.assertEqual(maintenance_common.repo_association_failure(pr, REPO), "")


class ProducerTests(unittest.TestCase):
    def test_foreign_details_url_is_unresolvable(self) -> None:
        self.assertIsNone(
            maintenance_common.parse_check_run_identity(
                "https://github.com/evil/fork/actions/runs/2/job/3", REPO
            )
        )
        self.assertEqual(
            maintenance_common.parse_check_run_identity(
                f"https://github.com/{REPO}/actions/runs/2/job/3", REPO
            ),
            (2, 3),
        )

    def test_collect_records_job_api_failure(self) -> None:
        def get_json(_url: str) -> tuple[int, Any]:
            return 403, {"message": "no"}

        evidence = maintenance_common.collect_producer_evidence(
            "uesu",
            "Game-Express",
            [
                {
                    "id": 1,
                    "name": "maintenance-ci",
                    "details_url": f"https://github.com/{REPO}/actions/runs/2/job/3",
                }
            ],
            ["maintenance-ci"],
            get_json,
        )
        self.assertEqual(evidence["maintenance-ci"]["error"], "job-api:403")

    def test_verify_requires_mutual_check_run_link(self) -> None:
        producers = {
            "maintenance-ci": {"workflow": ".github/workflows/ci.yml", "job": "maintenance-ci"}
        }
        found = {
            "workflow": ".github/workflows/ci.yml",
            "job": "maintenance-ci",
            "check_run_id": 1,
            "run_id": 2,
            "run_record_id": 2,
            "job_id": 3,
            "job_record_id": 3,
            "job_run_id": 2,
            "job_check_run_url": f"https://api.github.com/repos/{REPO}/check-runs/99",
            "run_attempt": 1,
            "job_run_attempt": 1,
            "head_sha": SHA,
            "job_head_sha": SHA,
            "job_status": "completed",
            "job_conclusion": "success",
            "run_status": "completed",
            "run_conclusion": "success",
        }
        result = maintenance_common.verify_check_producers(
            {"maintenance-ci": found},
            expected_names=["maintenance-ci"],
            head_sha=SHA,
            producers=producers,
            repository=REPO,
        )
        self.assertEqual(result["state"], "failed")
        self.assertIn("producer-check-run-id-mismatch", result["reason"])

    def test_stale_attempt_and_unapproved_job_fail(self) -> None:
        producers = {
            "maintenance-ci": {"workflow": ".github/workflows/ci.yml", "job": "maintenance-ci"}
        }
        found: dict[str, Any] = {
            "workflow": ".github/workflows/ci.yml",
            "job": "maintenance-ci",
            "check_run_id": 1,
            "run_id": 2,
            "run_record_id": 2,
            "job_id": 3,
            "job_record_id": 3,
            "job_run_id": 2,
            "job_check_run_url": f"https://api.github.com/repos/{REPO}/check-runs/1",
            "run_attempt": 2,
            "job_run_attempt": 1,
            "head_sha": SHA,
            "job_head_sha": SHA,
            "job_status": "completed",
            "job_conclusion": "success",
            "run_status": "completed",
            "run_conclusion": "success",
        }
        result = maintenance_common.verify_check_producers(
            {"maintenance-ci": found},
            expected_names=["maintenance-ci"],
            head_sha=SHA,
            producers=producers,
            repository=REPO,
        )
        self.assertEqual(result["reason"], "producer-attempt-mismatch:maintenance-ci")
        found["job_run_attempt"] = 2
        found["job"] = "other"
        result = maintenance_common.verify_check_producers(
            {"maintenance-ci": found},
            expected_names=["maintenance-ci"],
            head_sha=SHA,
            producers=producers,
            repository=REPO,
        )
        self.assertEqual(result["reason"], "unapproved-producer-job:maintenance-ci")

    def test_no_producers_configured_fails(self) -> None:
        result = maintenance_common.verify_check_producers(
            {},
            expected_names=["maintenance-ci"],
            head_sha=SHA,
            producers={},
            repository=REPO,
        )
        self.assertEqual(result["reason"], "no-approved-producers-configured")


class SecurityTests(unittest.TestCase):
    def test_disabled_vs_unconfigured(self) -> None:
        mode, kinds = maintenance_common.security_policy(
            {"security_evidence": {"mode": "disabled"}}
        )
        self.assertEqual(mode, "disabled")
        self.assertEqual(kinds, [])
        ready = maintenance_common.verify_security_evidence(None, [], mode="disabled")
        self.assertEqual(ready["reason"], "security-evidence-not-required")
        gap = maintenance_common.verify_security_evidence(None, [], mode="")
        self.assertEqual(gap["reason"], "security-evidence-unconfigured")

    def test_malformed_alert_is_not_zero_open(self) -> None:
        count = maintenance_common._count_open_alerts(
            [{"state": "open"}],
            code_scanning=True,
        )
        self.assertIsNone(count)
        count = maintenance_common._count_open_alerts(
            [{"state": "open", "most_recent_instance": {"state": "fixed"}}],
            code_scanning=True,
        )
        self.assertIsNone(count)
        count = maintenance_common._count_open_alerts(
            [{"state": "open", "most_recent_instance": {"state": "open"}}],
            code_scanning=True,
        )
        self.assertEqual(count, 1)

    def test_stale_analysis_is_not_this_head(self) -> None:
        def get_pages(url: str) -> tuple[int, Any]:
            if "analyses" in url:
                return 200, [{"commit_sha": "b" * 40, "error": None}]
            return 200, []

        result = maintenance_common.collect_security_evidence(
            "uesu", "Game-Express", SHA, ["code-scanning"], get_pages, ref="chore/x"
        )
        self.assertEqual(result["code-scanning"]["state"], "no-analysis-for-head")

    def test_missing_ref_scope_is_not_clean(self) -> None:
        def get_pages(url: str) -> tuple[int, Any]:
            if "analyses" in url:
                return 200, [{"commit_sha": SHA, "error": None}]
            return 200, []

        result = maintenance_common.collect_security_evidence(
            "uesu", "Game-Express", SHA, ["code-scanning"], get_pages, ref=""
        )
        self.assertEqual(result["code-scanning"]["state"], "missing-ref-scope")

    def test_open_alerts_fail_closed(self) -> None:
        result = maintenance_common.verify_security_evidence(
            {"code-scanning": {"state": "ok", "open": 1}},
            ["code-scanning"],
            mode="required",
        )
        self.assertEqual(result["state"], "failed")
        self.assertEqual(result["reason"], "unresolved-code-scanning-alerts:1")

    def test_http_403_defers(self) -> None:
        result = maintenance_common.verify_security_evidence(
            {"secret-scanning": {"state": "unavailable", "detail": "alerts-http:403"}},
            ["secret-scanning"],
            mode="required",
        )
        self.assertEqual(result["state"], "defer")


class PublicationTests(unittest.TestCase):
    def test_dependabot_skips_and_python_bump_needs_mode(self) -> None:
        pr = {
            "number": 1,
            "user": {"login": "github-actions[bot]"},
            "head": {"sha": SHA, "ref": "chore/python-bump"},
        }
        skipped = maintenance_common.verify_publication_gate(
            mode="", kind="dependabot", evidence={}, pr=pr
        )
        self.assertEqual(skipped["reason"], "publication-not-applicable")
        gap = maintenance_common.verify_publication_gate(
            mode="", kind="python_bump", evidence={}, pr=pr
        )
        self.assertEqual(gap["reason"], "publication-evidence-unconfigured")
        disabled = maintenance_common.verify_publication_gate(
            mode="disabled", kind="python_bump", evidence={}, pr=pr
        )
        self.assertEqual(disabled["reason"], "publication-lane-blocked")
        self.assertEqual(disabled["state"], "failed")

    def test_required_mode_rejects_missing_run_and_digest_mismatch(self) -> None:
        pr = {
            "number": 9,
            "user": {"login": "github-actions[bot]"},
            "head": {"sha": SHA, "ref": "chore/python-bump"},
        }
        missing = maintenance_common.verify_publication_gate(
            mode="required",
            kind="python_bump",
            evidence={"repository": REPO},
            pr=pr,
            candidate_version="3.14.9",
            repository=REPO,
        )
        self.assertEqual(missing["reason"], "no-proposer-run")

        run = {
            "id": 44,
            "workflow_id": 7,
            "path": maintenance_common.DEFAULT_PROPOSER_PATH,
            "status": "completed",
            "conclusion": "success",
            "run_attempt": 1,
            "head_sha": "c" * 40,
            "actor": {"login": "github-actions[bot]"},
            "repository": {"full_name": REPO},
            "head_repository": {"full_name": REPO},
        }
        evidence = {
            "repository": REPO,
            "proposer_run": run,
            "proposer_attempt": {
                "id": 44,
                "run_attempt": 1,
                "status": "completed",
                "conclusion": "success",
                "head_sha": "c" * 40,
            },
            "validation_record": {
                "run_id": 44,
                "run_attempt": 1,
                "source_head": "c" * 40,
                "candidate_version": "3.14.9",
                "interpreter": "3.14.9",
                "pip": maintenance_common.PINNED_PIP,
                "pip_tools": maintenance_common.PINNED_PIP_TOOLS,
                "digests": {".python-version": "aaa"},
            },
            "publication_record": {
                "run_id": 44,
                "run_attempt": 1,
                "pull_number": 9,
                "published_head": SHA,
                "branch": "chore/python-bump",
                "pr_author": "github-actions[bot]",
                "run_actor": "github-actions[bot]",
                "commit_identity": "github-actions[bot]",
                "digests": {".python-version": "bbb"},
            },
            "proposal_digests": {".python-version": "aaa"},
            "expected_commit_identity": "github-actions[bot]",
            "published_commit": {"sha": SHA},
        }
        mismatch = maintenance_common.verify_publication_gate(
            mode="required",
            kind="python_bump",
            evidence=evidence,
            pr=pr,
            candidate_version="3.14.9",
            proposal_files=[".python-version"],
            repository=REPO,
        )
        self.assertEqual(mismatch["reason"], "publication-digest-mismatch:.python-version")

    def test_notice_round_trip_with_and_without_prefix(self) -> None:
        record = {"run_id": 1, "candidate_version": "3.14.9"}
        rendered = maintenance_common.notice("proposal-validation", record)
        assert rendered is not None
        self.assertTrue(rendered.startswith("::notice::proposal-validation "))
        self.assertEqual(
            maintenance_common.parse_notice(rendered, "proposal-validation"),
            record,
        )
        stripped = rendered[len("::notice::") :]
        self.assertEqual(
            maintenance_common.parse_notice(stripped, "proposal-validation"),
            record,
        )
        self.assertIsNone(maintenance_common.parse_notice("not json", "proposal-validation"))

    def test_candidate_version_comes_from_pin_patch_not_title(self) -> None:
        files = [{"filename": ".python-version", "patch": "-3.14.8\n+3.14.9\n"}]
        self.assertEqual(maintenance_common.candidate_version_from_files(files), "3.14.9")
        self.assertIsNone(
            maintenance_common.candidate_version_from_files(
                [{"filename": "README.md", "patch": "+chore: bump CPython pin 3.14.8 -> 3.14.9\n"}]
            )
        )
        self.assertIsNone(
            maintenance_common.candidate_version_from_files(
                [{"filename": ".python-version", "patch": "-3.14.8\n+nope\n"}]
            )
        )

    def test_collect_binds_matching_publication_notice(self) -> None:
        source = "c" * 40
        pin = b"3.14.9\n"
        digest = hashlib.sha256(pin).hexdigest()
        validation = maintenance_common.build_validation_record(
            source_head=source,
            candidate="3.14.9",
            interpreter="3.14.9",
            pip_version=maintenance_common.PINNED_PIP,
            pip_tools_version=maintenance_common.PINNED_PIP_TOOLS,
            digests={".python-version": digest},
            run_id=44,
            run_attempt=1,
        )
        publication = maintenance_common.build_publication_record(
            run_id=44,
            run_attempt=1,
            pull_number=12,
            published_head=SHA,
            branch="chore/python-bump",
            digests={".python-version": digest},
            pr_author="github-actions[bot]",
            commit_identity="github-actions[bot]",
            run_actor="github-actions[bot]",
        )
        val_msg = maintenance_common.notice("proposal-validation", validation)
        pub_msg = maintenance_common.notice("proposal-publication", publication)
        assert val_msg is not None and pub_msg is not None
        val_msg = val_msg[len("::notice::") :]
        pub_msg = pub_msg[len("::notice::") :]
        pr = {
            "number": 12,
            "user": {"login": "github-actions[bot]"},
            "head": {"sha": SHA, "ref": "chore/python-bump", "repo": {"full_name": REPO}},
        }
        files = [{"filename": ".python-version", "patch": "-3.14.8\n+3.14.9\n"}]

        def get_json(url: str) -> tuple[int, Any]:
            if "/contents/" in url:
                return 200, {
                    "encoding": "base64",
                    "content": base64.b64encode(pin).decode("ascii"),
                }
            if "/commits/" in url:
                return 200, _published_commit(SHA)
            if "/attempts/" in url:
                return 200, {
                    "id": 44,
                    "run_attempt": 1,
                    "status": "completed",
                    "conclusion": "success",
                    "head_sha": source,
                }
            return 404, {}

        def get_pages(url: str) -> tuple[int, Any]:
            if "/runs?" in url:
                return 200, [
                    {
                        "id": 44,
                        "workflow_id": 7,
                        "path": ".github/workflows/python_version_bump.yml",
                        "status": "completed",
                        "conclusion": "success",
                        "run_attempt": 1,
                        "head_sha": source,
                        "actor": {"login": "github-actions[bot]"},
                        "repository": {"full_name": REPO},
                        "head_repository": {"full_name": REPO},
                    }
                ]
            if "/jobs" in url:
                return 200, [
                    {
                        "id": 9,
                        "name": "publish",
                        "check_run_url": f"https://api.github.com/repos/{REPO}/check-runs/77",
                    }
                ]
            if "/annotations" in url:
                return 200, [{"message": val_msg}, {"message": pub_msg}]
            return 404, {}

        evidence = maintenance_common.collect_publication_evidence(
            "uesu",
            "Game-Express",
            pr,
            files,
            get_json=get_json,
            get_pages=get_pages,
            trusted_proposer_path=".github/workflows/python_version_bump.yml",
            proposal_files=[".python-version"],
            expected_commit_identity="github-actions[bot]",
        )
        self.assertNotIn("error", evidence)
        self.assertEqual(evidence["proposal_digests"][".python-version"], digest)
        self.assertEqual(evidence["publication_record"]["pull_number"], 12)
        verified = maintenance_common.verify_publication_gate(
            mode="required",
            kind="python_bump",
            evidence=evidence,
            pr=pr,
            candidate_version="3.14.9",
            proposal_files=[".python-version"],
            repository=REPO,
        )
        self.assertEqual(verified["state"], "ready")

    def test_correct_notice_wrong_actual_commit_fails_verify(self) -> None:
        pr = {
            "number": 9,
            "user": {"login": "github-actions[bot]"},
            "head": {"sha": SHA, "ref": "chore/python-bump"},
        }
        run = {
            "id": 44,
            "workflow_id": 7,
            "path": maintenance_common.DEFAULT_PROPOSER_PATH,
            "status": "completed",
            "conclusion": "success",
            "run_attempt": 1,
            "head_sha": "c" * 40,
            "actor": {"login": "github-actions[bot]"},
            "repository": {"full_name": REPO},
            "head_repository": {"full_name": REPO},
        }
        evidence: dict[str, Any] = {
            "repository": REPO,
            "proposer_run": run,
            "proposer_attempt": {
                "id": 44,
                "run_attempt": 1,
                "status": "completed",
                "conclusion": "success",
                "head_sha": "c" * 40,
            },
            "validation_record": {
                "run_id": 44,
                "run_attempt": 1,
                "source_head": "c" * 40,
                "candidate_version": "3.14.9",
                "interpreter": "3.14.9",
                "pip": maintenance_common.PINNED_PIP,
                "pip_tools": maintenance_common.PINNED_PIP_TOOLS,
                "digests": {".python-version": "aaa"},
            },
            "publication_record": {
                "run_id": 44,
                "run_attempt": 1,
                "pull_number": 9,
                "published_head": SHA,
                "branch": "chore/python-bump",
                "pr_author": "github-actions[bot]",
                "run_actor": "github-actions[bot]",
                "commit_identity": "github-actions[bot]",
                "digests": {".python-version": "aaa"},
            },
            "proposal_digests": {".python-version": "aaa"},
            "expected_commit_identity": "github-actions[bot]",
            "published_commit": {
                "sha": SHA,
                "author": {"login": "alice"},
                "committer": {"login": "bob"},
                "commit": {
                    "author": {"name": "Alice", "email": "alice@example.test"},
                    "committer": {"name": "Bob", "email": "bob@example.test"},
                },
            },
        }
        result = maintenance_common.verify_publication_gate(
            mode="required",
            kind="python_bump",
            evidence=evidence,
            pr=pr,
            candidate_version="3.14.9",
            proposal_files=[".python-version"],
            repository=REPO,
        )
        self.assertEqual(result["state"], "failed")
        self.assertEqual(result["reason"], "published-commit-author-login-mismatch")

        evidence["published_commit"] = _published_commit(SHA)
        ok = maintenance_common.verify_publication_gate(
            mode="required",
            kind="python_bump",
            evidence=evidence,
            pr=pr,
            candidate_version="3.14.9",
            proposal_files=[".python-version"],
            repository=REPO,
        )
        self.assertEqual(ok["state"], "ready")


class ReleaseDateTests(unittest.TestCase):
    def test_apply_strips_setup_python_published_at(self) -> None:
        manifest = [
            {
                "version": "3.15.0",
                "stable": True,
                "published_at": "2026-10-01T00:00:00Z",
                "release_date": "2026-10-01T00:00:00Z",
            }
        ]
        enriched, report = maintenance_common.apply_release_dates(manifest, {}, "unavailable")
        self.assertNotIn("published_at", enriched[0])
        self.assertNotIn("release_date", enriched[0])
        self.assertIn("3.15.0", report["stripped_untrusted_dates"])
        self.assertIn("3.15.0", report["unknown"])

    def test_python_org_date_is_the_authority(self) -> None:
        manifest = [{"version": "3.15.0", "published_at": "2099-01-01T00:00:00Z"}]
        enriched, report = maintenance_common.apply_release_dates(
            manifest, {"3.15.0": "2026-01-15"}, "ok"
        )
        self.assertEqual(enriched[0]["release_date"], "2026-01-15")
        self.assertEqual(enriched[0]["release_date_source"], "python.org-downloads-api")
        self.assertNotIn("published_at", enriched[0])
        self.assertEqual(report["resolved"], ["3.15.0"])

    def test_fetch_uses_injected_opener_and_cache(self) -> None:
        payload = {
            "results": [
                {"name": "Python 3.15.0", "release_date": "2026-01-15T00:00:00Z"},
                {"name": "Not a release", "release_date": "2026-01-01T00:00:00Z"},
            ],
            "next": None,
        }

        class _Resp:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def read(self):
                return json.dumps(payload).encode("utf-8")

        def opener(url: str, timeout: int = 10):
            del timeout
            self.assertIn("python.org", url)
            return _Resp()

        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "dates.json"
            dates, state, _detail = maintenance_common.fetch_release_dates(
                opener=opener,
                cache_path=cache,
                now=datetime.datetime(2026, 3, 1, tzinfo=datetime.timezone.utc),
            )
            self.assertEqual(state, "ok")
            self.assertEqual(dates["3.15.0"], "2026-01-15")
            self.assertTrue(cache.is_file())


class CompilerPinTests(unittest.TestCase):
    def test_configured_commit_identity_matches_publisher_git(self) -> None:
        profile = json.loads((ROOT / ".github" / "maintenance.json").read_text(encoding="utf-8"))
        login, name, email = maintenance_common.configured_commit_identity(profile)
        self.assertEqual(login, "github-actions[bot]")
        self.assertEqual(name, "github-actions[bot]")
        self.assertEqual(email, BOT_EMAIL)
        self.assertIsNotNone(
            maintenance_common.published_commit_identity_failure(
                {"sha": SHA},
                head=SHA,
                expected_login=login,
                expected_name=name,
                expected_email=email,
            )
        )

    def test_pins_match_dev_lock_and_profile(self) -> None:
        self.assertEqual(maintenance_common.PINNED_PIP, "26.1.1")
        self.assertEqual(maintenance_common.PINNED_PIP_TOOLS, "7.5.3")
        profile = json.loads((ROOT / ".github" / "maintenance.json").read_text(encoding="utf-8"))
        pip, tools = maintenance_common.compiler_pins(profile)
        self.assertEqual(
            (pip, tools),
            (maintenance_common.PINNED_PIP, maintenance_common.PINNED_PIP_TOOLS),
        )
        text = (ROOT / "requirements-dev.txt").read_text(encoding="utf-8")
        self.assertIn(f"pip=={pip}", text)
        self.assertIn(f"pip-tools=={tools}", text)


class CiCompilerPinTests(unittest.TestCase):
    def test_lock_consistency_rejects_missing_compiler_pin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "requirements.txt").write_text("pkg==1.0 --hash=sha256:aa\n", encoding="utf-8")
            (root / "requirements-dev.txt").write_text(
                "ruff==0.17.0 --hash=sha256:bb\n", encoding="utf-8"
            )
            problems = ci_mod._compiler_pin_failures(root, {})
            self.assertTrue(any("pip==" in p for p in problems))


class GameAdapterIntegrationTests(unittest.TestCase):
    def test_game_evaluate_automerge_integrates_maintenance_common_guards(self) -> None:
        policy = maintenance.load_policy(ROOT)
        checks = [
            {
                "id": 100 + idx,
                "name": name,
                "status": "completed",
                "conclusion": "success",
                "head_sha": SHA,
                "app": {"slug": "github-actions"},
                "workflow_path": ".github/workflows/ci.yml",
                "workflow_name": "CI",
                "run_id": 500,
                "run_attempt": 1,
                "steps": [
                    {
                        "name": "Audit runtime requirements against OSV",
                        "status": "completed",
                        "conclusion": "success",
                    }
                ],
            }
            for idx, name in enumerate(policy["mandatory_check_names"])
        ]
        base_payload: dict[str, Any] = {
            "base_repo": REPO,
            "head_repo": REPO,
            "expected_repo": REPO,
            "base_ref": "main",
            "head_ref": "chore/python-bump",
            "head_sha": SHA,
            "state": "OPEN",
            "is_draft": False,
            "mergeable": "MERGEABLE",
            "mergeable_state": "clean",
            "author": "github-actions[bot]",
            "pr_number": 52,
            "changed_files": [".python-version", "ruff.toml"],
            "file_diffs": {
                ".python-version": "@@ -1 +1 @@\n-3.14.8\n+3.14.9\n",
                "ruff.toml": '@@ -1 +1 @@\n-target-version = "py314"\n+target-version = "py314"\n',
            },
            "python_update": {"from": "3.14.8", "to": "3.14.9"},
            "provenance": {
                "verified": True,
                "workflow": ".github/workflows/python_version_bump.yml",
                "workflow_name": "Python Version Bump",
                "workflow_run_id": 888,
                "workflow_conclusion": "success",
                "published_pr_number": 52,
                "published_head_sha": SHA,
                "old_version": "3.14.8",
                "new_version": "3.14.9",
                "update_kind": "patch",
                "review_required": False,
                "auto_merge_eligible": True,
            },
            "check_runs": checks,
            "security_scan": {
                "present": True,
                "status": "clean",
                "step_conclusion": "success",
                "head_sha": SHA,
            },
            "published_commit": _published_commit(SHA),
            "vars": {"AUTO_MERGE_PYTHON_BUMP": "yes"},
        }
        ok_dec = maintenance.evaluate_automerge(base_payload, policy)
        self.assertTrue(ok_dec.eligible, ok_dec.reason)

        # Unrelated commit author login must fail closed via maintenance_common.published_commit_identity_failure
        bad_commit_payload = dict(base_payload)
        bad_commit_payload["published_commit"] = _published_commit(SHA, login="alice")
        bad_dec = maintenance.evaluate_automerge(bad_commit_payload, policy)
        self.assertFalse(bad_dec.eligible)
        self.assertIn("published-commit-author-login-mismatch", bad_dec.reason)

        # Mismatched producer check_run_url must fail closed via maintenance_common.verify_check_producers
        bad_prod_payload = dict(base_payload)
        bad_prod_payload["producer_evidence"] = {
            name: {
                "workflow": ".github/workflows/ci.yml",
                "job": name,
                "check_run_id": 100 + idx,
                "run_id": 500,
                "run_record_id": 500,
                "job_id": 200 + idx,
                "job_record_id": 200 + idx,
                "job_run_id": 500,
                "job_check_run_url": f"https://api.github.com/repos/{REPO}/check-runs/999999",
                "run_attempt": 1,
                "job_run_attempt": 1,
                "head_sha": SHA,
                "job_head_sha": SHA,
                "job_status": "completed",
                "job_conclusion": "success",
                "run_status": "completed",
                "run_conclusion": "success",
            }
            for idx, name in enumerate(policy["mandatory_check_names"])
        }
        bad_prod_dec = maintenance.evaluate_automerge(bad_prod_payload, policy)
        self.assertFalse(bad_prod_dec.eligible)
        self.assertIn("producer-check-run-id-mismatch", bad_prod_dec.reason)

    def test_emit_validation_and_publication_notices_round_trip(self) -> None:
        val_notice = maintenance.emit_validation_notice(
            ROOT,
            candidate="3.14.9",
            source_head="b" * 40,
            run_id=77,
            run_attempt=1,
            interpreter="3.14.9",
            pip_version="26.1.1",
            pip_tools_version="7.5.3",
        )
        parsed_val = maintenance_common.parse_notice(
            val_notice, maintenance_common.VALIDATION_NOTICE
        )
        self.assertIsNotNone(parsed_val)
        assert parsed_val is not None
        self.assertEqual(parsed_val["pip"], "26.1.1")
        self.assertEqual(parsed_val["pip_tools"], "7.5.3")
        self.assertIn(".python-version", parsed_val["digests"])
        self.assertIn("ruff.toml", parsed_val["digests"])

        with self.assertRaises(ValueError):
            maintenance.emit_validation_notice(
                ROOT,
                candidate="3.14.9",
                source_head="b" * 40,
                run_id=77,
                run_attempt=1,
                interpreter="3.14.9",
                pip_version="25.0.0",
                pip_tools_version="7.5.3",
            )

        if (
            maintenance._distribution_version("pip") == "26.1.1"
            and maintenance._distribution_version("pip-tools") == "7.5.3"
        ):
            auto_val_notice = maintenance.emit_validation_notice(
                ROOT,
                candidate="3.14.9",
                source_head="b" * 40,
                run_id=77,
                run_attempt=1,
                interpreter="3.14.9",
            )
            self.assertIsNotNone(
                maintenance_common.parse_notice(
                    auto_val_notice, maintenance_common.VALIDATION_NOTICE
                )
            )

        pub_notice = maintenance.emit_publication_notice(
            ROOT,
            pull_number=52,
            published_head=SHA,
            branch="chore/python-bump",
            pr_author="github-actions[bot]",
            run_id=77,
            run_attempt=1,
        )
        parsed_pub = maintenance_common.parse_notice(
            pub_notice, maintenance_common.PUBLICATION_NOTICE
        )
        self.assertIsNotNone(parsed_pub)
        assert parsed_pub is not None
        self.assertEqual(parsed_pub["pull_number"], 52)
        self.assertEqual(parsed_pub["published_head"], SHA)


if __name__ == "__main__":
    unittest.main()
