"""Supervise the explicitly authorized private historical test, never post directly.

Dispatches only the fixed private-test workflow, one run at a time. The remote
journals are authoritative. Any unknown status, source hold, lost journal or lack
of progress stops the supervisor; it never repeats a failed or ambiguous run.
"""
from __future__ import annotations

import subprocess
import time

import candidate_private_backfill as test

from gamexpress import candidate_news_delivery as delivery

EXPECTED = {"nte": 103, "endfield": 143, "silverpalace": 21}
WORKFLOW = "source_research_probe.yml"


def command(*args, timeout=50):
    try:
        result = subprocess.run(list(args), stdin=subprocess.DEVNULL, capture_output=True,
                                timeout=timeout, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError("command outcome not confirmed") from exc
    if result.returncode:
        raise ValueError("command outcome not confirmed")
    return result.stdout


def status():
    posted = pending = pages = 0
    for source in test.SOURCES:
        comment = test.gh_api(f"repos/{test.REPOSITORY}/issues/comments/{test.COMMENT_IDS[source]}")
        state = test.check_comment(comment, source, test.COMMENT_IDS[source])
        state = delivery._validate(state, source, state.get("route"))
        if len(state["posted"]) + len(state["pending"]) != EXPECTED[source]:
            raise ValueError("historic snapshot count changed")
        partial = state["partial"]
        if partial and partial["inflight"]:
            raise ValueError("an in-flight page requires inspection")
        posted += len(state["posted"])
        pending += len(state["pending"])
        pages += len(partial["messages"]) if partial else 0
    return posted, pending, pages


def runs():
    result = test.gh_api(f"repos/{test.REPOSITORY}/actions/workflows/{WORKFLOW}/runs?branch={test.BRANCH}&event=workflow_dispatch&per_page=40")
    rows = result.get("workflow_runs") if isinstance(result, dict) else None
    if not isinstance(rows, list):
        raise ValueError("run listing unavailable")
    return {row["id"]: row for row in rows if isinstance(row, dict) and type(row.get("id")) is int}


def current_head():
    ref = f"refs/heads/{test.BRANCH}"
    output = command("git", "ls-remote", "--heads", "origin", ref).decode().splitlines()
    if len(output) != 1:
        raise ValueError("branch head unavailable")
    fields = output[0].split()
    if len(fields) != 2 or fields[1] != ref:
        raise ValueError("branch head invalid")
    return fields[0]


def watch(run_id):
    command("gh", "run", "watch", str(run_id), "--exit-status", timeout=1200)
    result = test.gh_api(f"repos/{test.REPOSITORY}/actions/runs/{run_id}/jobs?per_page=100")
    jobs = result.get("jobs") if isinstance(result, dict) else None
    selected = [job for job in jobs or [] if job.get("name") == "Private Feature 3 historical test"]
    if len(selected) != 1 or selected[0].get("conclusion") != "success":
        raise ValueError("historic batch did not complete successfully")


def run():
    expected_head = current_head()
    if expected_head != command("git", "rev-parse", "HEAD").decode().strip():
        raise ValueError("local branch does not match remote")
    before = status()
    print(f"Starting with {before[0]} confirmed articles and {before[1]} remaining.", flush=True)
    batches = 0
    while before[1]:
        if current_head() != expected_head:
            raise ValueError("branch changed during private test")
        if batches >= 300:
            raise ValueError("private test batch bound reached")
        known = set(runs())
        command("gh", "workflow", "run", WORKFLOW, "--ref", test.BRANCH, "-f", "scope=candidate-historic-send")
        new = []
        for _ in range(20):
            new = [row for ident, row in runs().items() if ident not in known
                   and row.get("head_sha") == expected_head and row.get("event") == "workflow_dispatch"]
            if new:
                break
            time.sleep(3)
        if len(new) != 1:
            raise ValueError("dispatched run identity is ambiguous")
        run_id = new[0]["id"]
        print(f"Batch {batches + 1}: https://github.com/{test.REPOSITORY}/actions/runs/{run_id}", flush=True)
        watch(run_id)
        after = status()
        if after[0] < before[0] or after[1] > before[1] or (after[0] == before[0] and after[2] <= before[2]):
            raise ValueError("journal made no confirmed forward progress")
        batches += 1
        print(f"Confirmed articles: {after[0]}; remaining: {after[1]}; partial pages: {after[2]}.", flush=True)
        before = after
    print("Private historic test complete: 267 articles confirmed. Production state unchanged.", flush=True)


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:  # noqa: BLE001 — do not expose remote responses or credentials
        print(f"Private test stopped safely ({type(exc).__name__}); inspect its last run and journal before continuing.", flush=True)
        raise SystemExit(1) from None
