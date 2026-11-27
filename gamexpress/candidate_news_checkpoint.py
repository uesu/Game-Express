"""Experimental Git checkpoint for candidate-news write-ahead state.

Each successful call saves state/state.json, creates a state-only commit and pushes
it to the SAME checked-out branch, then verifies the remote ref. An ahead/behind
branch, a dirty index, any failed/ambiguous Git operation or an unexpected state
path fails closed. This alone does not provide cross-repository failover locking.
"""
from __future__ import annotations

import asyncio
import copy
import json
import subprocess
from pathlib import Path

from .candidate_news_delivery import SOURCES, _validate


class GitCheckpoint:
    """Async checkpoint callback for one source; no caller may POST unless it returns True."""

    def __init__(self, root: Path, state, source: str, branch: str):
        self.root = root.resolve()
        self.state = state
        self.source = source
        self.branch = branch

    def _git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root, stdin=subprocess.DEVNULL,
                              capture_output=True, timeout=30, check=False)

    def _head(self):
        result = self._git("rev-parse", "--verify", "HEAD")
        return result.stdout.strip() if result.returncode == 0 else None

    def _remote_head(self):
        result = self._git("ls-remote", "--heads", "origin", f"refs/heads/{self.branch}")
        lines = result.stdout.splitlines()
        if result.returncode != 0 or len(lines) != 1:
            return None
        parts = lines[0].split()
        return parts[0] if len(parts) == 2 and parts[1] == f"refs/heads/{self.branch}".encode() else None

    def _save(self, snapshot):
        try:
            if (self.source not in SOURCES or not isinstance(snapshot, dict)
                    or self.state.path.resolve() != self.root / "state/state.json"
                    or not self.branch or not isinstance(self.branch, str)):
                return False
            _validate(snapshot, self.source, snapshot.get("route"))
            current = self._git("symbolic-ref", "--quiet", "--short", "HEAD")
            valid = self._git("check-ref-format", "--branch", self.branch)
            if (current.returncode != 0 or current.stdout.strip() != self.branch.encode() or valid.returncode != 0
                    or self._git("diff", "--cached", "--quiet").returncode != 0):
                return False
            head = self._head()
            if head is None or self._remote_head() != head:
                return False
            # State.load can recover a corrupt/missing file by constructing an empty
            # state. Never treat that as a fresh backlog: compare all candidate records
            # against the committed, authoritative JSON before modifying anything.
            committed_blob = self._git("show", "HEAD:state/state.json")
            if committed_blob.returncode != 0:
                return False
            committed = json.loads(committed_blob.stdout)
            if not isinstance(committed, dict):
                return False
            remote_records = committed.get("candidate_news", {})
            records = self.state.data.get("candidate_news", {})
            if (not isinstance(remote_records, dict) or not isinstance(records, dict)
                    or records != remote_records):
                return False
            self.state.data["candidate_news"] = records
            records[self.source] = copy.deepcopy(snapshot)
            self.state.save()
            if self._git("add", "--", "state/state.json").returncode != 0:
                return False
            staged = self._git("diff", "--cached", "--name-only", "-z")
            if staged.returncode != 0 or set(filter(None, staged.stdout.split(b"\0"))) - {b"state/state.json"}:
                return False
            if staged.stdout:
                commit = self._git("-c", "user.name=github-actions[bot]",
                                   "-c", "user.email=41898282+github-actions[bot]@users.noreply.github.com",
                                   "commit", "-m", "auto: checkpoint candidate news [skip ci]")
                if commit.returncode != 0:
                    return False
                pushed = self._git("push", "origin", f"HEAD:refs/heads/{self.branch}")
                if pushed.returncode != 0:
                    return False
            head = self._head()
            return head is not None and self._remote_head() == head
        except (OSError, ValueError, TypeError, subprocess.SubprocessError):
            return False

    async def __call__(self, snapshot):
        return await asyncio.to_thread(self._save, snapshot)
