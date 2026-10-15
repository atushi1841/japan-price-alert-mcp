"""Self-contained EC price fetcher (stdlib only: urllib + re)."""
from __future__ import annotations

import json
import re
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
}


@dataclass
class PriceSnapshot:
    url: str
    platform: str
    price_jpy: int | None = None
    title: str = ""
    in_stock: bool = True
    scraped_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    raw_extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "platform": self.platform,
            "price_jpy": self.price_jpy,
            "title": self.title,
            "in_stock": self.in_stock,
            "scraped_at": self.scraped_at,
            "raw_extra": self.raw_extra,
        }


def detect_platform(url: str) -> str:
    host = urllib.parse.urlparse(url).netloc.lower()
    if "mercari.com" in host:
        return "mercari"
    if "yahoo.co.jp" in host:
        return "yahoo"
    if "rakuten.co.jp" in host:
        return "rakuten"
    if "suumo.jp" in host:
        return "suumo"
    if "kakaku.com" in host:
        return "kakaku"
    if "suruga-ya.jp" in host:
        return "surugaya"
    return "generic"


def fetch_html(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(url, headers=DEFAULT_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        charset = resp.headers.get_content_charset() or "utf-8"
        try:
            return raw.decode(charset, errors="replace")
        except LookupError:
            return raw.decode("utf-8", errors="replace")


_JSONLD_RE = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.S | re.I,
)
_OG_TITLE_RE = re.compile(
    r'<meta[^>]+(?:property|name)=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']', re.I
)
_PRICE_META_RE = re.compile(
    r'<meta[^>]+(?:property|name)=["\'](?:og:price:amount|product:price:amount)["\'][^>]+content=["\']([^"\']+)["\']',
    re.I,
)
_TITLE_TAG_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)
_YEN_RE = re.compile(r"[¥￥]\s*([0-9][0-9,]*)")
_SOLD_OUT_RE = re.compile(r"売り切れ|SOLD\s?OUT", re.I)


def _clean_price(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    m = re.search(r"[0-9][0-9,]*", str(value))
    if not m:
        return None
    try:
        return int(m.group().replace(",", ""))
    except ValueError:
        return None


def _extract_jsonld(html: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for block in _JSONLD_RE.findall(html):
        try:
            data = json.loads(block)
        except (json.JSONDecodeError, TypeError):
            continue
        nodes = data if isinstance(data, list) else [data]
        for node in nodes:
            if not isinstance(node, dict):
                continue
            typ = str(node.get("@type", ""))
            if "Product" in typ or "RealEstate" in typ or "Offer" in typ:
                if "name" in node and not out.get("title"):
                    out["title"] = str(node["name"]).strip()[:200]
                offers = node.get("offers")
                if isinstance(offers, list):
                    offers = offers[0] if offers else None
                if isinstance(offers, dict):
                    price = offers.get("price", offers.get("lowPrice"))
                    if price is not None and _clean_price(price) is not None:
                        out["price"] = _clean_price(price)
                    avail = str(offers.get("availability", ""))
                    if "OutOfStock" in avail:
                        out["in_stock"] = False
                if "price" in node:
                    p = _clean_price(node["price"])
                    if p is not None and out.get("price") is None:
                        out["price"] = p
    return out


def _regex_price(html: str) -> int | None:
    for m in _YEN_RE.finditer(html):
        p = _clean_price(m.group(1))
        if p is not None and p >= 1:
            return p
    return None


def parse_price_page(url: str, html: str, platform: str | None = None) -> PriceSnapshot:
    platform = platform or detect_platform(url)
    snap = PriceSnapshot(url=url, platform=platform)

    ld = _extract_jsonld(html)
    snap.price_jpy = ld.get("price")
    if ld.get("title"):
        snap.title = ld["title"]
    if "in_stock" in ld:
        snap.in_stock = bool(ld["in_stock"])

    if snap.price_jpy is None:
        m = _PRICE_META_RE.search(html)
        if m:
            snap.price_jpy = _clean_price(m.group(1))

    if not snap.title:
        m = _OG_TITLE_RE.search(html) or _TITLE_TAG_RE.search(html)
        if m:
            snap.title = re.sub(r"\s+", " ", m.group(1)).strip()[:200]

    if snap.price_jpy is None:
        snap.price_jpy = _regex_price(html)

    if platform in ("mercari", "generic") and _SOLD_OUT_RE.search(html[:4000]):
        if snap.price_jpy is not None:
            snap.in_stock = False

    return snap


def fetch_price(url: str, timeout: int = 20) -> PriceSnapshot:
    platform = detect_platform(url)
    html = fetch_html(url, timeout=timeout)
    snap = parse_price_page(url, html, platform)
    if snap.price_jpy is None:
        raise ValueError(f"price not found for {url} (platform={platform})")
    return snap