"""Opt-in, conservative candidate news backfill path; disabled unless explicitly configured.

Only the explicitly nominated primary GitHub repository and branch may send.
Standbys never send candidate news automatically. Each page requires a verified
same-branch Git checkpoint and a one-shot POST. Unknown outcomes hold.
This path is not activated by adding a game to NEWS_GAMES alone.
"""
from __future__ import annotations

import asyncio
import os
import re
import subprocess
from urllib.parse import urlsplit

from . import candidate_news_delivery as delivery
from .candidate_news_checkpoint import IsolatedGitLedger
from .config import ROOT

# A release gate, not a configuration flag. No production posts until the
# end-of-job persistence/rebase and multi-instance failure paths are reviewed.
CANDIDATE_NEWS_READY = False

# Backfill is intentionally slow: at most one article / three pages per source per run.
MAX_PAGES_PER_SOURCE_RUN = 3


def _origin_is_authority(root, repository):
    """Require the checkout's actual origin to be the nominated GitHub repository."""
    try:
        result = subprocess.run(["git", "remote", "get-url", "origin"], cwd=root, stdin=subprocess.DEVNULL,
                                capture_output=True, timeout=10, check=False)
        url = result.stdout.decode("utf-8").strip()
        parts = urlsplit(url)
        return (result.returncode == 0 and parts.scheme == "https" and parts.hostname == "github.com"
                and not parts.username and not parts.password and parts.port in (None, 443)
                and not parts.query and not parts.fragment
                and parts.path.removeprefix("/").removesuffix(".git").lower() == repository.lower())
    except (OSError, ValueError, UnicodeError, subprocess.SubprocessError):
        return False


def authoritative_branch(settings, root):
    """Return only an explicitly designated primary Actions branch; no auto-failover."""
    repository = str(settings.env.get("NEWS_CANDIDATES_AUTHORITY_REPOSITORY", "") or "").strip()
    branch = str(settings.env.get("NEWS_CANDIDATES_AUTHORITY_BRANCH", "") or "").strip()
    if (settings.instance_role != "primary" or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository)
            or not branch or os.environ.get("GITHUB_ACTIONS") != "true"
            or os.environ.get("GITHUB_EVENT_NAME") not in ("workflow_dispatch", "schedule")
            or os.environ.get("GITHUB_REPOSITORY", "").lower() != repository.lower()
            or os.environ.get("GITHUB_REF_NAME", "") != branch
            or os.environ.get("GITHUB_REF", "") != f"refs/heads/{branch}"
            or not _origin_is_authority(root, repository)):
        return None
    return branch


async def run_candidate_news(ctx):
    settings = ctx.settings
    if (not ctx.active or "news" not in settings.features or not settings.news_enabled
            or settings.env.get("NEWS_CANDIDATES_BACKFILL", "").strip() != "1"):
        return
    selected = sorted(delivery.SOURCES & settings.news_games)
    if settings.games_filter:
        selected = [source for source in selected if source in settings.games_filter]
    if not selected:
        return
    if not CANDIDATE_NEWS_READY:
        ctx.warnings.append("Candidate news: delivery is not released; no discovery or posts")
        return
    if settings.dry_run or settings.test_mode:
        ctx.report.append("Candidate news: live backfill disabled in dry-run/test mode")
        return
    branch = authoritative_branch(settings, ROOT)
    if branch is None:
        ctx.warnings.append("Candidate news: explicit primary repository/branch authority unavailable; no posts")
        return
    ledger = IsolatedGitLedger(ROOT, branch)
    if not await ledger.open():
        ctx.warnings.append("Candidate news: authoritative ledger unavailable or stale; no posts")
        return
    try:
        for source in selected:
            if ledger.poisoned:
                ctx.warnings.append("Candidate news: checkpoint failed; remaining sources held")
                break
            target = delivery.destination(settings, source)
            if target is None:
                ctx.warnings.append(f"{source} news: dedicated destination missing or invalid; no discovery or posts")
                continue
            _, fingerprint = target
            try:
                # Read each record from the separately checkpointed authoritative ledger.
                prior = ledger.data["candidate_news"].get(source)
                if prior is not None:
                    delivery._validate(prior, source, fingerprint)
                rows = await delivery.discover(ctx.fetcher, source)
                state = delivery.ingest(source, fingerprint, prior, rows)
                if not state["pending"]:
                    ctx.report.append(f"{source} news: caught up ({len(state['posted'])} recorded)")
                    continue

                animation_assets = {}

                async def checkpoint(snapshot, *, _source=source):
                    return await ledger.checkpoint(_source, snapshot)

                async def render(row, *, _source=source, _assets=animation_assets):
                    pages, files = await delivery.render_candidate_animated(ctx.fetcher, settings, _source, row)
                    _assets.clear()
                    _assets.update(files)
                    return pages

                async def send(payload, *, _source=source, _assets=animation_assets):
                    # Git checkpoints usually exceed this delay, but never rely on that for pacing.
                    await asyncio.sleep(1.5)
                    attachments = payload.get("attachments") or []
                    if attachments:
                        files = {entry["filename"]: _assets[entry["filename"]] for entry in attachments}
                        return await delivery.send_candidate_once(ctx.webhook.session, settings, _source, payload, files=files)
                    return await delivery.send_candidate_once(ctx.webhook.session, settings, _source, payload)

                state = await delivery.deliver_oldest(state, source, fingerprint, as_of=ctx.now,
                                                      checkpoint=checkpoint, render=render, send=send,
                                                      max_pages=MAX_PAGES_PER_SOURCE_RUN)
                pages = len(state["partial"]["messages"]) if state["partial"] else 0
                ctx.report.append(f"{source} news: queued={len(state['pending'])} recorded={len(state['posted'])} "
                                  f"partial-pages={pages}")
            except Exception as exc:  # noqa: BLE001 — hold this source without affecting unrelated news
                # Never interpolate exceptions: HTTP clients can include secret URLs.
                ctx.warnings.append(f"{source} news: held ({type(exc).__name__}); inspect before retry")
    finally:
        await ledger.close()
