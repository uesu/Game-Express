"""Manual, read-only source reconnaissance; not an integration or a health guarantee.

Only fixed public URLs are requested. No secrets, posting, state, or response bodies are
written. Run with --self-test for offline tests, or without arguments for live probing.
"""
from __future__ import annotations

import json
import re
import sys
import unittest
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from urllib.parse import urlsplit

LIMIT = 4 * 1024 * 1024
TIMEOUT = 15
TARGETS = (
    ("crimson-genshin", "https://www.crimsonwitch.com/codes/Genshin_Impact", "crimson"),
    ("crimson-starrail", "https://www.crimsonwitch.com/codes/Honkai_Star_Rail", "crimson"),
    ("crimson-zenless", "https://www.crimsonwitch.com/codes/Zenless_Zone_Zero", "crimson"),
    ("crimson-rss-genshin", "https://www.crimsonwitch.com/feeds/genshin/rss.xml", "rss"),
    ("crimson-rss-starrail", "https://www.crimsonwitch.com/feeds/star%20rail/rss.xml", "rss"),
    ("crimson-rss-zenless", "https://www.crimsonwitch.com/feeds/zzz/rss.xml", "rss"),
    ("ogc-endfield", "https://api.ennead.cc/codes/endfield", "codes"),
    ("ogc-nte", "https://api.ennead.cc/codes/nte", "codes"),
    ("ennead-genshin", "https://api.ennead.cc/mihoyo/genshin/codes", "ennead"),
    ("ennead-starrail", "https://api.ennead.cc/mihoyo/starrail/codes", "ennead"),
    ("ennead-zenless", "https://api.ennead.cc/mihoyo/zenless/codes", "ennead"),
    ("news-endfield", "https://endfield.gryphline.com/en-us/news", "html"),
    ("endfield-cms-list", "https://web-news.gryphline.com/api/bulletin?lang=en-us&code=arknights_endfield_official&page=1&pageSize=20", "endfield-list"),
    ("endfield-cms-page-2", "https://web-news.gryphline.com/api/bulletin?lang=en-us&code=arknights_endfield_official&page=2&pageSize=20", "endfield-list"),
    ("endfield-cms-detail", "https://web-news.gryphline.com/api/bulletin/7011?lang=en-us&code=arknights_endfield_official", "endfield-detail"),
    ("endfield-update-notice", "https://web-news.gryphline.com/api/bulletin/3835?lang=en-us&code=arknights_endfield_official", "endfield-detail"),
    ("news-nte", "https://nte.perfectworld.com/en/article/news/index.html", "html"),
    ("news-nte-page-2", "https://nte.perfectworld.com/en/article/news/index1.html", "html"),
    ("news-nte-patch-notes", "https://nte.perfectworld.com/en/article/news/gamenews/20261109/264948.html", "html"),
    ("news-silver", "https://silverpalace.elementagames.com/en-us/news", "html"),
    ("silver-list", "https://silverpalace.elementagames.com/server/index.php/home/news_list?lang=en-us&page=1", "silver-list"),
    ("silver-page-2", "https://silverpalace.elementagames.com/server/index.php/home/news_list?lang=en-us&page=2", "silver-list"),
    ("silver-detail", "https://silverpalace.elementagames.com/server/index.php/home/news_detail?lang=en-us&id=120", "silver-detail"),
    ("media-endfield", "https://web-static.hg-cdn.com/upload/image/20261124/a3a96dba4a3e82dbcedce572ff553b12.jpg", "media"),
    ("media-nte", "https://ntevmg.perfectworld.com/webops/nte/104en.jpg", "media"),
    ("media-silver", "https://s.elementagames.com/official/image/20260928/2b8cc49efcf5a2c3e456955935f2cb02.jpg", "media"),
)


GROUPS = {
    "codes": tuple(name for name, _, _ in TARGETS if name.startswith(("ogc-", "ennead-"))),
    "crimson": tuple(name for name, _, _ in TARGETS if name.startswith("crimson-")),
    "endfield-nte": tuple(name for name, _, _ in TARGETS if name.startswith(("endfield-", "news-endfield", "news-nte"))),
    "silver": tuple(name for name, _, _ in TARGETS if name.startswith(("silver-", "news-silver"))),
    "media": tuple(name for name, _, _ in TARGETS if name.startswith("media-")),
}


class Page(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links = 0
        self.internal_news_links = 0
        self.scripts = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "script":
            self.scripts += 1
        if tag == "a":
            href = dict(attrs).get("href") or ""
            self.links += bool(href)
            try:
                path = urlsplit(href).path.lower()
            except ValueError:
                path = ""
            self.internal_news_links += bool(path and ("newsdetail" in path or "/news/" in path))


def describe(kind: str, body: bytes) -> str:
    """Report structure, never actual upstream strings or content."""
    if kind in ("codes", "ennead", "endfield-list", "endfield-detail", "silver-list", "silver-detail"):
        try:
            value = json.loads(body)
        except (ValueError, UnicodeError):
            return "invalid-json"
        if kind.startswith("silver-"):
            if (not isinstance(value, dict) or type(value.get("code")) is not int
                    or value["code"] != 0 or not isinstance(value.get("data"), dict)):
                return "unexpected-json-envelope"
            data = value["data"]
            if kind == "silver-detail":
                fields = ("id", "title", "publish_date", "cover", "content")
                present = sum(key in data for key in fields)
                body_field = data.get("content" if kind == "silver-detail" else "data")
                body_shape = "html" if isinstance(body_field, str) and "<" in body_field and ">" in body_field else "other"
                return f"expected-detail-fields={present}/{len(fields)} body-shape={body_shape}"
            rows = data.get("list")
            if not isinstance(rows, list):
                return "unexpected-list-shape"
            valid = sum(isinstance(row, dict) and isinstance(row.get("id"), str)
                        and isinstance(row.get("title"), str)
                        and isinstance(row.get("publish_date"), str) for row in rows)
            pages = data.get("total_page")
            pages = pages if isinstance(pages, int) and not isinstance(pages, bool) and pages >= 0 else "invalid"
            return f"rows={len(rows)} valid-id-title-date={valid} total-pages={pages}"
        if kind.startswith("endfield-"):
            if (not isinstance(value, dict) or type(value.get("code")) is not int
                    or value["code"] != 0 or not isinstance(value.get("data"), dict)):
                return "unexpected-json-envelope"
            data = value["data"]
            if kind == "endfield-detail":
                fields = ("cid", "title", "displayTime", "cover", "data")
                present = sum(key in data for key in fields)
                body_field = data.get("content" if kind == "silver-detail" else "data")
                body_shape = "html" if isinstance(body_field, str) and "<" in body_field and ">" in body_field else "other"
                return f"expected-detail-fields={present}/{len(fields)} body-shape={body_shape}"
            rows = data.get("list")
            if not isinstance(rows, list):
                return "unexpected-list-shape"
            valid = sum(isinstance(row, dict) and isinstance(row.get("cid"), str)
                        and isinstance(row.get("title"), str)
                        and isinstance(row.get("displayTime"), int)
                        and not isinstance(row.get("displayTime"), bool) for row in rows)
            sticky = sum(isinstance(row, dict) and row.get("sticky") is True for row in rows)
            total = data.get("total")
            total = total if isinstance(total, int) and not isinstance(total, bool) and total >= 0 else "invalid"
            return f"rows={len(rows)} valid-id-title-time={valid} sticky={sticky} total={total}"
        if kind == "codes":
            if not isinstance(value, list):
                return "unexpected-json-shape"
            valid = sum(isinstance(x, dict) and isinstance(x.get("code"), str)
                        and isinstance(x.get("rewards"), list) for x in value)
            return f"rows={len(value)} code-and-rewards-shape={valid}"
        if not isinstance(value, dict):
            return "unexpected-json-shape"
        return " ".join(f"{key}={len(value[key]) if isinstance(value.get(key), list) else 'missing-or-not-list'}"
                        for key in ("active", "inactive"))
    if kind == "media":
        image = (body.startswith((b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"GIF87a", b"GIF89a"))
                 or (body[:4] == b"RIFF" and body[8:12] == b"WEBP"))
        return f"recognized-image-signature={image}"
    if kind == "rss":
        # Reject DTD/entity expansion and avoid logging upstream titles/links.
        if b"<!DOCTYPE" in body.upper() or b"<!ENTITY" in body.upper():
            return "xml-dtd-rejected"
        try:
            root = ET.fromstring(body)
        except ET.ParseError:
            return "invalid-xml"
        return f"rss-items={len(root.findall('.//item'))} atom-entries={len(root.findall('.//{http://www.w3.org/2005/Atom}entry'))}"
    text = body.decode("utf-8", errors="replace")
    page = Page()
    page.feed(text)
    result = f"links={page.links} news-shaped-links={page.internal_news_links} scripts={page.scripts}"
    if kind == "crimson":
        result += f" initialCodes-marker={'initialCodes' in text}"
    return result


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def print_result(message: str, annotations: bool) -> None:
    # Only the probe's fixed labels, numbers and structural tokens reach annotations.
    safe = re.sub(r"[^A-Za-z0-9 _=./():;>,+-]", "?", message)[:250]
    print(f"::notice title=Source research::{safe}" if annotations else safe)


def probe(target: str | None = None, *, require_html: bool = False, annotations: bool = False,
          group: str | None = None) -> int:
    opener = urllib.request.build_opener(NoRedirect())
    failures = 0
    for name, url, kind in TARGETS:
        if (target is not None and name != target) or (group is not None and name not in GROUPS[group]):
            continue
        request = urllib.request.Request(url, headers={"User-Agent": "Game-Express-Source-Research/1.0", "Accept": "*/*"})
        try:
            with opener.open(request, timeout=TIMEOUT) as response:
                body = response.read(LIMIT + 1)
                if len(body) > LIMIT:
                    print_result(f"{name}: response-too-large (>{LIMIT} bytes)", annotations)
                    failures += 1
                    continue
                description = describe(kind, body)
                print_result(f"{name}: http={response.status} bytes={len(body)} {description}", annotations)
                if target and not structurally_valid(kind, description, require_html):
                    failures += 1
        except urllib.error.HTTPError as exc:
            # Do not follow redirects or print attacker-controlled headers or bodies.
            print_result(f"{name}: http={exc.code} (redirects not followed)", annotations)
            failures += 1
        except (OSError, ValueError) as exc:
            print_result(f"{name}: request-failed ({type(exc).__name__})", annotations)
            failures += 1
    print_result(f"HTTP/request failures={failures}; structural reports require human review; empty is not proof of health.", annotations)
    return 1 if failures else 0


def structurally_valid(kind: str, description: str, require_html: bool = False) -> bool:
    """Single-target runner status is meaningful without exposing response content."""
    if require_html:
        return "expected-detail-fields=5/5 body-shape=html" in description
    if kind.endswith("-detail"):
        return "expected-detail-fields=5/5" in description
    if kind.endswith("-list"):
        match = re.match(r"rows=(\d+) valid-id-title-(?:date|time)=(\d+) ", description)
        return bool(match and int(match[1]) > 0 and match[1] == match[2] and "=invalid" not in description)
    if kind == "html":
        return description.startswith("links=") and "news-shaped-links=0" not in description
    return not description.startswith(("invalid", "unexpected"))


class ProbeTests(unittest.TestCase):
    def test_json_shapes(self):
        self.assertEqual(describe("codes", b'[{"code":"X","rewards":[]},{}]'), "rows=2 code-and-rewards-shape=1")
        self.assertEqual(describe("codes", b'{}'), "unexpected-json-shape")
        self.assertEqual(describe("codes", b'{'), "invalid-json")
        self.assertEqual(describe("ennead", b'{"active":[],"inactive":[1]}'), "active=0 inactive=1")

    def test_endfield_cms_shapes(self):
        page = {"code": 0, "data": {"list": [
            {"cid": "0740", "title": "not printed", "displayTime": 100, "sticky": True},
            {"cid": "12", "title": "x", "displayTime": 101, "sticky": False},
            {"cid": 12, "title": "x", "displayTime": True},
        ], "total": 3}}
        self.assertEqual(describe("endfield-list", json.dumps(page).encode()),
                         "rows=3 valid-id-title-time=2 sticky=1 total=3")
        self.assertEqual(describe("endfield-list", b'{"code":1,"data":{"list":[]}}'),
                         "unexpected-json-envelope")
        self.assertEqual(describe("endfield-list", b'{"code":0,"data":{"list":{}}}'),
                         "unexpected-list-shape")
        self.assertEqual(describe("endfield-detail", b'{"code":0,"data":{"cid":"0740",'
                             b'"title":"x","displayTime":123,"cover":"url","data":"body"}}'),
                         "expected-detail-fields=5/5 body-shape=other")

    def test_silver_cms_shapes(self):
        payload = {"code": 0, "data": {"list": [
            {"id": "120", "title": "not printed", "publish_date": "2026-10-09"},
            {"id": 2, "title": "x", "publish_date": None},
        ], "total_page": 7}}
        self.assertEqual(describe("silver-list", json.dumps(payload).encode()),
                         "rows=2 valid-id-title-date=1 total-pages=7")
        self.assertEqual(describe("silver-list", b'{"code":1,"data":{"list":[]}}'),
                         "unexpected-json-envelope")
        self.assertEqual(describe("silver-list", b'{"code":0,"data":{"list":{}}}'),
                         "unexpected-list-shape")
        self.assertEqual(describe("silver-detail", b'{"code":0,"data":{"id":"120",'
                             b'"title":"x","publish_date":"2026-10-09","cover":"url","content":"body"}}'),
                         "expected-detail-fields=5/5 body-shape=other")

    def test_target_structure_gate(self):
        self.assertTrue(structurally_valid("endfield-detail", "expected-detail-fields=5/5 body-shape=html", True))
        self.assertFalse(structurally_valid("endfield-detail", "expected-detail-fields=5/5 body-shape=other", True))
        self.assertFalse(structurally_valid("silver-list", "unexpected-list-shape"))
        self.assertFalse(structurally_valid("silver-list", "rows=1 valid-id-title-date=1 total-pages=invalid"))
        self.assertFalse(structurally_valid("html", "links=3 news-shaped-links=0 scripts=1"))

    def test_media_signatures(self):
        self.assertEqual(describe("media", b"\xff\xd8\xffdummy"), "recognized-image-signature=True")
        self.assertEqual(describe("media", b"<html>not an image</html>"), "recognized-image-signature=False")

    def test_rss_and_html(self):
        self.assertEqual(describe("rss", b'<rss><channel><item/></channel></rss>'), "rss-items=1 atom-entries=0")
        self.assertEqual(describe("rss", b'<!DOCTYPE x><rss/>'), "xml-dtd-rejected")
        self.assertEqual(describe("rss", b'<rss>'), "invalid-xml")
        result = describe("crimson", b'<a href="/en/news/12">secret</a><script>initialCodes</script>')
        self.assertEqual(result, "links=1 news-shaped-links=1 scripts=1 initialCodes-marker=True")
        self.assertNotIn("secret", result)


if __name__ == "__main__":
    if sys.argv[1:] == ["--self-test"]:
        unittest.main(argv=[sys.argv[0]])
    elif sys.argv[1:] == ["--annotations"]:
        raise SystemExit(probe(annotations=True))
    elif len(sys.argv) == 4 and sys.argv[1] == "--group" and sys.argv[3] == "--annotations":
        if sys.argv[2] not in GROUPS:
            raise SystemExit("Unknown fixed group")
        raise SystemExit(probe(group=sys.argv[2], annotations=True))
    elif len(sys.argv) in (3, 4) and sys.argv[1] == "--target":
        names = {name for name, _, _ in TARGETS}
        if sys.argv[2] not in names or (len(sys.argv) == 4 and sys.argv[3] != "--require-html"):
            raise SystemExit("Unknown fixed target or option")
        raise SystemExit(probe(sys.argv[2], require_html=len(sys.argv) == 4))
    elif sys.argv[1:]:
        raise SystemExit("Usage: python tools/source_research_probe.py [--self-test | --annotations | --group NAME --annotations | --target NAME [--require-html]]")
    else:
        raise SystemExit(probe())
