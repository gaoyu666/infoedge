from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

from app.core.config import settings
from app.services.sources.base import SourceRecord, request_json


APIFY_API_BASE = "https://api.apify.com/v2"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _first_text(item: dict[str, Any], keys: list[str], default: str = "") -> str:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if value is not None and not isinstance(value, (dict, list)):
            return str(value)
    return default


def _first_number(item: dict[str, Any], keys: list[str]) -> float:
    for key in keys:
        value = item.get(key)
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value.replace(",", "").strip())
            except ValueError:
                continue
    return 0.0


def _best_url(item: dict[str, Any]) -> str | None:
    value = _first_text(
        item,
        [
            "url",
            "productUrl",
            "product_url",
            "adSnapshotUrl",
            "ad_archive_url",
            "landingPageUrl",
            "link",
            "pageUrl",
        ],
    )
    return value or None


@dataclass
class ApifyActorConnector:
    name: str
    actor_id: str
    default_input: dict[str, Any]
    notes_when_configured: str
    category: str
    source_type: str = "third_party_api"
    token_env: str = "APIFY_TOKEN"
    run_timeout_seconds: int = field(default_factory=lambda: settings.apify_run_timeout_seconds)

    @property
    def enabled(self) -> bool:
        return bool(settings.apify_token)

    @property
    def status(self) -> str:
        return "healthy" if self.enabled else "needs_config"

    @property
    def notes(self) -> str:
        if not self.enabled:
            return f"需要配置 {self.token_env} 后启用；{self.notes_when_configured}"
        return self.notes_when_configured

    async def fetch(self, limit: int) -> list[SourceRecord]:
        if not self.enabled:
            raise RuntimeError(f"{self.token_env} is not configured")
        run = await asyncio.to_thread(self._start_run, limit)
        dataset_id = await self._wait_for_dataset(run)
        items = await asyncio.to_thread(self._read_dataset_items, dataset_id, limit)
        return [self._normalize_item(item, index + 1) for index, item in enumerate(items[:limit])]

    def _start_run(self, limit: int) -> dict[str, Any]:
        actor_path = quote(self.actor_id, safe="")
        url = f"{APIFY_API_BASE}/acts/{actor_path}/runs?token={settings.apify_token}"
        payload = {**self.default_input}
        for key in ("maxItems", "maxResults", "max_results", "limit"):
            if key in payload:
                payload[key] = limit
        return request_json(url, method="POST", payload=payload, timeout=30).get("data", {})

    async def _wait_for_dataset(self, run: dict[str, Any]) -> str:
        run_id = run.get("id")
        dataset_id = run.get("defaultDatasetId")
        if not run_id:
            raise RuntimeError(f"Apify actor {self.actor_id} did not return a run id")
        deadline = asyncio.get_running_loop().time() + self.run_timeout_seconds
        status = run.get("status") or "READY"
        while status not in {"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"}:
            if asyncio.get_running_loop().time() >= deadline:
                raise RuntimeError(f"Apify actor {self.actor_id} timed out")
            await asyncio.sleep(5)
            run = await asyncio.to_thread(self._get_run, run_id)
            status = run.get("status") or status
            dataset_id = run.get("defaultDatasetId") or dataset_id
        if status != "SUCCEEDED":
            raise RuntimeError(f"Apify actor {self.actor_id} finished with status {status}")
        if not dataset_id:
            raise RuntimeError(f"Apify actor {self.actor_id} did not return a dataset")
        return dataset_id

    def _get_run(self, run_id: str) -> dict[str, Any]:
        url = f"{APIFY_API_BASE}/actor-runs/{run_id}?token={settings.apify_token}"
        return request_json(url, timeout=30).get("data", {})

    def _read_dataset_items(self, dataset_id: str, limit: int) -> list[dict[str, Any]]:
        url = f"{APIFY_API_BASE}/datasets/{dataset_id}/items?token={settings.apify_token}&clean=true&limit={limit}"
        data = request_json(url, timeout=30)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and isinstance(data.get("items"), list):
            return data["items"]
        return []

    def _normalize_item(self, item: dict[str, Any], rank: int) -> SourceRecord:
        title = _first_text(
            item,
            [
                "title",
                "name",
                "productTitle",
                "product_title",
                "adTitle",
                "pageName",
                "brandName",
                "text",
                "caption",
            ],
            default=f"{self.name} item {rank}",
        )
        item_id = _first_text(
            item,
            [
                "id",
                "asin",
                "productId",
                "product_id",
                "listingId",
                "archiveId",
                "adArchiveId",
                "url",
                "productUrl",
            ],
            default=f"{title}:{rank}",
        )
        content = _first_text(
            item,
            [
                "description",
                "productDescription",
                "adText",
                "text",
                "caption",
                "body",
                "summary",
            ],
        )
        price = _first_number(item, ["price", "currentPrice", "salePrice", "finalPrice"])
        rating = _first_number(item, ["rating", "stars", "score"])
        reviews = _first_number(item, ["reviewsCount", "reviewCount", "totalReviews", "ratings"])
        metrics = {
            "rank": rank,
            "price": price,
            "rating": rating,
            "review_count": int(reviews),
        }
        return SourceRecord(
            source=self.name,
            source_item_id=str(item_id),
            title=title[:300],
            url=_best_url(item),
            content=content,
            published_at=_utcnow(),
            metrics=metrics,
            payload={
                "category": self.category,
                "actor_id": self.actor_id,
                "raw": item,
            },
        )


def get_apify_connectors() -> list[ApifyActorConnector]:
    return [
        ApifyActorConnector(
            name="Apify: Amazon Products",
            actor_id="apify/amazon-product-scraper",
            category="amazon_market_data",
            default_input={
                "categoryOrProductUrls": [{"url": "https://www.amazon.com/s?k=portable+blender"}],
                "maxItems": 3,
            },
            notes_when_configured="通过 Apify Amazon Product Scraper 获取结构化商品、价格、评分、评论等数据，作为 Amazon 深度数据备用方案。",
        ),
        ApifyActorConnector(
            name="Apify: TikTok Creative Center",
            actor_id="doliz/tiktok-creative-center-scraper",
            category="tiktok_ads",
            default_input={
                "target": "Top Ads Dashboard",
                "dashboard_region": ["US"],
                "dashboard_period": 7,
                "maxItems": 3,
            },
            notes_when_configured="通过 Apify TikTok Creative Center actor 获取广告、热词、商品、音乐等结构化数据；通常还需要 TikTok 登录 cookie。",
        ),
        ApifyActorConnector(
            name="Apify: Meta Ads Library",
            actor_id="apify/facebook-ads-scraper",
            category="meta_ads",
            default_input={
                "query": "shopify",
                "country": "US",
                "maxResults": 3,
            },
            notes_when_configured="通过 Apify Facebook Ads Scraper 获取 Meta Ads Library 竞品广告数据。",
        ),
        ApifyActorConnector(
            name="Apify: Etsy Products",
            actor_id="automation-lab/etsy-scraper",
            category="etsy_products",
            default_input={
                "query": "personalized gift",
                "maxItems": 3,
            },
            notes_when_configured="通过 Apify Etsy Scraper 获取 Etsy 搜索/商品/店铺数据，可作为官方 API 外的趋势补充。",
        ),
        ApifyActorConnector(
            name="Apify: 1688 Products",
            actor_id="automation-lab/1688-scraper",
            category="china_supply",
            default_input={
                "keywords": ["phone case", "bluetooth earbuds"],
                "maxItems": 3,
            },
            notes_when_configured="通过 Apify 1688 Scraper 获取供给侧商品和价格；通常需要 1688 登录 cookie 才稳定。",
        ),
        ApifyActorConnector(
            name="Apify: Temu Products",
            actor_id="automation-lab/temu-scraper",
            category="temu_products",
            default_input={
                "query": "pet grooming kit",
                "maxItems": 3,
            },
            notes_when_configured="通过 Apify Temu Scraper 获取 Temu 商品、价格、评价、销量等数据。",
        ),
    ]
