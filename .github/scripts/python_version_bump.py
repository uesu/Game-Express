"""Checks for a newer STABLE Python minor series and, if one exists, bumps the two
workflow files (+ ruff.toml, when Ruff already understands that target) in place.

Used by .github/workflows/python_version_bump.yml. Dependabot cannot do this job: the
Python interpreter version is a `python-version:` string inside workflow YAML, not a
tracked dependency file (see docs/DEPENDABOT.md and docs/PYTHON_VERSION.md).

Source of truth: actions/python-versions' versions-manifest.json — the EXACT list
actions/setup-python itself downloads from. Anything this script proposes is therefore
already installable on the runner the moment the PR opens; nothing is guessed.

Writes GitHub Actions outputs (changed, old_version, new_version, ruff_bumped) and a
PR body to $PR_BODY_PATH. Never raises on a network hiccup: it just skips this week's
check (changed=false) so a flaky connection can't turn into a failed scheduled run —
next Monday tries again.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
WORKFLOW_FILES = [
    os.path.join(ROOT, ".github", "workflows", "ci.yml"),
    os.path.join(ROOT, ".github", "workflows", "monitor.yml"),
]
RUFF_TOML = os.path.join(ROOT, "ruff.toml")
MANIFEST_URL = "https://raw.githubusercontent.com/actions/python-versions/main/versions-manifest.json"
PIN_RE = re.compile(r"(python-version:\s*')(\d+\.\d+)(')")
RUFF_TARGET_RE = re.compile(r'(target-version\s*=\s*")py(\d+)(")')


def _out(key: str, value: str) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    line = f"{key}={value}\n"
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line)
    else:
        print(line, end="")


def current_pin() -> tuple[int, int] | None:
    with open(WORKFLOW_FILES[0], encoding="utf-8") as fh:
        text = fh.read()
    m = PIN_RE.search(text)
    if not m:
        return None
    major, minor = m.group(2).split(".")
    return int(major), int(minor)


def fetch_manifest() -> list[dict] | None:
    req = urllib.request.Request(MANIFEST_URL, headers={"User-Agent": "Game-Express-python-bump"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        print(f"::warning::could not read {MANIFEST_URL}: {e} — skipping this week's check")
        return None


def highest_stable_minor(manifest: list[dict]) -> tuple[tuple[int, int], str] | None:
    """-> ((major, minor), full 'X.Y.Z' of the newest patch) for the newest STABLE CPython 3.x
    series that has a Linux build (what ci.yml / monitor.yml actually run on)."""
    best: tuple[int, int] | None = None
    best_full = ""
    for entry in manifest:
        if not entry.get("stable"):
            continue
        version = str(entry.get("version") or "")
        parts = version.split(".")
        if len(parts) < 3 or not all(p.isdigit() for p in parts[:3]):
            continue
        major, minor = int(parts[0]), int(parts[1])
        if major != 3:
            continue
        if not any((f.get("platform") or "").lower() == "linux" for f in entry.get("files") or []):
            continue
        key = (major, minor)
        if best is None or key > best or (key == best and version > best_full):
            best, best_full = key, version
    return (best, best_full) if best else None


def ruff_understands(target: str) -> bool:
    """True when the installed ruff accepts --target-version <target> (it rejects an
    unknown target with a usage error, exit code 2)."""
    try:
        proc = subprocess.run(["ruff", "check", "--target-version", target, "--no-cache", RUFF_TOML],
                              capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError) as e:
        print(f"::warning::could not run ruff to validate target-version {target}: {e}")
        return False
    return proc.returncode != 2 and "invalid value" not in (proc.stderr or "").lower()


def bump_workflow_files(new_minor: str) -> None:
    for path in WORKFLOW_FILES:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        new_text = PIN_RE.sub(rf"\g<1>{new_minor}\g<3>", text)
        if new_text != text:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(new_text)


def bump_ruff_toml(new_major: int, new_minor: int) -> bool:
    target = f"py{new_major}{new_minor}"
    if not ruff_understands(target):
        print(f"::warning::ruff does not recognise --target-version {target} yet — "
              "leaving ruff.toml unchanged; bump it separately once ruff adds support")
        return False
    with open(RUFF_TOML, encoding="utf-8") as fh:
        text = fh.read()
    new_text = RUFF_TARGET_RE.sub(rf"\g<1>py{new_major}{new_minor}\g<3>", text)
    if new_text != text:
        with open(RUFF_TOML, "w", encoding="utf-8") as fh:
            fh.write(new_text)
        return True
    return False


def write_body(old: str, new: str, new_full: str, ruff_bumped: bool) -> None:
    ruff_line = ("- `ruff.toml` `target-version` bumped to match (`ruff` already understands it)."
                if ruff_bumped else
                "- `ruff.toml` **left unchanged** — the installed `ruff` doesn't recognise this "
                "target yet; bump it in a follow-up once a new `ruff` release adds support.")
    body = f"""### Automated Python version bump: {old} → {new}

Opened by `.github/workflows/python_version_bump.yml`, which runs weekly and compares the
pinned `python-version:` against [`actions/python-versions`'s own release manifest]({MANIFEST_URL})
— the exact list `actions/setup-python` downloads from. **{new_full}** is marked `stable` there
with a Linux build, so it is already installable on this repo's runners today.

- `ci.yml` and `monitor.yml`: `python-version: '{old}'` → `'{new}'`.
{ruff_line}
- **Everything was already proved green BEFORE this PR existed**, under the **new** interpreter:
  every dependency installed from a prebuilt wheel (`--only-binary=:all:`), then `compileall` +
  `validate` + the offline suite + the preview render. `ci.yml` also runs on this PR normally —
  it is opened with a personal access token, so workflow triggers fire — but that check arrives
  after the fact; the gate inside the bump job is what decided this PR was worth opening.
- **This PR does not merge itself by default.** It merges automatically only if the repository
  variable `AUTO_MERGE_PYTHON_BUMP` is set to **`all`**. `yes` deliberately does *not* merge a
  series bump in this repo — so leaving it at `yes`, or unset, means this one waits for you.
- Patch releases within the `{new}` series (e.g. the next bugfix release) need no further PRs —
  pinning the minor only (not the full `X.Y.Z`) means the runner always picks the newest patch.
- The **next** minor bump after this one will need another PR like this one; Python ships a new
  minor series roughly every October.
"""
    path = os.environ.get("PR_BODY_PATH", "/tmp/python_bump_body.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)


def main() -> int:
    pin = current_pin()
    if pin is None:
        print("::warning::could not find a python-version pin in ci.yml — skipping")
        _out("changed", "false")
        return 0
    old_str = f"{pin[0]}.{pin[1]}"
    # Known from here on. Emit it now so every run reports the pin — including the
    # "up to date" and manifest-failure paths, where it is the only useful fact.
    _out("old_version", old_str)
    manifest = fetch_manifest()
    if manifest is None:
        _out("changed", "false")
        return 0
    hit = highest_stable_minor(manifest)
    if hit is None:
        print("::warning::manifest had no stable Linux CPython 3.x build — skipping")
        _out("changed", "false")
        return 0
    (new_major, new_minor), new_full = hit
    new_str = f"{new_major}.{new_minor}"
    if (new_major, new_minor) <= pin:
        print(f"up to date: {old_str} is already the newest stable series ({new_str} <= {old_str})")
        _out("changed", "false")
        return 0
    print(f"bumping {old_str} -> {new_str} (newest stable patch: {new_full})")
    bump_workflow_files(new_str)
    ruff_bumped = bump_ruff_toml(new_major, new_minor)
    write_body(old_str, new_str, new_full, ruff_bumped)
    _out("changed", "true")
    _out("new_version", new_str)
    _out("ruff_bumped", "true" if ruff_bumped else "false")
    return 0


if __name__ == "__main__":
    sys.exit(main())
