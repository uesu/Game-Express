"""Private-only, independently journaled test of correctly labelled GIF attachments.

One article sample per run, never retries an uncertain send. The 99 sample uploads
original bytes; the 93 sample is downscaled/re-encoded to respect upload limits.
This is an experiment, not a production delivery implementation.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qsl, urlsplit

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import aiohttp  # noqa: E402
import candidate_private_backfill as historic  # noqa: E402
from live_candidate_probe import NoRedirectSession  # noqa: E402

from gamexpress import candidate_news_delivery as delivery  # noqa: E402
from gamexpress.cards import IS_COMPONENTS_V2, container, text, validate_payload  # noqa: E402
from gamexpress.http import Fetcher  # noqa: E402
from gamexpress.sources import silverpalace  # noqa: E402

MARKER = "feature3-silver-animation-upload-probe-v1"
COMMENT_ID = 7236050623  # independently verified, preparation permanently locked
IDS = {"93", "99"}
SOURCE_LIMIT = 24 * 1024 * 1024
UPLOAD_LIMIT = 8 * 1024 * 1024


def gif_info(raw):
    """Validate GIF blocks and count frames without decoding untrusted pixels."""
    if len(raw) < 14 or raw[:6] not in (b"GIF87a", b"GIF89a"):
        raise ValueError("not GIF")
    width, height = int.from_bytes(raw[6:8], "little"), int.from_bytes(raw[8:10], "little")
    if not 1 <= width <= 1920 or not 1 <= height <= 1920:
        raise ValueError("unexpected GIF size")
    i = 13 + (3 * (1 << ((raw[10] & 7) + 1)) if raw[10] & 0x80 else 0)
    frames = 0

    def subblocks(pos):
        while pos < len(raw):
            count = raw[pos]
            pos += 1
            if not count:
                return pos
            pos += count
        raise ValueError("truncated GIF")

    while i < len(raw):
        tag = raw[i]
        i += 1
        if tag == 0x3B:
            if frames < 2 or frames > 600 or i != len(raw):
                raise ValueError("not a complete bounded animation")
            return width, height, frames
        if tag == 0x21:
            i = subblocks(i + 1)
        elif tag == 0x2C:
            if i + 9 > len(raw):
                break
            packed = raw[i + 8]
            i += 9 + (3 * (1 << ((packed & 7) + 1)) if packed & 0x80 else 0)
            i = subblocks(i + 1)
            frames += 1
        else:
            break
    raise ValueError("invalid GIF blocks")


async def fetch_gif(session, url):
    if not silverpalace._official_cover(url):
        raise ValueError("untrusted source")
    async with session.get(url, allow_redirects=False, timeout=aiohttp.ClientTimeout(total=120)) as response:
        if response.status != 200:
            raise ValueError("source unavailable")
        data = bytearray()
        async for chunk in response.content.iter_chunked(65536):
            data.extend(chunk)
            if len(data) > SOURCE_LIMIT:
                raise ValueError("source too large")
    raw = bytes(data)
    gif_info(raw)
    return raw


def transcode(raw):
    import imageio_ffmpeg  # research-only pinned dependency, not a runtime dependency

    with tempfile.TemporaryDirectory() as tmp:
        src, dst = Path(tmp) / "source.gif", Path(tmp) / "animated.gif"
        src.write_bytes(raw)
        for size, fps in ((640, 10), (480, 8)):
            args = [imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-nostdin", "-threads", "2",
                    "-i", str(src), "-filter_complex",
                    f"fps={fps},scale={size}:-2:flags=lanczos,split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=sierra2_4a",
                    "-loop", "0", "-y", str(dst)]
            result = subprocess.run(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, timeout=180, check=False)
            if result.returncode:
                raise ValueError("GIF conversion failed")
            if dst.stat().st_size <= UPLOAD_LIMIT:
                out = dst.read_bytes()
                gif_info(out)
                return out, size, fps
    raise ValueError("converted GIF exceeds upload bound")


async def prepare(fetcher, route):
    if COMMENT_ID:
        raise ValueError("preparation locked")
    historic.MARKER = MARKER
    if any((await asyncio.to_thread(historic.prior_comments)).values()):
        raise ValueError("probe journal already exists")
    rows = [r for r in await delivery.discover(fetcher, "silverpalace") if r["id"] in IDS]
    if len(rows) != 2 or {r["id"] for r in rows} != IDS:
        raise ValueError("samples missing")
    state = delivery.ingest("silverpalace", route, None, rows)
    comment = await asyncio.to_thread(historic.gh_api, f"repos/{historic.REPOSITORY}/issues/{historic.ISSUE}/comments",
                                      method="POST", body={"body": historic.encode("silverpalace", state)})
    if historic.check_comment(comment, "silverpalace") != state:
        raise ValueError("preparation unconfirmed")
    print(f"::notice title=Silver upload experiment::prepared=1 count=2 comment={comment['id']} sent=0", flush=True)


async def send(session, fetcher, settings, route):
    if not COMMENT_ID:
        raise ValueError("probe journal not locked")
    historic.MARKER = MARKER
    comment = await asyncio.to_thread(historic.gh_api, f"repos/{historic.REPOSITORY}/issues/comments/{COMMENT_ID}")
    journal = historic.CommentJournal("silverpalace", comment, route)
    if set(journal.state["posted"]) | {r["id"] for r in journal.state["pending"]} != IDS:
        raise ValueError("unexpected sample queue")
    if journal.state["partial"] and journal.state["partial"]["inflight"]:
        raise ValueError("inflight; inspect before retry")
    if not journal.state["pending"]:
        print("::notice title=Silver upload experiment::already-complete=1 no-send=1", flush=True)
        return
    contents = {}

    async def render(row):
        item = await silverpalace.news_article(fetcher, delivery.candidate_game("silverpalace"), row)
        if item is None:
            raise ValueError("article unavailable")
        images = [b["url"] for b in item.article_blocks if b.get("kind") == "image"]
        if not images:
            raise ValueError("sample missing")
        raw = await fetch_gif(session, images[0])
        w, h, frames = gif_info(raw)
        if row["id"] == "93":
            data, width, fps = await asyncio.to_thread(transcode, raw)
            label = f"93 · size-reduced GIF ({width}px wide, {fps} fps); full animation, not original quality"
        else:
            data = raw
            label = "99 · original GIF bytes uploaded as image/gif; no conversion"
        if len(data) > UPLOAD_LIMIT:
            raise ValueError("upload size bound exceeded")
        ow, oh, oframes = gif_info(data)
        digest = hashlib.sha256(data).hexdigest()
        contents["data"] = data
        payload = {"flags": IS_COMPONENTS_V2, "allowed_mentions": {"parse": []}, "attachments": [{"id": 0, "filename": "animation.gif"}],
                   "components": [container([text("**Private Silver Palace animation test**\n" + label),
                     {"type": 12, "items": [{"media": {"url": "attachment://animation.gif"}, "description": "SHA256 " + digest}]}])]}
        if validate_payload(payload):
            raise ValueError("payload invalid")
        print(f"::notice title=Silver upload sample::id={row['id']} source-bytes={len(raw)} source-frames={frames} "
              f"source-size={w}x{h} upload-bytes={len(data)} upload-frames={oframes} upload-size={ow}x{oh}", flush=True)
        return [payload]

    async def send_one(payload):
        target = delivery.destination(settings, "silverpalace")
        if not target or target[1] != route:
            raise ValueError("destination mismatch")
        data = contents["data"]
        form = aiohttp.FormData()
        form.add_field("payload_json", json.dumps(payload), content_type="application/json")
        form.add_field("files[0]", data, filename="animation.gif", content_type="image/gif")
        parts = urlsplit(target[0])
        params = {"wait": "true", "with_components": "true", **dict(parse_qsl(parts.query))}
        async with session.post(parts._replace(query="").geturl(), params=params, data=form,
                                allow_redirects=False, timeout=aiohttp.ClientTimeout(total=120)) as response:
            status = response.status
            body = await response.content.read(65537)
            if len(body) > 65536:
                return SimpleNamespace(ok=False, ambiguous=True, message_id=None)
            try:
                result = json.loads(body)
            except (ValueError, UnicodeDecodeError):
                return SimpleNamespace(ok=False, ambiguous=True, message_id=None)
            mid = result.get("id") if isinstance(result, dict) else None
            if not 200 <= status < 300 or not isinstance(mid, str) or not mid.isdigit():
                return SimpleNamespace(ok=False, ambiguous=True, message_id=None)
            attachments = result.get("attachments") or []
            types = sorted({a.get("content_type", "missing") for a in attachments if isinstance(a, dict)})
            print(f"::notice title=Silver upload response::status={status} attachments={len(attachments)} "
                  f"mime={','.join(types)}", flush=True)
            return SimpleNamespace(ok=True, ambiguous=False,
                message_id=historic.anonymize(mid, settings.env["DISCORD_WEBHOOK_NEWS_SILVERPALACE"]))

    state = await delivery.deliver_oldest(journal.state, "silverpalace", route, as_of=int(time.time()),
             checkpoint=journal.checkpoint, render=render, send=send_one, max_pages=1)
    print(f"::notice title=Silver upload experiment::confirmed={len(state['posted'])} pending={len(state['pending'])} "
          f"partial={int(bool(state['partial']))} production-state=unchanged", flush=True)


async def main(mode):
    historic.guard()
    settings, routes = historic.settings_and_routes()
    async with aiohttp.ClientSession(trust_env=False) as session:
        fetcher = Fetcher(NoRedirectSession(session))
        if mode == "prepare":
            await prepare(fetcher, routes["silverpalace"])
        else:
            await send(session, fetcher, settings, routes["silverpalace"])


if __name__ == "__main__":
    if sys.argv[1:] not in (["--prepare"], ["--send"]):
        raise SystemExit("Specify --prepare or --send explicitly.")
    try:
        asyncio.run(main(sys.argv[1][2:]))
    except Exception as exc:  # noqa: BLE001 — never expose destination or response
        print(f"::notice title=Silver upload experiment held::error-type={type(exc).__name__}", flush=True)
        raise SystemExit("Held; inspect independent journal and channel before retry.") from None
