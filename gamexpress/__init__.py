"""Game-Express — gacha livestream schedule & redemption-code monitor for Discord."""

from __future__ import annotations

import os


def build_id() -> str:
    """Short commit hash of the running checkout (`702c9bd`), or `'local'` outside Actions."""
    code_sha = os.environ.get("GAMEXPRESS_CODE_SHA", "").strip()[:7]
    if code_sha:
        return code_sha
    return os.environ.get("GITHUB_SHA", "").strip()[:7] or "local"
