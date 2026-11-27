"""Read-only comparison of three fixed Silver Palace article 7 artwork files."""
from __future__ import annotations

import asyncio
import hashlib
import io
import itertools
import warnings

import aiohttp
from PIL import Image, ImageChops, ImageOps, ImageStat

URLS = {
    "cover": "https://s.elementagames.com/official/image/20251218/12b219c30555a6b622f100e4603c2aea.jpg",
    "body": "https://s.elementagames.com/official/image/20251218/e4a8b3d37c628be4e73294c8469e73d6.jpg",
    "banner": "https://s.elementagames.com/official/image/20251218/c519fca919cb0cb555fd02af5f2866a9.jpg",
}


async def run():
    images, digests = {}, {}
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30), trust_env=False) as session:
        for name, url in URLS.items():
            async with session.get(url, allow_redirects=False) as response:
                if response.status != 200 or not response.headers.get("Content-Type", "").lower().startswith("image/"):
                    raise ValueError("media unavailable")
                data = bytearray()
                async for chunk in response.content.iter_chunked(65536):
                    data.extend(chunk)
                    if len(data) > 8 * 1024 * 1024:
                        raise ValueError("media exceeds byte limit")
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(data)) as image:
                    image = ImageOps.exif_transpose(image)
                    if image.width * image.height > 25000000:
                        raise ValueError("media exceeds pixel limit")
                    images[name] = image.convert("RGB")
            digests[name] = hashlib.sha256(data).hexdigest()
            print(f"::notice title=Silver image::{name} size={images[name].width}x{images[name].height} "
                  f"bytes={len(data)} sha256={digests[name]}", flush=True)
    for a, b in itertools.combinations(URLS, 2):
        # Normalized whole-frame mean pixel differences are descriptive, not a dedup rule.
        first = images[a].resize((128, 128))
        second = images[b].resize((128, 128))
        diff = ImageStat.Stat(ImageChops.difference(first, second)).mean
        score = sum(diff) / (3 * 255)
        print(f"::notice title=Silver comparison::{a}-{b} identical-bytes={int(digests[a] == digests[b])} "
              f"normalized-rgb-difference={score:.4f}", flush=True)


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except Exception:  # noqa: BLE001 — report no uncontrolled URL or response data
        raise SystemExit("Image comparison unavailable; no state or messages changed.") from None
