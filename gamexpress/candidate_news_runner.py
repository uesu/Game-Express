"""Opt-in, conservative candidate news backfill path; disabled unless explicitly configured.

Only single-instance Actions environments are permitted. Each page requires a
verified same-branch Git checkpoint and a one-shot POST. Unknown outcomes hold.
This path is not activated by adding a game to NEWS_GAMES alone.
"""
from __future__ import annotations

import asyncio
import os

from . import candidate_news_delivery as delivery
from .candidate_news_checkpoint import GitCheckpoint
from .config import ROOT

# A release gate, not a configuration flag. No production posts until the
# end-of-job persistence/rebase and multi-instance failure paths are reviewed.
CANDIDATE_NEWS_READY = False

# Backfill is intentionally slow: at most one article / three pages per source per run.
MAX_PAGES_PER_SOURCE_RUN = 3


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
    if settings.instance_role != "primary" or settings.peer_state_url:
        ctx.warnings.append("Candidate news: single-instance primary only; peer/failover integration is not ready")
        return
    branch = os.environ.get("GITHUB_REF_NAME", "")
    if os.environ.get("GITHUB_ACTIONS") != "true" or not branch:
        ctx.warnings.append("Candidate news: durable Actions branch checkpoint unavailable; no posts")
        return
    records = ctx.state.data.get("candidate_news", {})
    if not isinstance(records, dict):
        ctx.warnings.append("Candidate news: invalid stored state; no posts")
        return

    for source in selected:
        target = delivery.destination(settings, source)
        if target is None:
            ctx.warnings.append(f"{source} news: dedicated destination missing or invalid; no discovery or posts")
            continue
        _, fingerprint = target
        try:
            # Validate existing route/state before any source requests.
            prior = records.get(source)
            if prior is not None:
                delivery._validate(prior, source, fingerprint)
            rows = await delivery.discover(ctx.fetcher, source)
            state = delivery.ingest(source, fingerprint, prior, rows)
            if not state["pending"]:
                ctx.report.append(f"{source} news: caught up ({len(state['posted'])} recorded)")
                continue
            checkpoint = GitCheckpoint(ROOT, ctx.state, source, branch)

            async def render(row, *, _source=source):
                return await delivery.render_candidate(ctx.fetcher, settings, _source, row)

            async def send(payload, *, _source=source):
                # Git checkpoints usually exceed this delay, but never rely on that for pacing.
                await asyncio.sleep(1.5)
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
