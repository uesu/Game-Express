"""Read-only application completion summaries; no maintenance or posting logic."""
from __future__ import annotations

import asyncio
import functools
import html
import logging
import os
import re
import time
from contextvars import ContextVar

_log = logging.getLogger(__name__)
_current = ContextVar("application_summary", default=None)


def safe_text(value):
    text = str(value)
    for name, secret in os.environ.items():
        if len(secret) >= 8 and re.search(r"TOKEN|SECRET|PASSWORD|WEBHOOK|API_KEY", name, re.I):
            text = text.replace(secret, "[REDACTED]")
    text = re.sub(r"https?://[^\s/]*(?:discord(?:app)?\.com)/api/webhooks/[^\s<>]+",
                  "[REDACTED_WEBHOOK]", text, flags=re.I)
    text = re.sub(r"([?&](?:token|feed|key|api_key|access_token)=)[^&\s<>]+",
                  r"\1[REDACTED]", text, flags=re.I)
    text = re.sub(r"(Bearer\s+)[^\s<>]+", r"\1[REDACTED]", text, flags=re.I)
    return html.escape(text.replace("\r", " ").replace("\n", " "), quote=False).replace("`", "'")[:1200]


def annotation(value):
    return safe_text(value).replace("%", "%25")


def observe_feed(entries):
    """Count selected feed returns, not HTTP requests, unique posts or delivery."""
    record = _current.get()
    if record is not None:
        record["feed_returns"] += 1
        count = max(0, int(entries))
        record["usable_feeds"] += int(count > 0)
        record["entries_observed"] += count


def _emit(record):
    lines = [f"### {record['name']} — application completion",
             f"- Outcome: {record['outcome']}",
             f"- Configured targets: {record['configured']}",
             f"- Elapsed application time: {record['elapsed']:.3f}s"]
    if record["feed_returns"]:
        lines.append(f"- Selected-feed observations: {record['feed_returns']}; "
                     f"usable: {record['usable_feeds']}; entries observed: {record['entries_observed']}")
    else:
        lines.append("- Feed observations: unavailable (not measured on this path)")
    if record.get("exception_type"):
        lines.append(f"- Exception type: {record['exception_type']} (original exception re-raised)")
    lines.extend(["- Posting counts and source health: see the existing per-item/source logs; not inferred here.",
                  "- Repository commit/push status: not observed by this application summary."])
    text = "\n".join(safe_text(line) for line in lines) + "\n"
    _log.info("Application completion: %s", safe_text(record["outcome"]))
    destination = os.environ.get("GITHUB_STEP_SUMMARY")
    if destination:
        try:
            with open(destination, "a", encoding="utf-8") as stream:
                stream.write(text)
        except Exception as exc:
            _log.warning("Application summary output unavailable (%s)", type(exc).__name__)


def summarize_run(name, configured=None):
    """Observe completion without retries, posting, state writes or changed returns."""
    def decorate(function):
        @functools.wraps(function)
        async def wrapped(*args, **kwargs):
            started = time.monotonic()
            record = dict(name=name, configured="unknown", outcome="started",
                          feed_returns=0, usable_feeds=0, entries_observed=0)
            if configured is not None:
                try:
                    record["configured"] = int(configured())
                except Exception:
                    pass
            token = _current.set(record)
            try:
                result = await function(*args, **kwargs)
                record["outcome"] = "returned normally (not a delivery/source-health guarantee)"
                if record["configured"] == 0:
                    record["outcome"] = "not configured (no targets)"
                elif record["feed_returns"] and not record["usable_feeds"]:
                    record["outcome"] = "no usable feeds observed (existing fallback behavior preserved)"
                if hasattr(result, "games"):
                    record["configured"] = len(result.games)
                    if result.errors:
                        record["outcome"] = "returned with reported application errors"
                    elif not result.active:
                        record["outcome"] = "passive standby (not an active posting run)"
                    elif not result.settings.features:
                        record["outcome"] = "features disabled (not an active posting run)"
                    if result.settings.dry_run:
                        record["outcome"] += "; dry run"
                    elif result.settings.test_mode:
                        record["outcome"] += "; test mode"
                return result
            except asyncio.CancelledError:
                record["outcome"] = "cancelled"
                raise
            except Exception as exc:
                record["outcome"] = "raised an application exception"
                record["exception_type"] = type(exc).__name__
                raise
            finally:
                record["elapsed"] = time.monotonic() - started
                try:
                    _emit(record)
                except Exception:
                    # Reporting must not replace an application's return/exception.
                    _log.warning("Application summary could not be rendered")
                finally:
                    _current.reset(token)
        return wrapped
    return decorate
