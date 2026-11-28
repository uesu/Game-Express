"""No-send shared-ledger failover probe using two real GitHub repositories.

A read-only News-Express clone simulates a standby Actions checkout; GitHub Actions
identity and heartbeat activation are simulated in-process. Only a synthetic ledger
on the current Game-Express development branch is ever written.
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gamexpress import candidate_news_delivery as delivery  # noqa: E402
from gamexpress import candidate_news_runner as runner  # noqa: E402
from gamexpress.candidate_news_checkpoint import IsolatedGitLedger  # noqa: E402
from gamexpress.cards import news_payloads  # noqa: E402
from gamexpress.config import Game, load_settings  # noqa: E402
from gamexpress.models import Item  # noqa: E402

BRANCH = "arena/98b5f4e1-game-express"
AUTHORITY = "uesu/Game-Express"
STANDBY = "uesu/News-Express"
LEDGER = "state/feature3-shared-failover-probe.json"
SOURCE = "silverpalace"
ARTICLE = "987654321"
HOOK = "https://discord.com/api/webhooks/111111111111111111/aaaaaaaaaaaaaaaaaaaa"


def git(root, *args):
    result = subprocess.run(["git", *args], cwd=root, stdin=subprocess.DEVNULL,
                            capture_output=True, timeout=90, check=False)
    if result.returncode:
        raise ValueError("Git operation not confirmed")
    return result.stdout


def guard():
    if (os.environ.get("GITHUB_REPOSITORY") != AUTHORITY or os.environ.get("GITHUB_REF_NAME") != BRANCH
            or os.environ.get("GITHUB_REF") != f"refs/heads/{BRANCH}"
            or os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
            or os.environ.get("GITHUB_RUN_ATTEMPT") != "1" or not os.environ.get("GH_TOKEN")):
        raise ValueError("wrong test context")


async def main():
    guard()
    print("::notice title=Standby probe::stage=context-ok", flush=True)
    settings = load_settings({"INSTANCE_ROLE": "standby", "NEWS_CANDIDATES_STANDBY_ENABLED": "1",
        "NEWS_CANDIDATES_AUTHORITY_REPOSITORY": AUTHORITY, "NEWS_CANDIDATES_AUTHORITY_BRANCH": BRANCH,
        "NEWS_CANDIDATES_STANDBY_REPOSITORY": STANDBY, "NEWS_CANDIDATES_STANDBY_BRANCH": "main",
        "NEWS_CANDIDATES_LEDGER_TOKEN": os.environ["GH_TOKEN"], "NEWS_CANDIDATES_BACKFILL": "1",
        "NEWS_GAMES": SOURCE, "DISCORD_WEBHOOK_NEWS_SILVERPALACE": HOOK, "NO_PING": "1"})
    route = delivery.destination(settings, SOURCE)[1]
    initial = delivery.ingest(SOURCE, route, None, [{"id": ARTICLE, "title": "Synthetic standby probe", "date": "2000-01-01"}])
    if json.loads(git(ROOT, "show", f"HEAD:{LEDGER}")) != {"schema": 1, "candidate_news": {SOURCE: initial}}:
        raise ValueError("probe already used or unexpected fixture")
    print("::notice title=Standby probe::stage=fixture-ok", flush=True)
    game = Game(key=SOURCE, name="Silver Palace", short="Silver", enabled=False, color=0)
    item = Item(source=SOURCE, game=SOURCE, id=ARTICLE, title="Synthetic standby probe",
                url=f"https://silverpalace.elementagames.com/en-us/newsDetail?id={ARTICLE}", text="",
                published_ts=0, article_blocks=[{"kind": "text", "text": "Synthetic; never sent."}])
    sends = []

    async def discover(fetcher, source):
        return [{"id": ARTICLE, "title": "Synthetic standby probe", "date": "2000-01-01"}]

    async def render(fetcher, conf, source, row):
        return news_payloads(game, item), {}

    async def fake_send(session, conf, source, payload):
        if sends:
            raise ValueError("unexpected repeat")
        git(ROOT, "fetch", "origin", BRANCH)
        state = json.loads(git(ROOT, "show", f"FETCH_HEAD:{LEDGER}"))["candidate_news"][SOURCE]
        if not state["partial"] or state["partial"]["inflight"] is not True:
            raise ValueError("remote intent not checkpointed")
        sends.append(True)
        return SimpleNamespace(ok=True, message_id="101", ambiguous=False)

    with tempfile.TemporaryDirectory(prefix="candidate-readonly-standby-") as tmp:
        standby_root = Path(tmp) / "standby"
        git(Path(tmp), "clone", "--quiet", "--depth=1", "--branch", "main",
            "https://github.com/uesu/News-Express.git", str(standby_root))
        print("::notice title=Standby probe::stage=standby-clone-ok", flush=True)
        before = git(standby_root, "rev-parse", "HEAD")
        IsolatedGitLedger.LEDGER = LEDGER
        fake_context = {"GITHUB_REPOSITORY": STANDBY, "GITHUB_REF_NAME": "main", "GITHUB_REF": "refs/heads/main"}
        def context():
            return SimpleNamespace(settings=settings, active=True, now=int(time.time()), fetcher=None,
                                   webhook=SimpleNamespace(session=None), report=[], warnings=[])
        with (patch.dict(os.environ, fake_context), patch.object(runner, "ROOT", standby_root),
              patch.object(runner, "CANDIDATE_NEWS_READY", True), patch.object(delivery, "discover", discover),
              patch.object(delivery, "render_candidate_animated", render),
              patch.object(delivery, "send_candidate_once", fake_send)):
            import re
            token_ok = bool(re.fullmatch(r"[!-~]{20,2048}", settings.env["NEWS_CANDIDATES_LEDGER_TOKEN"]))
            origin_ok = runner._origin_is_authority(standby_root, STANDBY)
            checkout_ok = runner._checkout_is_current(standby_root, "main")
            valid = runner.standby_authority(settings, standby_root) is not None
            print(f"::notice title=Standby probe::authority-check={valid} token-format={token_ok} origin={origin_ok} current={checkout_ok}", flush=True)
            first = context()
            await runner.run_candidate_news(first)
            if first.warnings:
                safe = first.warnings[0]
                allowed = ("Candidate news: explicit primary repository/branch authority unavailable; no posts",
                           "Candidate news: shared authority checkout unavailable; no posts",
                           "Candidate news: authoritative ledger unavailable or stale; no posts",
                           "silverpalace news: primary route not yet bound; standby held",
                           "silverpalace news: held (DeliveryHold); inspect before retry")
                print(f"::notice title=Standby probe::first-warning={allowed.index(safe) if safe in allowed else 'other'}", flush=True)
            second = context()
            await runner.run_candidate_news(second)
            print(f"::notice title=Standby probe::simulated-sends={len(sends)} second-warning={bool(second.warnings)}", flush=True)
            if first.warnings or second.warnings or len(sends) != 1:
                raise ValueError("standby simulation held or repeated")
        if git(standby_root, "rev-parse", "HEAD") != before or git(standby_root, "status", "--porcelain"):
            raise ValueError("read-only standby checkout changed")
    git(ROOT, "fetch", "origin", BRANCH)
    final = json.loads(git(ROOT, "show", f"FETCH_HEAD:{LEDGER}"))["candidate_news"][SOURCE]
    if final["pending"] or final["partial"] is not None or final["posted"][ARTICLE]["messages"] != ["101"]:
        raise ValueError("shared ledger completion not confirmed")
    print("::notice title=Synthetic shared-ledger standby::cross-repo-checkout=pass github-checkpoints=pass repeat=held simulated-posts=1 discord-posts=0", flush=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:  # noqa: BLE001 — no token, Git output or exception details in logs
        raise SystemExit("Shared-ledger simulation held; inspect development state before any retry.") from None
