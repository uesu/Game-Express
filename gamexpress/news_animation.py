"""Bounded Discord attachment preparation for official news with mislabeled GIFs.

Pure planning preserves text/media order and keeps hashes in attachment names so a
checkpoint detects changed bytes on resume. This module never posts or persists.
Failures hold the article rather than silently replacing animation with a still.
"""
from __future__ import annotations

import asyncio
import copy
import hashlib
import re
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

import aiohttp

from .cards import renumber_page_labels, validate_payload
from .http import BROWSER_UA

SOURCE_LIMIT = 24 * 1024 * 1024
UPLOAD_LIMIT = 8 * 1024 * 1024
TOTAL_SOURCE_LIMIT = 256 * 1024 * 1024
TOTAL_UPLOAD_LIMIT = 96 * 1024 * 1024
TRUSTED_SUFFIXES = ("hoyolab.com", "hoyoverse.com", "hoyocdn.com", "mihoyo.com", "mihoyocdn.com",
                    "kurogame.com", "kurogames.com", "aki-game.net", "aki-game.com", "easebar.com",
                    "anantagame.com", "netease.com", "163.com", "ytimg.com")
TRUSTED_EXACT = ("web-static.hg-cdn.com", "ntevmg.perfectworld.com", "s.elementagames.com")
NAME_RE = re.compile(r"animation-([a-f0-9]{64})\.gif\Z")


def gif_info(raw: bytes, *, with_duration=False):
    """Validate GIF block framing, dimensions and animation without decoding pixels."""
    if len(raw) < 14 or raw[:6] not in (b"GIF87a", b"GIF89a"):
        raise ValueError("invalid GIF")
    width, height = int.from_bytes(raw[6:8], "little"), int.from_bytes(raw[8:10], "little")
    if not 1 <= width <= 1920 or not 1 <= height <= 1920:
        raise ValueError("GIF dimensions outside safety bound")
    i = 13 + (3 * (1 << ((raw[10] & 7) + 1)) if raw[10] & 0x80 else 0)
    frames = 0
    duration_cs = 0
    delay_cs = 0

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
                raise ValueError("GIF incomplete or outside frame bound")
            return (width, height, frames, duration_cs) if with_duration else (width, height, frames)
        if tag == 0x21:
            if i + 5 < len(raw) and raw[i] == 0xF9 and raw[i + 1] == 4:
                delay_cs = int.from_bytes(raw[i + 3:i + 5], "little")
            i = subblocks(i + 1)
        elif tag == 0x2C:
            if i + 9 > len(raw):
                break
            packed = raw[i + 8]
            i += 9 + (3 * (1 << ((packed & 7) + 1)) if packed & 0x80 else 0)
            i = subblocks(i + 1)
            frames += 1
            duration_cs += delay_cs
            delay_cs = 0
        else:
            break
    raise ValueError("malformed GIF")


def trusted_url(url):
    try:
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        return (parts.scheme == "https" and not parts.username and not parts.password and parts.port in (None, 443)
                and not parts.fragment and (host in TRUSTED_EXACT or
                    any(host == suffix or host.endswith("." + suffix) for suffix in TRUSTED_SUFFIXES)))
    except (ValueError, TypeError):
        return False


async def fetch_gif(fetcher, url):
    if not trusted_url(url):
        raise ValueError("animation source is not an official allowlisted host")
    async with fetcher.session.get(url, headers={"User-Agent": BROWSER_UA}, allow_redirects=False,
                                   timeout=aiohttp.ClientTimeout(total=120)) as response:
        if response.status != 200:
            raise ValueError("animation source unavailable")
        data = bytearray()
        async for chunk in response.content.iter_chunked(65536):
            data.extend(chunk)
            if len(data) > SOURCE_LIMIT:
                raise ValueError("animation exceeds source safety limit")
    raw = bytes(data)
    gif_info(raw)
    return raw


def convert_gif(raw):
    """Copy original if it fits; otherwise use bounded, lossy GIF conversion.

    The private prototype has been visually confirmed for the 480px/8fps case.
    A rejected conversion is held; it must not silently lose an animation.
    """
    _, _, _, original_duration = gif_info(raw, with_duration=True)
    if len(raw) <= UPLOAD_LIMIT:
        return raw
    import imageio_ffmpeg

    with tempfile.TemporaryDirectory() as tmp:
        src, dst = Path(tmp) / "source.gif", Path(tmp) / "animation.gif"
        src.write_bytes(raw)
        for size, fps in ((640, 10), (480, 8)):
            args = [imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-nostdin", "-threads", "2",
                    "-i", str(src), "-filter_complex",
                    f"fps={fps},scale={size}:-2:flags=lanczos,split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=sierra2_4a",
                    "-loop", "0", "-y", str(dst)]
            result = subprocess.run(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, timeout=180, check=False)
            if result.returncode:
                raise ValueError("animation conversion failed")
            if dst.stat().st_size <= UPLOAD_LIMIT:
                out = dst.read_bytes()
                _, _, _, output_duration = gif_info(out, with_duration=True)
                if not original_duration or abs(output_duration - original_duration) > max(40, 200 // fps):
                    raise ValueError("converted animation duration changed")
                return out
    raise ValueError("converted GIF exceeds upload safety limit")


def split_pages(payloads, replacements, *, max_pages):
    """Replace selected gallery URLs, split at attachment boundaries, and preserve order."""
    if not replacements:
        return payloads
    out = []
    for original in payloads:
        if (len(original.get("components", [])) != 1 or original["components"][0].get("type") != 17
                or original.get("attachments")):
            raise ValueError("unsupported animation article layout")
        template = copy.deepcopy(original)
        children = template["components"][0]["components"]
        atoms = []
        for child in children:
            if child.get("type") == 12:
                for entry in child["items"]:
                    atom = copy.deepcopy(child)
                    atom["items"] = [copy.deepcopy(entry)]
                    atoms.append(atom)
            else:
                atoms.append(child)
        segments, current, has_file = [], [], False
        for index, child in enumerate(atoms):
            url = child["items"][0]["media"]["url"] if child.get("type") == 12 else None
            name = replacements.get(url)
            if name:
                if has_file:
                    raise ValueError("animation pagination failure")
                child["items"][0]["media"]["url"] = "attachment://" + name
                has_file = True
            current.append(child)
            if has_file and any(x.get("type") == 12 and x["items"][0]["media"]["url"] in replacements
                                for x in atoms[index + 1:]):
                segments.append(current)
                current, has_file = [], False
        if current:
            segments.append(current)
        for kids in segments:
            page = copy.deepcopy(template)
            page["components"][0]["components"] = kids
            names = [x["items"][0]["media"]["url"][len("attachment://"):]
                     for x in kids if x.get("type") == 12 and x["items"][0]["media"]["url"].startswith("attachment://")]
            if len(names) > 1:
                raise ValueError("more than one upload per message")
            if names:
                page["attachments"] = [{"id": 0, "filename": names[0]}]
            if validate_payload(page):
                raise ValueError("invalid animation page")
            out.append(page)
    if len(out) > max_pages:
        raise ValueError("animation pages exceed safety limit")
    renumber_page_labels(out)
    if any(validate_payload(page) for page in out):
        raise ValueError("invalid animation pagination")
    return out


async def prepare(fetcher, payloads, *, max_pages=120):
    """Prepare mislabelled official GIFs for Discord; leave normal articles unchanged."""
    urls = list(dict.fromkeys(entry["media"]["url"] for page in payloads
              for box in page.get("components", []) for child in box.get("components", []) if child.get("type") == 12
              for entry in child.get("items", [])))
    replacements, assets, total_in, total_out = {}, {}, 0, 0
    for url in urls:
        prefix = await fetcher._news_media_prefix(url)
        if not prefix:
            raise ValueError("animation detection unavailable")
        raw, mime = prefix
        if not raw.startswith((b"GIF87a", b"GIF89a")):
            continue
        if mime == "image/gif" and urlsplit(url).path.lower().endswith(".gif"):
            continue  # established correctly labeled native GIF path
        body = await fetch_gif(fetcher, url)
        total_in += len(body)
        if total_in > TOTAL_SOURCE_LIMIT:
            raise ValueError("article animation download bound exceeded")
        converted = await asyncio.to_thread(convert_gif, body)
        total_out += len(converted)
        if total_out > TOTAL_UPLOAD_LIMIT:
            raise ValueError("article animation upload bound exceeded")
        name = "animation-" + hashlib.sha256(converted).hexdigest() + ".gif"
        replacements[url] = name
        assets[name] = converted
    return split_pages(payloads, replacements, max_pages=max_pages), assets
