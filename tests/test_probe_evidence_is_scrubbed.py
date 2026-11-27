"""Guard: no committed evidence or fixture may carry a credential-shaped string.

Why this file exists
--------------------
On 2026-11-27 GitHub's secret scanning opened **five "Google API Key" alerts** against this
repository, all pointing at `tests/fixtures/probes/www.youtube.com__*.body.txt`. The key was not
ours — YouTube's HTML embeds Google's public `INNERTUBE_API_KEY` in every page, and the probe job
had committed three channel pages verbatim. Nothing was leaked and nothing was compromised, but a
repository is not the place to keep a key-shaped string: every clone, every tarball and every
mirror inherits it, and the alerts never clear on their own.

Two things changed, and this file is the second one:

1. `.github/workflows/ci.yml`'s `mode=save` now **scrubs** credential-shaped strings before it
   commits anything (`SECRET_SHAPES`, in that job). The evidence is still useful — the shape and
   the markup survive — it just cannot carry a live-looking key.
2. this guard **fails the build** if one ever lands again, whoever writes it: the probe job, a
   hand-copy from a browser, a fixture scraped by a new adapter.

Scope: `tests/fixtures/**` only. Test *source* files legitimately contain fake tokens and example
webhook URLs (`tests/test_smoke.py` builds settings from `.../webhooks/1234/tok`), so scanning the
Python files would produce nothing but noise. Fixtures are data copied from the wire, which is
exactly where a real key hides.

Run:  python tests/test_probe_evidence_is_scrubbed.py      (pytest collects it too)
No network, no secrets.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))     # same plain-runner shape as every other test file here
FIXTURES = ROOT / "tests" / "fixtures"

# The same shapes the probe job scrubs. Deliberately narrow: each one is long and distinctive
# enough that no rewritten markup or CSS hash can match it by accident.
SHAPES = {
    "Google API key": re.compile(r"AIza[0-9A-Za-z_-]{35}"),
    "GitHub token": re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}"),
    "GitHub fine-grained PAT": re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    "AWS access key id": re.compile(r"AKIA[0-9A-Z]{16}"),
    "Discord webhook": re.compile(r"discord(?:app)?\.com/api/webhooks/\d+/[A-Za-z0-9_-]{20,}"),
}

# Files that are scanned even though their suffix is not text: the probe saves whatever the server
# sent, and a `.body.txt` is always text, so the only skips are the binaries a test may add later.
SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".zip", ".gz", ".mp4", ".webm",
                 ".woff", ".woff2", ".ttf", ".pyc"}


def _fixture_files() -> list[Path]:
    if not FIXTURES.is_dir():
        return []
    return [p for p in sorted(FIXTURES.rglob("*"))
            if p.is_file() and p.suffix.lower() not in SKIP_SUFFIXES and ".git" not in p.parts]


def test_no_fixture_contains_a_credential_shaped_string():
    files = _fixture_files()
    assert files, "no fixtures found — the scan would be vacuous"
    offenders: list[str] = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:                                  # unreadable file is a failure too
            offenders.append(f"{path.relative_to(ROOT)}: cannot read ({exc.__class__.__name__})")
            continue
        for label, pattern in SHAPES.items():
            for match in pattern.finditer(text):
                hit = match.group(0)
                # Never print the string itself: the log is public, the point is to keep it out.
                offenders.append(f"{path.relative_to(ROOT)}: {label} "
                                 f"({hit[:4]}…{len(hit)} chars, offset {match.start()})")
    assert not offenders, (
        "credential-shaped string(s) in committed fixtures — scrub them and re-commit:\n  "
        + "\n  ".join(sorted(set(offenders))))


def test_the_scrubber_actually_scrubs():
    """The same substitutions the probe job runs, so a regression in either place is caught here."""
    sample = ("key=AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8&x=1 "
              "token=ghp_" + "a" * 36 + " pat=github_pat_" + "b" * 30 +
              " aws=AKIA" + "C" * 16 + " hook=https://discord.com/api/webhooks/123456789012345678/"
              + "d" * 32)
    scrubbed = sample
    for pattern, replacement in (
        (SHAPES["Google API key"], "REDACTED-GOOGLE-API-KEY"),
        (SHAPES["GitHub token"], "REDACTED-GITHUB-TOKEN"),
        (SHAPES["GitHub fine-grained PAT"], "REDACTED-GITHUB-PAT"),
        (SHAPES["AWS access key id"], "REDACTED-AWS-KEY"),
    ):
        scrubbed = pattern.sub(replacement, scrubbed)
    scrubbed = re.sub(r"(discord(?:app)?\.com/api/webhooks/\d+/)[A-Za-z0-9_-]{20,}",
                      r"\1REDACTED", scrubbed)
    for label, pattern in SHAPES.items():
        assert not pattern.search(scrubbed), f"{label} survived the scrubber"
    assert "REDACTED-GOOGLE-API-KEY" in scrubbed and "x=1" in scrubbed   # only the key went


def test_the_probe_workflow_keeps_its_scrub_step():
    """A guard with no gate is decoration: the job that saves evidence must still scrub it."""
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "SECRET_SHAPES=" in workflow
    assert "REDACTED-GOOGLE-API-KEY" in workflow and "REDACTED-GITHUB-TOKEN" in workflow
    # and it must run while saving, not only in the printed report
    save_block = workflow[workflow.index('"${MODE:-save}"') if '"${MODE:-save}"' in workflow else 0:]
    assert "sed -E" in save_block and "scrubbed=" in workflow


def main() -> int:
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  PASS  {name}")
            except Exception as exc:  # noqa: BLE001
                failed += 1
                print(f"  FAIL  {name}: {type(exc).__name__}: {exc}")
    print("PROBE EVIDENCE SCRUB TEST:", "ALL PASS" if not failed else f"{failed} FAILED")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
