from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from typing import Any
from urllib.parse import quote, urlencode
from xml.etree import ElementTree

from app.services.sources.base import SourceRecord, fetch_text


GDELT_QUERIES = [
    ("GDELT: Geopolitics", "sanctions OR tariff OR export controls OR supply chain"),
    ("GDELT: Conflict Risk", "conflict OR missile OR drone OR blockade OR shipping disruption"),
    ("GDELT: Energy Markets", "oil OR gas OR LNG OR refinery OR energy prices"),
    ("GDELT: AI Regulation", "AI regulation OR chip ban OR semiconductor export controls"),
]

INTEL_RSS_FEEDS = [
    (
        "BBC: World",
        "https://feeds.bbci.co.uk/news/world/rss.xml",
        "world_news",
        "Tier-1 global news RSS for broad international situation awareness.",
    ),
    (
        "Al Jazeera: World",
        "https://www.aljazeera.com/xml/rss/all.xml",
        "world_news",
        "Global news RSS with strong Middle East and emerging-market coverage.",
    ),
    (
        "CISA: Cyber Advisories",
        "https://www.cisa.gov/cybersecurity-advisories/all.xml",
        "cyber_risk",
        "Official cybersecurity advisories; useful for software, infrastructure, and vendor-risk signals.",
    ),
    (
        "GDACS: Disaster Alerts",
        "https://www.gdacs.org/xml/rss.xml",
        "disaster_risk",
        "Global disaster alerts for earthquake, flood, storm, volcano, and humanitarian disruption signals.",
    ),
]


def _clean_text(value: str | None, limit: int = 1800) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    return unescape(re.sub(r"\s+", " ", text).strip())[:limit]


def _child_text(node: ElementTree.Element, *local_names: str) -> str:
    wanted = set(local_names)
    for child in list(node):
        local_name = child.tag.rsplit("}", 1)[-1]
        if local_name in wanted:
            return _clean_text(child.text or "")
    return ""


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


async def _fetch_json_any(url: str) -> Any:
    text = await asyncio.to_thread(fetch_text, url, accept="application/json,*/*")
    return json.loads(text)


@dataclass
class GdeltDocConnector:
    name: str
    query: str
    category: str = "global_event_news"
    source_type: str = "public_json"
    status: str = "needs_config"
    notes: str = "GDELT Doc API global news/event search. Disabled by default because the public endpoint is often rate-limited from shared hosts; enable after adding a proxy or relay."
    enabled: bool = False

    async def fetch(self, limit: int) -> list[SourceRecord]:
        params = {
            "query": self.query,
            "mode": "artlist",
            "format": "json",
            "maxrecords": max(10, limit),
            "sort": "hybridrel",
        }
        url = f"https://api.gdeltproject.org/api/v2/doc/doc?{urlencode(params)}"
        payload = await _fetch_json_any(url)
        articles = payload.get("articles", []) if isinstance(payload, dict) else []
        records: list[SourceRecord] = []
        for rank, item in enumerate(articles[:limit], start=1):
            title = item.get("title") or item.get("seendate") or ""
            if not title:
                continue
            source_url = item.get("url") or item.get("socialimage") or title
            records.append(
                SourceRecord(
                    source=self.name,
                    source_item_id=str(source_url),
                    title=_clean_text(title, 300),
                    url=item.get("url"),
                    content=_clean_text(
                        " ".join(
                            [
                                item.get("domain", ""),
                                item.get("sourcecountry", ""),
                                item.get("language", ""),
                            ]
                        )
                    ),
                    published_at=_parse_datetime(item.get("seendate")),
                    metrics={
                        "rank": rank,
                        "tone": item.get("tone") or 0,
                        "socialimage": 1 if item.get("socialimage") else 0,
                    },
                    payload={
                        "category": self.category,
                        "query": self.query,
                        "domain": item.get("domain"),
                        "sourcecountry": item.get("sourcecountry"),
                        "language": item.get("language"),
                    },
                )
            )
        return records


@dataclass
class IntelRssConnector:
    name: str
    url: str
    category: str
    notes: str
    source_type: str = "public_rss"
    status: str = "healthy"

    async def fetch(self, limit: int) -> list[SourceRecord]:
        return await asyncio.to_thread(self._fetch_sync, limit)

    def _fetch_sync(self, limit: int) -> list[SourceRecord]:
        text = fetch_text(self.url, accept="application/rss+xml,application/xml,*/*")
        root = ElementTree.fromstring(text)
        items = root.findall(".//item")
        if not items:
            items = root.findall("{http://www.w3.org/2005/Atom}entry")
        records: list[SourceRecord] = []
        for rank, item in enumerate(items[:limit], start=1):
            title = _child_text(item, "title")
            if not title:
                continue
            link = _child_text(item, "link")
            if not link:
                link_node = item.find("{http://www.w3.org/2005/Atom}link")
                link = link_node.attrib.get("href", "") if link_node is not None else ""
            published = _parse_datetime(_child_text(item, "pubDate", "published", "updated"))
            records.append(
                SourceRecord(
                    source=self.name,
                    source_item_id=_child_text(item, "guid", "id") or link or title,
                    title=title[:300],
                    url=link or None,
                    content=_child_text(item, "description", "summary", "content", "encoded"),
                    published_at=published,
                    metrics={"rank": rank, "news": 1},
                    payload={"category": self.category, "feed_url": self.url},
                )
            )
        return records


@dataclass
class PolymarketConnector:
    name: str = "Polymarket: Active Markets"
    source_type: str = "public_json"
    status: str = "healthy"
    notes: str = "Prediction-market odds and volume; useful as a leading indicator for geopolitics, regulation, crypto, and macro narratives."

    async def fetch(self, limit: int) -> list[SourceRecord]:
        params = {
            "active": "true",
            "closed": "false",
            "limit": max(10, limit),
            "order": "volume24hr",
            "ascending": "false",
        }
        url = f"https://gamma-api.polymarket.com/markets?{urlencode(params)}"
        payload = await _fetch_json_any(url)
        items = payload if isinstance(payload, list) else payload.get("markets", []) if isinstance(payload, dict) else []
        records: list[SourceRecord] = []
        excluded = re.compile(r"\b(nba|nfl|mlb|ufc|soccer|grammy|oscar|sports)\b", re.I)
        for rank, item in enumerate(items, start=1):
            question = item.get("question") or item.get("title") or ""
            if not question or excluded.search(question):
                continue
            slug = item.get("slug") or item.get("conditionId") or question
            volume = item.get("volume24hr") or item.get("volume") or 0
            liquidity = item.get("liquidity") or 0
            records.append(
                SourceRecord(
                    source=self.name,
                    source_item_id=str(slug),
                    title=_clean_text(question, 300),
                    url=f"https://polymarket.com/event/{slug}" if item.get("slug") else None,
                    content=_clean_text(item.get("description") or item.get("category") or ""),
                    published_at=_parse_datetime(item.get("startDate") or item.get("createdAt")),
                    metrics={
                        "rank": len(records) + 1,
                        "volume": int(float(volume or 0)),
                        "liquidity": int(float(liquidity or 0)),
                    },
                    payload={
                        "category": "prediction_market",
                        "market_id": item.get("id"),
                        "slug": item.get("slug"),
                        "end_date": item.get("endDate"),
                        "raw_category": item.get("category"),
                    },
                )
            )
            if len(records) >= limit:
                break
        return records


@dataclass
class CoinGeckoTrendingConnector:
    name: str = "CoinGecko: Trending"
    source_type: str = "public_json"
    status: str = "healthy"
    notes: str = "Crypto trending-search list; useful for retail liquidity, narrative, and risk-on/risk-off signals."

    async def fetch(self, limit: int) -> list[SourceRecord]:
        payload = await _fetch_json_any("https://api.coingecko.com/api/v3/search/trending")
        coins = payload.get("coins", []) if isinstance(payload, dict) else []
        records: list[SourceRecord] = []
        for rank, wrapper in enumerate(coins[:limit], start=1):
            item = wrapper.get("item") or {}
            coin_id = item.get("id") or item.get("coin_id") or item.get("name")
            name = item.get("name") or item.get("symbol") or ""
            if not coin_id or not name:
                continue
            records.append(
                SourceRecord(
                    source=self.name,
                    source_item_id=str(coin_id),
                    title=f"{name} ({item.get('symbol', '')}) trending on CoinGecko",
                    url=f"https://www.coingecko.com/en/coins/{quote(str(coin_id))}",
                    content=_clean_text(item.get("data", {}).get("content", {}).get("description") if isinstance(item.get("data"), dict) else ""),
                    published_at=datetime.utcnow(),
                    metrics={
                        "rank": rank,
                        "market_cap_rank": int(item.get("market_cap_rank") or 0),
                        "score": int(item.get("score") or 0),
                    },
                    payload={
                        "category": "crypto_trend",
                        "symbol": item.get("symbol"),
                        "thumb": item.get("thumb"),
                    },
                )
            )
        return records


@dataclass
class UsgsEarthquakeConnector:
    name: str = "USGS: Earthquakes"
    source_type: str = "public_geojson"
    status: str = "healthy"
    notes: str = "USGS significant earthquake feed; useful for disaster, logistics, insurance, energy, and supply-chain disruption monitoring."

    async def fetch(self, limit: int) -> list[SourceRecord]:
        url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_week.geojson"
        payload = await _fetch_json_any(url)
        features = payload.get("features", []) if isinstance(payload, dict) else []
        records: list[SourceRecord] = []
        for rank, feature in enumerate(features[:limit], start=1):
            props = feature.get("properties") or {}
            title = props.get("title") or props.get("place") or ""
            if not title:
                continue
            timestamp = props.get("time")
            published = datetime.utcfromtimestamp(timestamp / 1000) if isinstance(timestamp, (int, float)) else None
            records.append(
                SourceRecord(
                    source=self.name,
                    source_item_id=str(props.get("ids") or props.get("code") or title),
                    title=title[:300],
                    url=props.get("url"),
                    content=_clean_text(props.get("place") or ""),
                    published_at=published,
                    metrics={
                        "rank": rank,
                        "magnitude": float(props.get("mag") or 0),
                        "felt": int(props.get("felt") or 0),
                    },
                    payload={
                        "category": "natural_disaster",
                        "place": props.get("place"),
                        "type": props.get("type"),
                    },
                )
            )
        return records


def get_world_intel_connectors() -> list[Any]:
    return [
        *[
            GdeltDocConnector(name=name, query=query)
            for name, query in GDELT_QUERIES
        ],
        *[
            IntelRssConnector(name=name, url=url, category=category, notes=notes)
            for name, url, category, notes in INTEL_RSS_FEEDS
        ],
        PolymarketConnector(),
        CoinGeckoTrendingConnector(),
        UsgsEarthquakeConnector(),
    ]
