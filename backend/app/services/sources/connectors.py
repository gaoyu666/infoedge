from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
from typing import Any

from app.services.sources.base import SourceRecord, fetch_json, fetch_text
from app.services.sources.apify import get_apify_connectors
from app.services.sources.hotlists import get_trendradar_hotlist_connectors
from app.services.sources.investment import get_investment_connectors
from app.services.sources.public_intel import get_public_intel_connectors
from app.services.sources.rss_sources import get_tech_radar_connectors
from app.services.sources.world_intel import get_world_intel_connectors


SHOPIFY_STORES = [
    ("Allbirds", "https://allbirds.com"),
    ("ColourPop", "https://colourpop.com"),
    ("Tentree", "https://www.tentree.com"),
    ("Brooklinen", "https://www.brooklinen.com"),
]
AMAZON_KEYWORDS = ["portable blender", "standing desk", "pet grooming kit"]
GOOGLE_PLAY_QUERIES = ["ai shopping", "fitness planner", "budget tracker"]


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _strip_html(value: str | None) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    return unescape(re.sub(r"\s+", " ", text).strip())[:1800]


def _text_between(value: str, start: str, end: str) -> str:
    start_at = value.find(start)
    if start_at < 0:
        return ""
    start_at += len(start)
    end_at = value.find(end, start_at)
    if end_at < 0:
        return ""
    return value[start_at:end_at]


@dataclass
class ShopifyCatalogConnector:
    name: str = "Shopify: Public Catalog"
    source_type: str = "public_json"
    status: str = "healthy"
    notes: str = "抓取 Shopify 店铺公开 /products.json 商品目录；无需密钥，适合供给侧、定价、品类和新品监控。"

    async def fetch(self, limit: int) -> list[SourceRecord]:
        per_store = max(1, min(4, limit))
        tasks = [self._fetch_store(store_name, base_url, per_store) for store_name, base_url in SHOPIFY_STORES]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        records: list[SourceRecord] = []
        errors: list[str] = []
        for result in results:
            if isinstance(result, Exception):
                errors.append(str(result))
            else:
                records.extend(result)
        if not records and errors:
            raise RuntimeError("; ".join(errors[:3]))
        return records[: max(limit, per_store)]

    async def _fetch_store(self, store_name: str, base_url: str, limit: int) -> list[SourceRecord]:
        url = f"{base_url.rstrip('/')}/products.json?limit={limit}"
        payload = await fetch_json(url)
        records: list[SourceRecord] = []
        for product in payload.get("products", [])[:limit]:
            title = product.get("title") or ""
            handle = product.get("handle") or product.get("id") or title
            variants = product.get("variants") or []
            prices = []
            available = 0
            for variant in variants:
                try:
                    prices.append(float(variant.get("price") or 0))
                except (TypeError, ValueError):
                    pass
                if variant.get("available"):
                    available += 1
            min_price = min(prices) if prices else 0
            max_price = max(prices) if prices else 0
            tags = product.get("tags") or []
            records.append(
                SourceRecord(
                    source=self.name,
                    source_item_id=f"{store_name}:{handle}",
                    title=f"{store_name}: {title}",
                    url=f"{base_url.rstrip('/')}/products/{handle}" if handle else base_url,
                    content=_strip_html(product.get("body_html") or " ".join(tags)),
                    published_at=_parse_datetime(product.get("published_at") or product.get("created_at")),
                    metrics={
                        "min_price": min_price,
                        "max_price": max_price,
                        "variants": len(variants),
                        "available_variants": available,
                    },
                    payload={
                        "store": store_name,
                        "vendor": product.get("vendor"),
                        "product_type": product.get("product_type"),
                        "tags": tags[:20],
                        "images": len(product.get("images") or []),
                    },
                )
            )
        return records


@dataclass
class AmazonLightConnector:
    name: str = "Amazon: Light Search"
    source_type: str = "crawler"
    status: str = "experimental"
    notes: str = "轻量抓取 Amazon 搜索页结果标题、价格和评论数；用于小规模验证，遇到验证码/拦截会自动降级。"

    async def fetch(self, limit: int) -> list[SourceRecord]:
        per_keyword = max(1, min(3, limit))
        tasks = [asyncio.to_thread(self._fetch_keyword, keyword, per_keyword) for keyword in AMAZON_KEYWORDS]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        records: list[SourceRecord] = []
        errors: list[str] = []
        for result in results:
            if isinstance(result, Exception):
                errors.append(str(result))
            else:
                records.extend(result)
        if not records and errors:
            raise RuntimeError("; ".join(errors[:3]))
        return records[: max(limit, per_keyword)]

    def _fetch_keyword(self, keyword: str, limit: int) -> list[SourceRecord]:
        from urllib.parse import quote_plus

        url = f"https://www.amazon.com/s?k={quote_plus(keyword)}"
        html = fetch_text(url, accept="text/html,application/xhtml+xml,*/*")
        lowered = html.lower()
        if "captcha" in lowered or "robot check" in lowered:
            raise RuntimeError(f"amazon blocked keyword={keyword}")
        chunks = re.split(r'data-asin="([A-Z0-9]{10})"', html)
        records: list[SourceRecord] = []
        for index in range(1, len(chunks), 2):
            asin = chunks[index]
            block = chunks[index + 1][:9000]
            if "s-result-item" not in block:
                continue
            title = _strip_html(_text_between(block, "<h2", "</h2>"))
            title = re.sub(r"^.*?>", "", title).strip()
            if len(title) < 8:
                continue
            price_text = _strip_html(_text_between(block, 'class="a-price"', "</span>"))
            rating_text = _strip_html(_text_between(block, "a-icon-alt", "</span>"))
            review_text = _strip_html(_text_between(block, 'a-size-base s-underline-text', "</span>"))
            records.append(
                SourceRecord(
                    source=self.name,
                    source_item_id=f"{keyword}:{asin}",
                    title=title[:300],
                    url=f"https://www.amazon.com/dp/{asin}",
                    content=f"Keyword: {keyword}. Price: {price_text}. Rating: {rating_text}. Reviews: {review_text}",
                    published_at=None,
                    metrics={
                        "rank": len(records) + 1,
                        "review_count": int(re.sub(r"\D", "", review_text) or 0),
                    },
                    payload={
                        "keyword": keyword,
                        "asin": asin,
                        "price_text": price_text,
                        "rating_text": rating_text,
                        "review_text": review_text,
                    },
                )
            )
            if len(records) >= limit:
                break
        if not records:
            raise RuntimeError(f"amazon returned no parseable products for keyword={keyword}")
        return records


@dataclass
class GooglePlayConnector:
    name: str = "Google Play: App Search"
    source_type: str = "scraper_library"
    status: str = "healthy"
    notes: str = "使用 google-play-scraper 按商业关键词抓取美国 Google Play 应用；无需密钥，但属于非官方库，需监控可用性。"

    async def fetch(self, limit: int) -> list[SourceRecord]:
        return await asyncio.to_thread(self._fetch_sync, limit)

    def _fetch_sync(self, limit: int) -> list[SourceRecord]:
        try:
            from google_play_scraper import search
        except ImportError as exc:
            raise RuntimeError("google-play-scraper is not installed") from exc

        records: list[SourceRecord] = []
        per_query = max(1, min(3, limit))
        for query in GOOGLE_PLAY_QUERIES:
            apps = search(query, lang="en", country="us", n_hits=per_query)
            for rank, app in enumerate(apps[:per_query], start=1):
                app_id = app.get("appId") or app.get("app_id") or app.get("url") or app.get("title")
                title = app.get("title") or ""
                if not app_id or not title:
                    continue
                records.append(
                    SourceRecord(
                        source=self.name,
                        source_item_id=f"{query}:{app_id}",
                        title=title,
                        url=f"https://play.google.com/store/apps/details?id={app_id}",
                        content=app.get("summary") or app.get("description") or "",
                        published_at=None,
                        metrics={
                            "rank": rank,
                            "score": app.get("score") or 0,
                            "ratings": app.get("ratings") or 0,
                        },
                        payload={
                            "query": query,
                            "developer": app.get("developer"),
                            "genre": app.get("genre"),
                            "price": app.get("price"),
                            "free": app.get("free"),
                            "installs": app.get("installs"),
                        },
                    )
                )
                if len(records) >= limit:
                    return records
        return records


def get_connector_instances() -> list[Any]:
    return [
        ShopifyCatalogConnector(),
        AmazonLightConnector(),
        GooglePlayConnector(),
        *get_tech_radar_connectors(),
        *get_trendradar_hotlist_connectors(),
        *get_investment_connectors(),
        *get_world_intel_connectors(),
        *get_public_intel_connectors(),
        *get_apify_connectors(),
    ]
