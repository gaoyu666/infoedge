from __future__ import annotations

import asyncio
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

from app.services.sources.base import SourceRecord, request_json


NEWSNOW_API_BASE = "https://newsnow.busiyi.world/api/s"

TREND_RADAR_HOTLISTS = [
    ("TrendRadar: Toutiao Hot", "toutiao", "Toutiao"),
    ("TrendRadar: Baidu Hot Search", "baidu", "Baidu Hot Search"),
    ("TrendRadar: Wallstreetcn Hot", "wallstreetcn-hot", "Wallstreetcn Hot"),
    ("TrendRadar: The Paper", "thepaper", "The Paper"),
    ("TrendRadar: Bilibili Hot Search", "bilibili-hot-search", "Bilibili Hot Search"),
    ("TrendRadar: CLS Hot", "cls-hot", "CLS Hot"),
    ("TrendRadar: Ifeng Hot", "ifeng", "Ifeng"),
    ("TrendRadar: Tieba Hot", "tieba", "Tieba"),
    ("TrendRadar: Weibo Hot", "weibo", "Weibo"),
    ("TrendRadar: Douyin Hot", "douyin", "Douyin"),
    ("TrendRadar: Zhihu Hot", "zhihu", "Zhihu"),
]


def _clean_text(value: Any, limit: int = 500) -> str:
    text = re.sub(r"<[^>]+>", " ", str(value or ""))
    return re.sub(r"\s+", " ", text).strip()[:limit]


def _parse_countish(value: Any) -> int:
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value or "").lower().replace(",", "").replace("+", "").strip()
    multiplier = 1
    if text.endswith("k"):
        multiplier = 1000
        text = text[:-1]
    elif text.endswith("m"):
        multiplier = 1_000_000
        text = text[:-1]
    digits = re.findall(r"\d+(?:\.\d+)?", text)
    return int(float(digits[0]) * multiplier) if digits else 0


@dataclass
class TrendRadarHotlistConnector:
    name: str
    platform_id: str
    platform_name: str
    source_type: str = "public_json"

    @property
    def enabled(self) -> bool:
        return bool(os.getenv("NEWSNOW_API_BASE") or os.getenv("NEWSNOW_ENABLE_PUBLIC_API") == "1")

    @property
    def status(self) -> str:
        return "experimental" if self.enabled else "needs_config"

    @property
    def notes(self) -> str:
        if self.enabled:
            return "TrendRadar-inspired hot-list connector using the configured NewsNow API; useful for Chinese social/search momentum signals."
        return (
            "TrendRadar-inspired hot-list source. The default public NewsNow endpoint is Cloudflare-blocked "
            "from this runtime; set NEWSNOW_API_BASE to a reachable relay/API before live collection."
        )

    @property
    def api_base(self) -> str:
        return os.getenv("NEWSNOW_API_BASE", NEWSNOW_API_BASE).rstrip("?")

    async def fetch(self, limit: int) -> list[SourceRecord]:
        url = f"{self.api_base}?id={quote(self.platform_id)}&latest"
        payload = await asyncio.to_thread(request_json, url, timeout=15)
        return self.records_from_payload(payload, limit)

    def records_from_payload(self, payload: dict[str, Any], limit: int) -> list[SourceRecord]:
        status = str(payload.get("status", "")).lower()
        if status and status not in {"success", "cache"}:
            raise RuntimeError(f"NewsNow returned status={status}")
        records: list[SourceRecord] = []
        for rank, item in enumerate((payload.get("items") or [])[:limit], start=1):
            if not isinstance(item, dict):
                continue
            title = _clean_text(item.get("title"))
            if not title:
                continue
            url = _clean_text(item.get("url")) or _clean_text(item.get("mobileUrl")) or None
            hotness = _parse_countish(item.get("hot") or item.get("hotValue") or item.get("score"))
            records.append(
                SourceRecord(
                    source=self.name,
                    source_item_id=f"{self.platform_id}:{title}",
                    title=title[:300],
                    url=url,
                    content=f"{self.platform_name} rank {rank}.",
                    published_at=datetime.now(timezone.utc).replace(tzinfo=None),
                    metrics={"rank": rank, "hotness": hotness},
                    payload={
                        "category": "trendradar_hotlist",
                        "platform_id": self.platform_id,
                        "platform_name": self.platform_name,
                        "raw": item,
                    },
                )
            )
        return records


def get_trendradar_hotlist_connectors() -> list[TrendRadarHotlistConnector]:
    return [
        TrendRadarHotlistConnector(name=name, platform_id=platform_id, platform_name=platform_name)
        for name, platform_id, platform_name in TREND_RADAR_HOTLISTS
    ]
