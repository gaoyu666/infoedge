from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from email.utils import parsedate_to_datetime
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from html import unescape
from typing import Any
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from app.core.config import settings
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CleanItem, Opportunity, OpportunityAnalysis, RawItem, Signal, SourceStatus
from app.services.opportunity_scoring import OpportunityScoringAgent
from app.services.sources import SourceRecord, get_connector_catalog, get_source_connectors
from app.services.translation_agent import ChineseLocalizationAgent


USER_AGENT = "InfoEdge/0.1 real-pipeline"
SOURCE_FETCH_TIMEOUT = 18
SOURCE_TASK_TIMEOUT = 45
OPPORTUNITY_MIN_SCORE = settings.opportunity_min_score
SCORING_AGENT = OpportunityScoringAgent()
TRANSLATION_AGENT = ChineseLocalizationAgent()

GITHUB_QUERY_SOURCES = [
    ("GitHub", "AI"),
    ("GitHub: Agents", "AI agent automation"),
    ("GitHub: Ecommerce", "ecommerce shopify amazon automation"),
    ("GitHub: Creator Tools", "creator marketing automation"),
]
REDDIT_SUBREDDIT_SOURCES = [
    ("Reddit", "artificial"),
    ("Reddit: r/Entrepreneur", "Entrepreneur"),
    ("Reddit: r/SideProject", "SideProject"),
    ("Reddit: r/SaaS", "SaaS"),
    ("Reddit: r/ecommerce", "ecommerce"),
    ("Reddit: r/shopify", "shopify"),
]
RSS_SOURCES = [
    ("Google Trends: US", "https://trends.google.com/trending/rss?geo=US", "search_trend"),
    ("Product Hunt: Feed", "https://www.producthunt.com/feed", "product_launch"),
    ("TechCrunch: AI", "https://techcrunch.com/category/artificial-intelligence/feed/", "tech_news"),
    ("TechCrunch: Startups", "https://techcrunch.com/category/startups/feed/", "startup_news"),
]
GATED_SOURCE_CATALOG = [
    ("ACLED", "needs_config", "Conflict and protest event data. Requires an API key; useful for country-risk and supply-chain disruption scoring."),
    ("FRED", "needs_config", "US and global macro series. Requires an API key; useful for interest-rate, inflation, and liquidity-cycle signals."),
    ("EIA Open Data", "needs_config", "Energy inventory and price data. Configure an API key for deeper commodity and energy disruption monitoring."),
    ("UN Comtrade", "needs_config", "Trade-flow data. Configure an API key for import/export and supply-chain opportunity analysis."),
    ("AkShare", "third_party", "A-share, macro, fund, futures, and financial alternative data from the daily_stock_analysis ecosystem; add only with dependency/runtime isolation."),
    ("Tushare", "needs_config", "China market fundamentals and daily bars. Requires a Tushare token before it can be used as a live connector."),
    ("Pytdx", "third_party", "Tongdaxin market quotes connector used by stock-analysis workflows; needs network/runtime hardening before production collection."),
    ("Baostock", "third_party", "China A-share historical quote and fundamentals library; useful for low-cost market backfill."),
    ("YFinance", "third_party", "Yahoo Finance market quotes and company data. Third-party library based access, so keep it behind a connector boundary."),
    ("Longbridge OpenAPI", "needs_config", "Brokerage-grade quotes, fundamentals, and trading-related data. Requires Longbridge credentials."),
    ("TickFlow", "needs_config", "Market-data provider used by daily_stock_analysis. Requires provider access before ingestion."),
    ("Finnhub", "needs_config", "Equities, news, sentiment, and fundamentals API. Requires FINNHUB_API_KEY."),
    ("AlphaVantage", "needs_config", "Market quotes, technical indicators, and fundamentals API. Requires ALPHAVANTAGE_API_KEY."),
    ("Anspire AI Search", "needs_config", "AI search provider referenced by daily_stock_analysis for news retrieval. Requires provider credentials."),
    ("SerpAPI", "needs_config", "Search result API for news and web trend discovery. Requires SERPAPI_API_KEY."),
    ("Tavily Search", "needs_config", "Search API for research/news discovery. Requires TAVILY_API_KEY."),
    ("Bocha Search", "needs_config", "Chinese web search API for trend/news collection. Requires provider credentials."),
    ("Brave Search", "needs_config", "Brave Web Search API for broader web discovery. Requires BRAVE_SEARCH_API_KEY."),
    ("MiniMax Search", "needs_config", "Search/research provider referenced by stock-analysis workflows. Requires provider credentials."),
    ("SearXNG", "needs_config", "Self-hosted metasearch endpoint; configure SEARXNG_URL before live collection."),
    ("Stock Sentiment API", "needs_config", "Market/news sentiment source referenced by stock-analysis workflows. Requires provider credentials."),
    ("OpenSky Network", "needs_config", "Aircraft state vectors and flight activity. Anonymous access is limited; credentials recommended for reliable collection."),
    ("Wingbits", "needs_config", "ADS-B/flight intelligence network source from WorldMonitor-style feeds. Requires provider access."),
    ("AISStream", "needs_config", "Live AIS maritime positions over websocket. Requires AISSTREAM_API_KEY and a streaming connector."),
    ("adsb.lol", "third_party", "Community ADS-B aircraft feed; public access should be rate-limited and cached."),
    ("Global Fishing Watch", "needs_config", "Fishing vessel activity and maritime risk signals. Requires API credentials."),
    ("Shodan", "needs_config", "Internet-exposed asset and cyber-risk search. Requires SHODAN_API_KEY."),
    ("DeepState Map", "third_party", "Conflict map feed useful for geopolitical disruption monitoring; treat as third-party derived OSINT."),
    ("Amtrak", "third_party", "Rail status and route disruption data source used by OSINT dashboards."),
    ("DigiTraffic", "third_party", "Finnish traffic, maritime, and road-condition open data source."),
    ("SatNOGS", "third_party", "Satellite ground-station observation network for space/satellite situational awareness."),
    ("TinyGS", "third_party", "Community satellite telemetry network; needs a dedicated parser before live ingestion."),
    ("Meshtastic MQTT", "third_party", "Public/community mesh telemetry stream; requires streaming ingestion and privacy filtering."),
    ("APRS-IS", "third_party", "Amateur radio packet reporting stream; requires streaming ingestion and location privacy rules."),
    ("KiwiSDR", "third_party", "Public software-defined radio receiver directory; useful for RF monitoring workflows."),
    ("OpenMHZ", "third_party", "Public radio/audio monitoring source; requires downstream transcription/classification to be useful."),
    ("OpenAQ", "third_party", "Global air-quality measurements; public API may require key depending on deployment."),
    ("WRI Global Power Plant Database", "third_party", "Power-plant reference data for energy infrastructure mapping."),
    ("NASA FIRMS", "needs_config", "Fire/hotspot observations. Requires NASA FIRMS MAP_KEY for stable API access."),
    ("NASA GIBS", "third_party", "Satellite imagery tiles; useful for visual verification rather than text signal ingestion."),
    ("Esri World Imagery", "third_party", "Basemap/imagery layer for geospatial context and validation."),
    ("Microsoft Planetary Computer", "needs_config", "Geospatial catalog and satellite assets. Requires signed access for some datasets."),
    ("Copernicus CDSE", "needs_config", "Sentinel/Copernicus satellite products. Requires account credentials and heavy geospatial processing."),
    ("VIIRS Nightlights", "third_party", "Nighttime-lights economic activity proxy; add as periodic geospatial batch source."),
    ("RestCountries", "third_party", "Country metadata reference source for enrichment and region normalization."),
    ("Wikidata", "third_party", "Entity graph for organization, geography, and infrastructure enrichment."),
    ("Wikipedia", "third_party", "Entity/article reference source for context enrichment."),
    ("Nominatim", "third_party", "OpenStreetMap geocoding. Requires strict user-agent and rate-limit compliance."),
    ("CARTO", "third_party", "Geospatial visualization/data platform source used by map-heavy monitoring projects."),
    ("IMF PortWatch", "third_party", "Port and maritime trade disruption data for supply-chain monitoring."),
    ("Cloudflare Radar", "needs_config", "Internet traffic, outage, and cyber trend API. Requires Cloudflare API credentials for deeper access."),
    ("Submarine Cable Map", "third_party", "Subsea cable reference data for infrastructure-risk context."),
    ("AbuseIPDB", "needs_config", "IP reputation and abuse reports. Requires ABUSEIPDB_API_KEY."),
    ("ICAO NOTAM", "needs_config", "Aviation notices. Reliable machine access usually requires provider credentials."),
    ("FAA ASWS", "needs_config", "Aviation weather/status source. Requires a dedicated aviation connector and compliance review."),
    ("Amazon SP-API", "needs_config", "官方 SP-API，需要卖家/开发者授权；适合订单、库存、搜索表现和店铺数据。"),
    ("Amazon Market Data", "third_party", "Best Sellers、价格、评论和竞品销量建议走 Keepa/Rainforest/SerpApi 等服务，公开抓取稳定性低。"),
    ("TikTok Shop/Creative Center", "needs_config", "TikTok 官方开发者/研究/商业内容接口需要申请；创意中心大规模采集更适合第三方数据服务。"),
    ("Meta Ads Library", "needs_config", "官方接口需要 Meta 开发者访问；商业广告覆盖存在限制，竞品广告建议配第三方聚合服务。"),
    ("Product Hunt API", "needs_config", "官方 GraphQL API 需要 token；公开 feed 已接入，API 用于补投票、评论和分类趋势。"),
    ("Shopify Admin/Storefront", "needs_config", "需要店铺授权或目标店铺清单；适合成交、商品、价格和库存监控。"),
    ("Etsy Open API", "needs_config", "需要开发者 API key；适合手工/设计类商品趋势和竞品列表。"),
    ("Google Play", "third_party", "可用 GitHub 上的 google-play-scraper 类库做榜单/评论采集，但属于非官方抓取链路。"),
    ("Apple App Store", "healthy", "Apple Marketing Tools RSS/JSON 无密钥，已接入美国 Top Free Apps 榜单。"),
    ("1688/淘宝/天猫", "restricted", "高价值中文供给侧源，但官方开放接口/反爬限制强，建议后续接服务商或自有授权。"),
    ("拼多多/Temu", "restricted", "高价值价格和爆品源，公开稳定 API 不足，建议后续接服务商或授权数据。"),
]

LOW_VALUE_TERMS = {
    "comedian",
    "meme",
    "memes",
    "funny",
    "joke",
    "shitpost",
    "satire",
    "strawberry mango",
}
ENTITY_STOPWORDS = {
    "The",
    "This",
    "That",
    "What",
    "When",
    "Where",
    "Why",
    "How",
    "Show",
    "Ask",
    "You",
    "Your",
    "With",
    "From",
    "Being",
    "Day",
}
TITLE_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "into",
    "onto",
    "your",
    "you",
    "are",
    "was",
    "were",
    "inc",
    "llc",
    "ltd",
    "corp",
    "company",
    "startup",
    "app",
}
TRACKING_QUERY_PREFIXES = ("utm_",)
TRACKING_QUERY_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid", "ref", "ref_src"}


def _hash_id(prefix: str, value: str, length: int = 14) -> str:
    digest = hashlib.sha1(value.encode("utf-8", errors="ignore")).hexdigest()[:length]
    return f"{prefix}-{digest}"


def _utcnow() -> datetime:
    return datetime.utcnow()


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _parse_rss_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = _parse_datetime(value)
    if parsed is not None:
        return parsed
    try:
        email_dt = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if email_dt.tzinfo is not None:
        email_dt = email_dt.astimezone(timezone.utc).replace(tzinfo=None)
    return email_dt


def _strip_html(value: str | None) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    return _normalize_text(text)


def _child_text(node: ElementTree.Element, *local_names: str) -> str:
    wanted = set(local_names)
    for child in list(node):
        local_name = child.tag.rsplit("}", 1)[-1]
        if local_name in wanted:
            return _normalize_text(child.text or "")
    return ""


def _parse_countish(value: str | int | float | None) -> int:
    if isinstance(value, (int, float)):
        return int(value)
    if not value:
        return 0
    text = str(value).lower().replace(",", "").replace("+", "").strip()
    multiplier = 1
    if text.endswith("k"):
        multiplier = 1000
        text = text[:-1]
    elif text.endswith("m"):
        multiplier = 1_000_000
        text = text[:-1]
    try:
        return int(float(text) * multiplier)
    except ValueError:
        digits = re.findall(r"\d+", text)
        return int(digits[0]) if digits else 0


def _canonical_url(url: str | None) -> str:
    if not url:
        return ""
    parsed = urlsplit(url.strip())
    if not parsed.scheme or not parsed.netloc:
        return url.strip().rstrip("/")
    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=False)
        if key not in TRACKING_QUERY_KEYS and not key.startswith(TRACKING_QUERY_PREFIXES)
    ]
    normalized_path = parsed.path.rstrip("/") or "/"
    if parsed.netloc.endswith("techcrunch.com") and normalized_path == "/" and parsed.query.startswith("p="):
        normalized_path = ""
    return urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower().removeprefix("www."),
            normalized_path,
            urlencode(query, doseq=True),
            "",
        )
    ).rstrip("/")


def _normalized_title(value: str | None) -> str:
    text = unescape(value or "").lower()
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", text)
    words = [word for word in text.split() if len(word) > 1 and word not in TITLE_STOPWORDS]
    return " ".join(words[:16])


def _cluster_key(record: SourceRecord, topic: str | None = None) -> str:
    canonical_url = _canonical_url(record.url)
    if canonical_url and not canonical_url.endswith("trending/rss?geo=US"):
        return f"url:{canonical_url}"
    title = _normalized_title(record.title)
    if title:
        return f"title:{record.source}:{title}"
    return f"item:{record.source}:{record.source_item_id}"


def _fetch_text(url: str) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json, application/atom+xml, */*"})
    with urlopen(request, timeout=SOURCE_FETCH_TIMEOUT) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


async def _fetch_json(url: str) -> dict[str, Any]:
    text = await asyncio.to_thread(_fetch_text, url)
    return json.loads(text)


async def _fetch_hacker_news_query(source: str, query_text: str, limit: int) -> list[SourceRecord]:
    query = quote(query_text)
    url = f"https://hn.algolia.com/api/v1/search_by_date?tags=story&query={query}&hitsPerPage={limit}"
    payload = await _fetch_json(url)
    records: list[SourceRecord] = []
    for item in payload.get("hits", []):
        title = item.get("title") or item.get("story_title") or ""
        if not title:
            continue
        records.append(
            SourceRecord(
                source=source,
                source_item_id=str(item.get("objectID") or item.get("story_id") or title),
                title=title,
                url=item.get("url") or f"https://news.ycombinator.com/item?id={item.get('objectID')}",
                content="",
                published_at=_parse_datetime(item.get("created_at")),
                metrics={"points": item.get("points") or 0, "comments": item.get("num_comments") or 0},
                payload=item,
            )
        )
    return records


async def _fetch_hacker_news(limit: int) -> list[SourceRecord]:
    return await _fetch_hacker_news_query("HackerNews", "AI", limit)


async def _fetch_github_query(source: str, query_text: str, limit: int) -> list[SourceRecord]:
    since = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")
    query = quote(f"created:>{since} {query_text}")
    url = f"https://api.github.com/search/repositories?q={query}&sort=stars&order=desc&per_page={limit}"
    payload = await _fetch_json(url)
    records: list[SourceRecord] = []
    for item in payload.get("items", []):
        full_name = item.get("full_name") or item.get("name") or ""
        description = item.get("description") or ""
        if not full_name:
            continue
        records.append(
            SourceRecord(
                source=source,
                source_item_id=str(item.get("id") or full_name),
                title=full_name,
                url=item.get("html_url"),
                content=description,
                published_at=_parse_datetime(item.get("created_at")),
                metrics={
                    "stars": item.get("stargazers_count") or 0,
                    "forks": item.get("forks_count") or 0,
                    "open_issues": item.get("open_issues_count") or 0,
                },
                payload={
                    "language": item.get("language"),
                    "topics": item.get("topics") or [],
                    "description": description,
                    "stars": item.get("stargazers_count") or 0,
                    "forks": item.get("forks_count") or 0,
                },
            )
        )
    return records


async def _fetch_github(limit: int) -> list[SourceRecord]:
    return await _fetch_github_query("GitHub", "AI", limit)


async def _fetch_arxiv(limit: int) -> list[SourceRecord]:
    url = f"https://export.arxiv.org/api/query?search_query=cat:cs.AI&sortBy=submittedDate&sortOrder=descending&max_results={limit}"
    text = await asyncio.to_thread(_fetch_text, url)
    root = ElementTree.fromstring(text)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    records: list[SourceRecord] = []
    for entry in root.findall("atom:entry", ns):
        title = " ".join((entry.findtext("atom:title", default="", namespaces=ns) or "").split())
        if not title:
            continue
        url_node = entry.find("atom:link[@rel='alternate']", ns)
        source_id = entry.findtext("atom:id", default=title, namespaces=ns) or title
        summary = " ".join((entry.findtext("atom:summary", default="", namespaces=ns) or "").split())
        records.append(
            SourceRecord(
                source="arXiv",
                source_item_id=source_id,
                title=title,
                url=url_node.attrib.get("href") if url_node is not None else source_id,
                content=summary,
                published_at=_parse_datetime(entry.findtext("atom:published", default="", namespaces=ns)),
                metrics={"papers": 1},
                payload={"summary": summary[:1000]},
            )
        )
    return records


async def _fetch_reddit_subreddit(source: str, subreddit: str, limit: int) -> list[SourceRecord]:
    url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit={limit}"
    payload = await _fetch_json(url)
    records: list[SourceRecord] = []
    for child in payload.get("data", {}).get("children", []):
        item = child.get("data", {})
        title = item.get("title") or ""
        if not title:
            continue
        created = item.get("created_utc")
        published = datetime.utcfromtimestamp(created) if isinstance(created, (int, float)) else None
        records.append(
            SourceRecord(
                source=source,
                source_item_id=item.get("id") or title,
                title=title,
                url=item.get("url") or f"https://www.reddit.com{item.get('permalink', '')}",
                content=item.get("selftext") or "",
                published_at=published,
                metrics={
                    "score": item.get("score") or 0,
                    "comments": item.get("num_comments") or 0,
                    "upvote_ratio": item.get("upvote_ratio") or 0,
                },
                payload={
                    "subreddit": item.get("subreddit_name_prefixed"),
                    "permalink": item.get("permalink"),
                    "domain": item.get("domain"),
                    "is_self": item.get("is_self"),
                    "post_hint": item.get("post_hint"),
                    "link_flair_text": item.get("link_flair_text"),
                    "over_18": item.get("over_18"),
                    "score": item.get("score") or 0,
                    "comments": item.get("num_comments") or 0,
                },
            )
        )
    return records


async def _fetch_reddit(limit: int) -> list[SourceRecord]:
    return await _fetch_reddit_subreddit("Reddit", "artificial", limit)


async def _fetch_rss_feed(source: str, url: str, category: str, limit: int) -> list[SourceRecord]:
    text = await asyncio.to_thread(_fetch_text, url)
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
        description = _strip_html(
            _child_text(item, "description", "summary", "encoded", "content") or title
        )
        guid = _child_text(item, "guid", "id")
        source_id = link or guid or title
        if source_id == url:
            source_id = title
        published = _parse_rss_datetime(_child_text(item, "pubDate", "published", "updated"))
        approx_traffic = _child_text(item, "approx_traffic", "traffic")
        records.append(
            SourceRecord(
                source=source,
                source_item_id=source_id,
                title=title,
                url=link or None,
                content=description,
                published_at=published,
                metrics={
                    "rss_rank": rank,
                    "traffic": _parse_countish(approx_traffic),
                },
                payload={
                    "category": category,
                    "rank": rank,
                    "traffic_label": approx_traffic,
                    "feed_url": url,
                },
            )
        )
    return records


async def _fetch_apple_app_store(limit: int) -> list[SourceRecord]:
    url = f"https://rss.applemarketingtools.com/api/v2/us/apps/top-free/{max(10, limit)}/apps.json"
    payload = await _fetch_json(url)
    results = payload.get("feed", {}).get("results", [])
    records: list[SourceRecord] = []
    for rank, item in enumerate(results[:limit], start=1):
        app_id = str(item.get("id") or item.get("url") or item.get("name"))
        name = item.get("name") or ""
        if not app_id or not name:
            continue
        genres = item.get("genres") or []
        genre_names = [genre.get("name", "") for genre in genres if isinstance(genre, dict)]
        records.append(
            SourceRecord(
                source="Apple App Store",
                source_item_id=app_id,
                title=name,
                url=item.get("url"),
                content=" ".join([item.get("artistName") or "", ", ".join(genre_names)]).strip(),
                published_at=None,
                metrics={"rank": rank, "genre_count": len(genre_names)},
                payload={
                    "rank": rank,
                    "artist": item.get("artistName"),
                    "genres": genre_names,
                    "release_date": item.get("releaseDate"),
                },
            )
        )
    return records


def _normalize_text(value: str) -> str:
    text = unescape(value or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:1800]


def _extract_keywords(text: str) -> list[str]:
    candidates = [
        "agent",
        "agents",
        "llm",
        "ai",
        "open-source",
        "github",
        "workflow",
        "automation",
        "security",
        "eval",
        "observability",
        "video",
        "data",
        "robot",
        "reasoning",
        "model",
        "developer",
        "ecommerce",
        "shopify",
        "amazon",
        "tiktok",
        "ads",
        "marketing",
        "creator",
        "saas",
        "startup",
        "store",
        "app",
        "pricing",
        "reviews",
        "trend",
        "funding",
        "financing",
        "venture",
        "investor",
        "investment",
        "ipo",
        "sec",
        "edgar",
        "form d",
        "13f",
        "fund",
        "acquisition",
        "merger",
        "融资",
        "投资",
        "创投",
        "上市",
        "并购",
    ]
    lower = text.lower()
    found = [word for word in candidates if word in lower]
    return found[:8] or ["ai"]


def _extract_entities(title: str) -> list[str]:
    words = re.findall(r"\b[A-Z][A-Za-z0-9_.-]{2,}\b", title)
    seen: list[str] = []
    for word in words:
        if word in ENTITY_STOPWORDS:
            continue
        if word not in seen:
            seen.append(word)
    return seen[:6]


def _quality_rejection_reason(record: SourceRecord) -> str | None:
    text = f"{record.title} {record.content}".lower()
    if any(term in text for term in LOW_VALUE_TERMS):
        return "low_value_topic"
    if record.payload.get("over_18"):
        return "over_18"
    if record.source.startswith("Reddit"):
        domain = str(record.payload.get("domain") or "")
        post_hint = str(record.payload.get("post_hint") or "")
        is_self = bool(record.payload.get("is_self"))
        comments = int(record.metrics.get("comments", 0) or 0)
        if not is_self and post_hint in {"image", "hosted:video"}:
            return "media_only"
        if domain in {"i.redd.it", "v.redd.it"}:
            return "media_only"
        if len(_normalize_text(record.content)) < 40 and comments < 15:
            return "thin_discussion"
    if record.source.startswith("HackerNews") and int(record.metrics.get("points", 0) or 0) <= 1 and int(record.metrics.get("comments", 0) or 0) == 0:
        return "low_engagement"
    return None


def _classify(record: SourceRecord, keywords: list[str]) -> tuple[str, str, str, str]:
    lower = " ".join([record.title, record.content, " ".join(keywords)]).lower()
    if record.source.startswith("GitHub"):
        return "开源项目", "AI/开发者圈", "全球", "Dev->大众"
    if record.source == "arXiv":
        return "研究前沿", "AI/深科技圈", "全球", "Research->Market"
    if record.source.startswith("Google Trends"):
        return "搜索需求飙升", "大众需求/搜索趋势", "美国", "Search->Demand"
    if record.source.startswith("Apple App Store"):
        return "消费应用趋势", "应用/消费者需求", "美国", "AppStore->Product"
    if record.source.startswith("Google Play"):
        return "消费应用趋势", "应用/消费者需求", "美国", "PlayStore->Product"
    if record.source.startswith("Shopify"):
        return "独立站商品供给", "电商/消费品", "全球", "Storefront->Supply"
    if record.source.startswith("Amazon"):
        return "Amazon 商品需求", "电商/消费品", "美国", "Marketplace->Demand"
    if record.source.startswith("SEC EDGAR: Form D"):
        return "私募融资披露", "投资/一级市场", "美国", "Capital->Startup"
    if record.source.startswith("SEC EDGAR: 13F"):
        return "机构持仓披露", "投资/二级市场", "美国", "Institution->Market"
    if record.source.startswith("SEC EDGAR: S-1"):
        return "IPO 管线", "投资/资本市场", "美国", "IPO->Market"
    if record.source.startswith("36Kr"):
        return "创投新闻", "投资/中文创投", "中国", "CN VC->Market"
    if record.source.startswith("GDELT"):
        return "Global macro signal", "International situation", "Global", "World->Business"
    if record.source.startswith("BBC") or record.source.startswith("Al Jazeera"):
        return "International news", "International situation", "Global", "World->Business"
    if record.source.startswith("Polymarket"):
        return "Prediction market", "Investment/macro", "Global", "Odds->Signal"
    if record.source.startswith("CoinGecko"):
        return "Crypto market trend", "Investment/crypto", "Global", "Retail->Liquidity"
    if record.source.startswith("USGS") or record.source.startswith("GDACS"):
        return "Disaster disruption", "Supply chain/risk", "Global", "Event->Supply"
    if record.source.startswith("CISA"):
        return "Cyber risk", "Infrastructure/cyber", "Global", "Risk->Vendor"
    if record.source.startswith("Product Hunt"):
        return "新品发布趋势", "创业/新品市场", "全球", "Launch->Demand"
    if record.source.startswith("TechCrunch"):
        return "创业/科技新闻", "创业/科技商业", "全球", "Startup->Market"
    if "ecommerce" in lower or "shopify" in lower or "amazon" in lower or "store" in lower:
        return "电商/独立站趋势", "电商/消费品", "全球", "Platform->Seller"
    if "marketing" in lower or "ads" in lower or "creator" in lower or "tiktok" in lower:
        return "投放/内容趋势", "增长/广告投放", "全球", "Attention->Sales"
    if "saas" in lower or "startup" in lower or "pricing" in lower:
        return "SaaS/创业趋势", "创业/科技商业", "全球", "Founder->Market"
    if "security" in lower or "risk" in lower or "harmful" in lower:
        return "风险/安全", "AI/深科技圈", "全球", "US->CN"
    if "agent" in lower or "llm" in lower or "workflow" in lower:
        return "AI 工具趋势", "AI/深科技圈", "全球", "Dev->大众"
    return "社区热议", "AI/深科技圈", "全球", "Global->CN"


def _score_record(record: SourceRecord) -> tuple[int, str, int]:
    metrics = record.metrics
    score = 58
    if record.source.startswith("GitHub"):
        score += min(28, int(metrics.get("stars", 0)) // 40)
        score += min(8, int(metrics.get("forks", 0)) // 35)
    elif record.source.startswith("HackerNews"):
        score += min(20, int(metrics.get("points", 0)) // 4)
        score += min(10, int(metrics.get("comments", 0)) // 2)
    elif record.source.startswith("Reddit"):
        score += min(24, int(metrics.get("score", 0)) // 45)
        score += min(10, int(metrics.get("comments", 0)) // 12)
        if not record.content and str(record.payload.get("post_hint") or "") in {"image", "hosted:video"}:
            score -= 20
        if int(metrics.get("comments", 0) or 0) < 5:
            score -= 8
    elif record.source == "arXiv":
        score += 10
    elif record.source.startswith("Google Trends"):
        rank = int(metrics.get("rss_rank", 20) or 20)
        score += max(0, 24 - rank * 2)
        score += min(10, int(metrics.get("traffic", 0) or 0) // 10_000)
    elif record.source.startswith("Apple App Store"):
        rank = int(metrics.get("rank", 50) or 50)
        score += max(0, 30 - rank)
    elif record.source.startswith("Google Play"):
        rank = int(metrics.get("rank", 50) or 50)
        score += max(0, 28 - rank)
        score += min(8, int(float(metrics.get("score", 0) or 0)))
    elif record.source.startswith("Shopify"):
        score += min(14, int(metrics.get("variants", 0) or 0))
        if float(metrics.get("min_price", 0) or 0) > 0:
            score += 5
    elif record.source.startswith("Amazon"):
        score += max(0, 24 - int(metrics.get("rank", 20) or 20) * 4)
        score += min(12, int(metrics.get("review_count", 0) or 0) // 200)
    elif record.source.startswith("SEC EDGAR"):
        score += 16
        if record.source.startswith("SEC EDGAR: Form D") or record.source.startswith("SEC EDGAR: S-1"):
            score += 6
    elif record.source.startswith("36Kr"):
        rank = int(metrics.get("rank", 20) or 20)
        score += max(0, 20 - rank * 2)
    elif record.source.startswith("GDELT"):
        rank = int(metrics.get("rank", 20) or 20)
        score += max(0, 18 - rank)
        if abs(float(metrics.get("tone", 0) or 0)) >= 3:
            score += 4
    elif record.source.startswith("BBC") or record.source.startswith("Al Jazeera"):
        rank = int(metrics.get("rank", 20) or 20)
        score += max(0, 16 - rank)
    elif record.source.startswith("Polymarket"):
        rank = int(metrics.get("rank", 20) or 20)
        score += max(0, 22 - rank)
        score += min(10, int(metrics.get("volume", 0) or 0) // 50_000)
        score += min(6, int(metrics.get("liquidity", 0) or 0) // 25_000)
    elif record.source.startswith("CoinGecko"):
        rank = int(metrics.get("rank", 20) or 20)
        score += max(0, 20 - rank * 2)
    elif record.source.startswith("USGS") or record.source.startswith("GDACS"):
        score += 12
        score += min(12, int(float(metrics.get("magnitude", 0) or 0) * 2))
    elif record.source.startswith("CISA"):
        rank = int(metrics.get("rank", 20) or 20)
        score += max(0, 18 - rank)
    elif record.source.startswith("Product Hunt"):
        rank = int(metrics.get("rss_rank", 20) or 20)
        score += max(0, 22 - rank)
    elif record.source.startswith("TechCrunch"):
        rank = int(metrics.get("rss_rank", 20) or 20)
        score += max(0, 18 - rank)
    if record.published_at and record.published_at >= datetime.utcnow() - timedelta(hours=24):
        score += 6
    if _quality_rejection_reason(record):
        score -= 25
    score = max(50, min(96, score))
    level = "S" if score >= 88 else "A" if score >= 76 else "B" if score >= 65 else "C"
    if record.source == "arXiv" or record.source.startswith("GitHub"):
        crowding_score = 20
    elif (
        record.source.startswith("Google Trends")
        or record.source.startswith("Apple App Store")
        or record.source.startswith("Google Play")
        or record.source.startswith("Shopify")
        or record.source.startswith("Amazon")
        or record.source.startswith("Product Hunt")
        or record.source.startswith("SEC EDGAR")
        or record.source.startswith("36Kr")
        or record.source.startswith("GDELT")
        or record.source.startswith("BBC")
        or record.source.startswith("Al Jazeera")
        or record.source.startswith("Polymarket")
        or record.source.startswith("CoinGecko")
        or record.source.startswith("USGS")
        or record.source.startswith("GDACS")
        or record.source.startswith("CISA")
    ):
        crowding_score = 48
    else:
        crowding_score = 32
    return score, level, crowding_score


def _opportunity_for(clean: CleanItem, score: int, level: str, crowding_score: int) -> Opportunity:
    metrics = clean.metrics or {}
    scorecard = SCORING_AGENT.score(
        source=clean.source,
        topic=clean.topic,
        circle=clean.circle,
        base_score=score,
        crowding_score=crowding_score,
        metrics=metrics,
        sources=metrics.get("evidence_sources") or [clean.source],
    )
    dimensions = {
        **scorecard.dimensions,
        "clean_item_id": clean.id,
        "raw_item_id": clean.raw_item_id,
        "source_record_id": clean.raw_item_id,
    }
    playbook = "ai_tool"
    playbook_name = "AI 工具机会验证"
    strategies = [
        "确认目标用户是否已经在社区表达痛点",
        "找到 3 个同类方案并比较差异",
        "做一个最小落地页或演示脚本",
        "用小流量测试转化和付费意愿",
    ]
    difficulty = "medium"
    investment = "2,000-8,000 元"
    estimated_return = "3,000-20,000 元 (30天)"
    roi = "1.2x - 3x"
    breakeven = "完成 20-40 次有效转化"
    max_loss = "2,000-8,000 元测试预算"

    if clean.source.startswith("GitHub"):
        playbook = "open_source"
        playbook_name = "开源项目产品化"
        strategies = ["复现项目核心能力", "定位非技术用户场景", "封装托管版 MVP", "在垂直社区收集首批试用"]
        investment = "3,000-15,000 元"
        estimated_return = "5,000-40,000 元 (30天)"
        roi = "1.5x - 4x"
        breakeven = "获取 10 个付费试用"
    elif clean.source == "arXiv":
        playbook = "research_to_market"
        playbook_name = "论文到应用验证"
        strategies = ["提炼论文可产品化模块", "寻找行业数据或 demo 场景", "做技术可行性验证", "联系潜在 B 端用户访谈"]
        difficulty = "high"
        investment = "5,000-30,000 元"
        estimated_return = "长期孵化，短期以验证为主"
        roi = "0.8x - 5x"
        breakeven = "完成 3 次行业访谈"
        max_loss = "验证时间与研发成本"
    elif clean.source.startswith("Reddit"):
        playbook = "community_signal"
        playbook_name = "社区痛点验证"
        strategies = ["归纳帖子下的具体抱怨", "做问卷或评论区访谈", "用无代码原型测试需求", "整理内容素材做引流"]
    elif clean.source.startswith("Google Trends"):
        playbook = "search_demand"
        playbook_name = "搜索需求验证"
        strategies = ["拆解上升搜索词背后的购买/信息需求", "检查 Amazon/TikTok/Google 结果页竞争密度", "做一页内容或商品集合页验证点击", "用小预算广告测试转化意图"]
        investment = "1,000-5,000 元"
        estimated_return = "2,000-15,000 元 (14天)"
        roi = "1.2x - 3x"
        breakeven = "获得 100 次有效点击或 10 个咨询"
    elif clean.source.startswith("Apple App Store"):
        playbook = "app_trend"
        playbook_name = "应用榜单趋势拆解"
        strategies = ["分析榜单应用的获客入口和付费点", "整理差评中的未满足需求", "找低复杂度功能做垂直版", "用落地页或插件验证细分人群"]
        investment = "3,000-20,000 元"
        estimated_return = "5,000-50,000 元 (30天)"
        roi = "1.3x - 4x"
        breakeven = "获得 20 个候补名单用户"
    elif clean.source.startswith("Google Play"):
        playbook = "app_trend"
        playbook_name = "安卓应用榜单拆解"
        strategies = ["拆解榜单应用的增长渠道和付费点", "抓取差评关键词验证痛点", "做更窄地区/人群/行业版本", "用内容和小预算广告验证安装意图"]
        investment = "3,000-18,000 元"
        estimated_return = "5,000-45,000 元 (30天)"
        roi = "1.3x - 4x"
        breakeven = "获得 500 次落地页访问或 30 个安装意向"
    elif clean.source.startswith("Shopify"):
        playbook = "shopify_supply"
        playbook_name = "独立站商品供给验证"
        strategies = ["归纳同类 Shopify 店铺的新品、价格带和卖点", "反查 Amazon/TikTok 是否已有需求", "用 1688/Temu 寻找供给替代", "做小批量落地页或广告素材测试"]
        investment = "2,000-12,000 元"
        estimated_return = "3,000-30,000 元 (30天)"
        roi = "1.2x - 3.5x"
        breakeven = "获得 20 个加购或 5 单测试订单"
    elif clean.source.startswith("Amazon"):
        playbook = "amazon_demand"
        playbook_name = "Amazon 需求轻验证"
        strategies = ["记录关键词下高频商品、价格带和评论量", "筛选评论多但差异化弱的商品", "找低成本供给源和内容切入点", "用小预算广告或联盟页验证购买意图"]
        investment = "2,000-15,000 元"
        estimated_return = "3,000-35,000 元 (30天)"
        roi = "1.2x - 3x"
        breakeven = "获得 10 单测试订单或 30 个询盘"
    elif clean.source.startswith("SEC EDGAR: Form D"):
        playbook = "funding_watch"
        playbook_name = "私募融资披露跟踪"
        strategies = ["识别融资主体、行业和募资规模", "查找公司官网、招聘和产品动态", "匹配同赛道国内外替代机会", "跟踪投资机构和后续新闻确认热度"]
        difficulty = "medium"
        investment = "0-3,000 元"
        estimated_return = "以线索发现和赛道判断为主"
        roi = "信息差"
        breakeven = "形成 5 条可跟踪赛道/公司清单"
    elif clean.source.startswith("SEC EDGAR: 13F"):
        playbook = "institution_watch"
        playbook_name = "机构持仓变化观察"
        strategies = ["识别提交机构和持仓披露周期", "对比上一期持仓方向", "筛选加仓集中行业和热门标的", "结合新闻和财报判断是否可跟随或反向验证"]
        difficulty = "high"
        investment = "0-5,000 元"
        estimated_return = "以投资研究线索为主"
        roi = "研究收益"
        breakeven = "形成 3 个机构共识方向"
    elif clean.source.startswith("SEC EDGAR: S-1"):
        playbook = "ipo_pipeline"
        playbook_name = "IPO 管线机会观察"
        strategies = ["识别拟上市公司行业、增长和风险披露", "拆解招股书中的供应商/客户/竞品", "寻找上下游服务或内容机会", "追踪同赛道估值和二级市场反馈"]
        difficulty = "high"
        investment = "0-5,000 元"
        estimated_return = "以研究和机会储备为主"
        roi = "研究收益"
        breakeven = "形成 3 条 IPO 产业链机会"
    elif clean.source.startswith("36Kr"):
        playbook = "china_vc_news"
        playbook_name = "中文创投动态跟踪"
        strategies = ["提取融资公司、金额、轮次和投资方", "判断是否代表新需求或新供给", "对照 GitHub/产品/电商源验证落地方向", "沉淀赛道地图和潜在合作对象"]
        investment = "0-3,000 元"
        estimated_return = "以线索发现和选题判断为主"
        roi = "信息差"
        breakeven = "形成 10 条有效投融资线索"
    elif clean.source.startswith("GDELT") or clean.source.startswith("BBC") or clean.source.startswith("Al Jazeera"):
        playbook = "global_situation_watch"
        playbook_name = "Global situation opportunity watch"
        strategies = [
            "Map the event to affected sectors, routes, countries, and import/export exposure",
            "Check whether the same theme appears in markets, search, and official data",
            "Build a short watchlist of products, suppliers, or services that benefit from the shift",
            "Run a small content, sourcing, or outreach test before capital commitment",
        ]
        difficulty = "medium"
        investment = "0-5,000 CNY"
        estimated_return = "Information edge first; validate with a small commercial test"
        roi = "research edge"
        breakeven = "Produce 3 actionable sector or supplier leads"
    elif clean.source.startswith("Polymarket"):
        playbook = "prediction_market_watch"
        playbook_name = "Prediction market leading-signal watch"
        strategies = [
            "Separate real information from speculation by checking news and official sources",
            "Track volume and liquidity changes around the same question",
            "Map probability shifts to sectors, supply chains, or marketing timing",
            "Use the signal for watchlist building, not blind trading",
        ]
        difficulty = "medium"
        investment = "0-3,000 CNY"
        estimated_return = "Information edge / timing edge"
        roi = "research edge"
        breakeven = "Find 3 signals confirmed by another source"
    elif clean.source.startswith("CoinGecko"):
        playbook = "crypto_narrative_watch"
        playbook_name = "Crypto narrative and liquidity watch"
        strategies = [
            "Identify the narrative behind the trending asset",
            "Check whether the same theme appears in developer, search, and social sources",
            "Avoid direct exposure until liquidity and downside are clear",
            "Look for tool, content, community, or B2B service angles around the narrative",
        ]
        difficulty = "high"
        investment = "0-3,000 CNY"
        estimated_return = "Narrative lead generation; trading only after separate risk review"
        roi = "high variance"
        breakeven = "Create a watchlist of 5 narrative-linked opportunities"
    elif clean.source.startswith("USGS") or clean.source.startswith("GDACS"):
        playbook = "disruption_watch"
        playbook_name = "Disaster and supply-chain disruption watch"
        strategies = [
            "Map affected geography to ports, factories, commodities, tourism, and insurance exposure",
            "Check logistics, commodity, and local news confirmation",
            "Find short-term demand for replacement supply, repair, relocation, or information services",
            "Act only where there is a legal and ethical service angle",
        ]
        difficulty = "medium"
        investment = "0-5,000 CNY"
        estimated_return = "Lead discovery and risk avoidance"
        roi = "research edge"
        breakeven = "Identify 2 affected sectors with practical next steps"
    elif clean.source.startswith("CISA"):
        playbook = "cyber_vendor_watch"
        playbook_name = "Cyber advisory vendor-risk watch"
        strategies = [
            "Identify affected vendors, products, and customer segments",
            "Check exploit maturity and urgency from official advisories",
            "Package remediation, monitoring, content, or procurement alternatives",
            "Validate demand with 5 targeted outreach messages",
        ]
        difficulty = "medium"
        investment = "0-5,000 CNY"
        estimated_return = "Service leads / vendor-risk content opportunities"
        roi = "1.2x - 3x"
        breakeven = "Get 3 qualified conversations"
    elif clean.source.startswith("Product Hunt"):
        playbook = "product_launch"
        playbook_name = "新品发布复盘"
        strategies = ["拆解新品的目标人群、定价和首屏卖点", "查看同类产品评论里的未满足场景", "做更窄的中文/行业版验证", "用目录站、内容和冷启动社群获取首批线索"]
        investment = "2,000-10,000 元"
        estimated_return = "3,000-30,000 元 (30天)"
        roi = "1.2x - 3.5x"
        breakeven = "获得 15 个试用或 5 个付费意向"
    elif clean.source.startswith("TechCrunch"):
        playbook = "startup_watch"
        playbook_name = "融资/新品机会观察"
        strategies = ["识别新闻里的新预算流向", "找国内/垂直行业是否有替代需求", "建立竞品和关键词监控", "用咨询/代理/轻产品先验证"]
        investment = "2,000-12,000 元"
        estimated_return = "3,000-30,000 元 (30天)"
        roi = "1.1x - 3x"

    return Opportunity(
        id=_hash_id("op-live", clean.id, 18),
        signal_id=_hash_id("live", clean.raw_item_id, 20),
        score=scorecard.score,
        level=scorecard.level,
        dimensions=dimensions,
        playbook=playbook,
        playbook_name=playbook_name,
        window_hours=72 if clean.source != "arXiv" else 168,
        strategies=strategies,
        crowding_score=crowding_score,
        risk_level=scorecard.risk_level,
        risk_factors=scorecard.risk_factors,
        validation_score=scorecard.validation_score,
        bear_case="当前只是公开源早期信号，需要进一步验证用户付费意愿和可执行路径。",
        difficulty=difficulty,
        estimated_investment=investment,
        estimated_return=estimated_return,
        roi_ratio=roi,
        breakeven=breakeven,
        max_loss=max_loss,
        execution_status="not_started",
        current_step=0,
        status="new",
        created_at=_utcnow(),
    )


def _analysis_lens(playbook: str, source: str) -> dict[str, Any]:
    text = f"{playbook} {source}".lower()
    if "crypto" in text or "coingecko" in text:
        return {
            "plain_type": "加密市场叙事信号",
            "why_opportunity": "热门资产本身不等于可买入标的，但它会暴露资金、社区和搜索注意力正在聚集的主题。商业机会通常在工具、内容、社群、数据监控、风控和 B2B 服务侧。",
            "who_needs_it": ["加密投资者", "研究员和内容团队", "交易社群", "风控/监控工具用户"],
            "business_angles": ["主题研究报告", "监控面板订阅", "社群线索", "风控工具或 API"],
            "validation_plan": ["拆出资产背后的叙事关键词", "检查搜索、社媒、开发者活动是否同步升温", "做一页专题/监控页测试收藏和订阅"],
            "no_go_signals": ["只有单日价格波动，没有搜索或社区跟进", "流动性很差或容易被操纵", "用户只关心短线喊单，不愿意为工具/内容付费"],
        }
    if "prediction" in text or "polymarket" in text:
        return {
            "plain_type": "预测市场领先信号",
            "why_opportunity": "预测市场把分散信息压缩成概率和交易量。机会不一定是下注，而是利用概率变化提前准备供应链、内容、采购、投研或风控动作。",
            "who_needs_it": ["投资研究者", "跨境商家", "供应链团队", "新闻/内容团队"],
            "business_angles": ["事件监控简报", "行业预警服务", "交易/采购决策支持", "垂直内容订阅"],
            "validation_plan": ["看概率是否连续变化，而不是单笔噪声", "找官方新闻或市场数据交叉验证", "列出会受影响的国家、行业、商品和公司"],
            "no_go_signals": ["成交量很低", "事件无法映射到商业动作", "没有第二来源确认"],
        }
    if "global_situation" in text or "bbc" in text or "al jazeera" in text or "gdelt" in text:
        return {
            "plain_type": "国际局势/宏观事件信号",
            "why_opportunity": "国际新闻本身不是项目，项目来自它引发的价格、供应、渠道、监管、情绪或需求变化。要把事件映射到行业、地区、商品、服务和客户预算。",
            "who_needs_it": ["跨境卖家", "外贸/采购团队", "投研人员", "行业内容团队"],
            "business_angles": ["行业情报简报", "采购替代清单", "风险预警服务", "专题内容和线索获客"],
            "validation_plan": ["判断受影响地区和行业", "查是否会影响价格、交付、监管或消费心理", "找 2 个市场数据或官方来源确认"],
            "no_go_signals": ["只是大新闻但没有商业链路", "影响太泛，无法落到具体客户", "没有时效优势"],
        }
    if "cyber" in text or "cisa" in text:
        return {
            "plain_type": "网络安全/供应商风险信号",
            "why_opportunity": "安全公告意味着某些软件、供应商或客户群体短期会产生修复、替代、审计、培训和采购需求。机会在服务包装、工具监控、内容获客和替代方案。",
            "who_needs_it": ["中小企业 IT 负责人", "安全服务商", "采购/合规团队", "使用受影响产品的公司"],
            "business_angles": ["修复服务包", "漏洞监控订阅", "替代供应商清单", "安全内容获客"],
            "validation_plan": ["识别受影响厂商和产品", "确认漏洞严重性和利用成熟度", "列出目标客户行业", "发 5-10 条定向触达测试需求"],
            "no_go_signals": ["公告影响面很小", "没有明确受影响客户", "需要高资质交付但自己没有能力"],
        }
    if "product_launch" in text or "product hunt" in text:
        return {
            "plain_type": "新品发布/竞品拆解信号",
            "why_opportunity": "新品发布说明有团队正在验证某类需求。机会不是照抄产品，而是拆它的目标用户、定价、获客入口和差评空白，找到更窄的人群或本地化版本。",
            "who_needs_it": ["SaaS 创业者", "产品经理", "垂直行业服务商", "内容/增长团队"],
            "business_angles": ["更窄垂直版工具", "中文/行业版替代", "竞品目录和评测内容", "模板或自动化服务"],
            "validation_plan": ["拆首屏卖点和定价", "找同类产品评论里的未满足需求", "做一页替代方案测试点击/咨询", "联系 5 个目标用户确认痛点"],
            "no_go_signals": ["只有猎奇没有目标用户", "同类产品过多且无差异化", "用户不愿迁移或付费"],
        }
    return {
        "plain_type": "商业信号",
        "why_opportunity": "系统把公开数据源中的热度、时效、供需、竞争和执行难度转成一个可验证假设。它不是最终项目结论，而是值得用小成本继续验证的商业线索。",
        "who_needs_it": ["目标行业用户", "内容/投研团队", "中小商家", "垂直服务商"],
        "business_angles": ["信息差服务", "工具订阅", "线索获客", "小型服务包"],
        "validation_plan": ["确认真实受众是谁", "找到至少 2 个额外证据源", "做落地页、内容页或小样本触达"],
        "no_go_signals": ["没有明确客户", "不能转成可执行动作", "只有热度没有付费或采购意图"],
    }


def _display_title_for_analysis(source: str, title: str) -> str:
    if source.startswith("CoinGecko"):
        return re.sub(r"\s+(trending|趋势ing)\s+on\s+CoinGecko\b", " 在 CoinGecko 热门", title, flags=re.IGNORECASE)
    return title.replace("趋势ing", "趋势")


def _analysis_action(source: str, playbook: str, playbook_name: str) -> str:
    text = f"{source} {playbook} {playbook_name}".lower()
    if "cisa" in text or "cyber" in text:
        return "做修复服务/替代方案"
    if "gdacs" in text or "usgs" in text or "disaster" in text or "earthquake" in text:
        return "做供应链风险预警"
    if "polymarket" in text or "prediction" in text:
        return "做事件监控/投研清单"
    if "coingecko" in text or "crypto" in text:
        return "做叙事监控/内容工具"
    if "bbc" in text or "al jazeera" in text or "gdelt" in text or "global_situation" in text:
        return "做行业影响清单"
    if "sec edgar: 13f" in text or "institution" in text:
        return "跟踪机构共识"
    if "sec edgar: s-1" in text or "ipo" in text:
        return "拆产业链/竞品"
    if "sec edgar: form d" in text or "funding" in text or "36kr" in text:
        return "找赛道和销售线索"
    if "amazon" in text:
        return "验证价格带/差评痛点"
    if "shopify" in text or "ecommerce" in text:
        return "验证供给和独立站卖点"
    if "app store" in text or "google play" in text or "app_trend" in text:
        return "拆功能缺口/垂直替代"
    if "google trends" in text or "search" in text:
        return "做落地页测需求"
    if "product hunt" in text or "product_launch" in text:
        return "拆竞品/做窄版替代"
    if "reddit" in text or "community" in text:
        return "访谈痛点/做 MVP"
    if "github" in text or "open_source" in text:
        return "封装托管版/行业版"
    if "arxiv" in text or "research" in text:
        return "做 Demo/行业验证"
    return "小成本验证"


def _analysis_title_theme(source: str, playbook: str, playbook_name: str, fallback: str) -> str:
    text = f"{source} {playbook} {playbook_name}".lower()
    if "cisa" in text or "cyber" in text:
        return "网络安全服务机会"
    if "gdacs" in text or "usgs" in text or "disaster" in text or "earthquake" in text:
        return "供应链风险机会"
    if "polymarket" in text or "prediction" in text:
        return "事件预警机会"
    if "coingecko" in text or "crypto" in text:
        return "加密叙事机会"
    if "bbc" in text or "al jazeera" in text or "gdelt" in text or "global_situation" in text:
        return "国际局势机会"
    if "sec edgar: 13f" in text or "institution" in text:
        return "机构持仓机会"
    if "sec edgar: s-1" in text or "ipo" in text:
        return "IPO 管线机会"
    if "sec edgar: form d" in text or "funding" in text or "36kr" in text:
        return "融资线索机会"
    if "amazon" in text or "shopify" in text or "ecommerce" in text:
        return "电商选品机会"
    if "app store" in text or "google play" in text or "app_trend" in text:
        return "应用拆解机会"
    if "google trends" in text or "search" in text:
        return "搜索需求机会"
    if "product hunt" in text or "product_launch" in text:
        return "新品拆解机会"
    if "reddit" in text or "community" in text:
        return "社区痛点机会"
    if "github" in text or "open_source" in text:
        return "开源产品化机会"
    if "arxiv" in text or "research" in text:
        return "技术转化机会"
    return fallback or "商业验证机会"


def _analysis_object_label(title: str) -> str:
    text = re.sub(
        r"^(开源项目|新品发布|应用榜单|搜索趋势|论文方向|Amazon 商品|科技新闻|社区讨论|融资动向|机构持仓|IPO 管线)[：:]\s*",
        "",
        title,
        flags=re.IGNORECASE,
    )
    text = text.replace(" - ", " ").replace(" | ", " ")
    return text[:54].rstrip()


def _opportunity_analysis_for(clean: CleanItem, opportunity: Opportunity) -> OpportunityAnalysis:
    metrics = clean.metrics or {}
    title = _display_title_for_analysis(clean.source, str(metrics.get("title_zh") or clean.title or metrics.get("title_original") or ""))
    content = _normalize_text(str(metrics.get("content_zh") or clean.summary or metrics.get("content_original") or title))
    if len(content) > 220:
        content = f"{content[:217].rstrip()}..."
    lens = _analysis_lens(opportunity.playbook, clean.source)
    dimensions = opportunity.dimensions or {}
    sources = dimensions.get("sources") or metrics.get("evidence_sources") or [clean.source]
    evidence_count = int(dimensions.get("evidence_count") or metrics.get("evidence_count") or 1)
    analysis = {
        "plain_type": lens["plain_type"],
        "what_it_is": f"这不是一个已经包装好的项目，而是一条来自「{clean.source}」的{lens['plain_type']}。原始信号是：{title}。",
        "source_context": content,
        "why_opportunity": lens["why_opportunity"],
        "why_now": [
            f"机会分 {opportunity.score}，验证分 {opportunity.validation_score}，说明它已经超过系统的候选机会阈值。",
            f"当前有 {evidence_count} 个证据源：{'、'.join(sources[:4]) if isinstance(sources, list) else clean.source}。",
            f"窗口期 {opportunity.window_hours} 小时，适合先做轻量验证而不是直接重投入。",
        ],
        "who_needs_it": lens["who_needs_it"],
        "business_angles": lens["business_angles"],
        "validation_plan": lens["validation_plan"],
        "no_go_signals": lens["no_go_signals"],
        "merchant_take": f"我的判断：先把它当作「{opportunity.playbook_name}」方向的线索，用 {opportunity.window_hours} 小时窗口验证是否有真实客户动作。分数 {opportunity.score}，验证分 {opportunity.validation_score}，不适合跳过验证直接重仓。",
        "score_explanation": {
            "risk_level": opportunity.risk_level,
            "crowding_score": opportunity.crowding_score,
            "score": opportunity.score,
            "validation_score": opportunity.validation_score,
        },
    }
    return OpportunityAnalysis(
        opportunity_id=opportunity.id,
        source=clean.source[:80],
        title=f"{_analysis_title_theme(clean.source, opportunity.playbook, opportunity.playbook_name, lens['plain_type'])}｜{_analysis_object_label(title)}｜{_analysis_action(clean.source, opportunity.playbook, opportunity.playbook_name)}"[:240],
        evidence_title=title[:300],
        analysis=analysis,
        generated_by="MerchantAnalysisAgent",
        created_at=_utcnow(),
        updated_at=_utcnow(),
    )


def _signal_for(clean: CleanItem, score: int, level: str, crowding_score: int) -> Signal:
    crowding = "蓝海" if crowding_score <= 25 else "早期" if crowding_score <= 45 else "拥挤"
    is_research = clean.source == "arXiv"
    return Signal(
        id=_hash_id("live", clean.raw_item_id, 20),
        level=level,
        score=score,
        title=clean.title[:240],
        type=clean.topic,
        gap=clean.metrics.get("gap", "Global->CN") if clean.metrics else "Global->CN",
        window="72h" if not is_research else "7d",
        circle=clean.circle,
        region=clean.region,
        crowding=crowding,
        risk="中风险" if is_research else "低风险",
        difficulty="高门槛" if is_research else "中门槛",
        sources=[clean.source],
        time_label="刚刚",
        roi_label="1.2x-4x",
        convergence="真实源采集",
        created_at=_utcnow(),
    )


def _level_for_score(score: int) -> str:
    return "S" if score >= 88 else "A" if score >= 76 else "B" if score >= 65 else "C"


def _merge_signal(signal: Signal, clean: CleanItem, record: SourceRecord, score: int) -> bool:
    sources = list(signal.sources or [])
    changed = False
    if clean.source not in sources:
        sources.append(clean.source)
        signal.sources = sources
        changed = True
    evidence_count = max(len(sources), int((clean.metrics or {}).get("evidence_count", 1) or 1))
    boosted = min(96, max(signal.score, score) + min(10, (evidence_count - 1) * 3))
    if boosted != signal.score:
        signal.score = boosted
        signal.level = _level_for_score(boosted)
        changed = True
    signal.convergence = "多源聚合" if len(sources) > 1 else signal.convergence or "真实源采集"
    signal.time_label = "刚刚"
    if changed and len(clean.title or "") > len(signal.title):
        signal.title = clean.title[:240]
    return changed


def _merge_opportunity(opportunity: Opportunity, score: int, source_count: int) -> None:
    dimensions = opportunity.dimensions or {}
    dimensions["evidence_count"] = max(int(dimensions.get("evidence_count", 1) or 1), source_count)
    dimensions["merged_by"] = SCORING_AGENT.name
    opportunity.dimensions = dimensions
    opportunity.score = min(96, max(opportunity.score, score - 4) + min(8, max(0, source_count - 1) * 2))
    opportunity.level = _level_for_score(opportunity.score)
    opportunity.validation_score = min(96, max(opportunity.validation_score, score))
    opportunity.status = "new" if opportunity.status == "filtered" else opportunity.status


async def _upsert_source_status(db: AsyncSession, source: str, status: str, count: int, notes: str) -> None:
    row = (
        await db.execute(select(SourceStatus).where(SourceStatus.source == source))
    ).scalar_one_or_none()
    if row is None:
        row = SourceStatus(
            id=_hash_id("src-live", source, 10),
            source=source,
            status=status,
            freshness="fresh" if count else "stale",
            signal_count_24h=count,
            notes=notes,
            last_checked=_utcnow(),
        )
        db.add(row)
    else:
        row.status = status
        row.freshness = "fresh" if count else "stale"
        row.signal_count_24h = count
        row.notes = notes
        row.last_checked = _utcnow()


async def _store_record(db: AsyncSession, record: SourceRecord) -> tuple[bool, bool]:
    raw_id = _hash_id("raw", f"{record.source}:{record.source_item_id}", 18)
    localized = TRANSLATION_AGENT.localize(record)
    translation_meta = TRANSLATION_AGENT.metadata(record, localized)
    raw = await db.get(RawItem, raw_id)
    inserted_raw = False
    if raw is None:
        raw = RawItem(
            id=raw_id,
            source=record.source,
            source_item_id=record.source_item_id,
            title=record.title[:300],
            url=record.url,
            content=_normalize_text(record.content),
            payload={**record.payload, **translation_meta},
            published_at=record.published_at,
            fetched_at=_utcnow(),
        )
        db.add(raw)
        inserted_raw = True
    else:
        raw.fetched_at = _utcnow()
        raw.payload = {**(raw.payload or {}), **record.payload, **translation_meta}

    clean_id = _hash_id("clean", raw_id, 18)
    clean = await db.get(CleanItem, clean_id)
    clean_text = _normalize_text(f"{localized.title}. {localized.content}")
    keywords = _extract_keywords(clean_text)
    topic, circle, region, gap = _classify(record, keywords)
    inserted_signal = False
    if clean is None:
        clean = CleanItem(
            id=clean_id,
            raw_item_id=raw_id,
            source=record.source,
            title=_normalize_text(localized.title)[:300],
            summary=clean_text[:600],
            url=record.url,
            topic=topic,
            circle=circle,
            region=region,
            keywords=keywords,
            entities=_extract_entities(record.title),
            metrics={**record.metrics, "gap": gap, **translation_meta},
            published_at=record.published_at,
            created_at=_utcnow(),
        )
        db.add(clean)
    else:
        clean.title = _normalize_text(localized.title)[:300]
        clean.summary = clean_text[:600]
        clean.keywords = keywords
        clean.metrics = {**record.metrics, "gap": gap, **translation_meta}

    score, level, crowding_score = _score_record(record)
    signal_id = _hash_id("live", raw_id, 20)
    if await db.get(Signal, signal_id) is None:
        db.add(_signal_for(clean, score, level, crowding_score))
        inserted_signal = True

    opportunity_id = _hash_id("op-live", clean_id, 18)
    if score >= 65 and await db.get(Opportunity, opportunity_id) is None:
        db.add(_opportunity_for(clean, score, level, crowding_score))

    return inserted_raw, inserted_signal


async def _existing_ids(db: AsyncSession, model_cls, ids: list[str]) -> set[str]:
    if not ids:
        return set()
    rows = await db.execute(select(model_cls.id).where(model_cls.id.in_(ids)))
    return set(rows.scalars().all())


async def _existing_clean_by_cluster(db: AsyncSession, cluster_keys: list[str]) -> dict[str, CleanItem]:
    keys = [key for key in set(cluster_keys) if key]
    if not keys:
        return {}
    rows = (
        await db.execute(
            select(CleanItem).where(CleanItem.metrics["cluster_key"].as_string().in_(keys))
        )
    ).scalars().all()
    by_key: dict[str, CleanItem] = {}
    for row in rows:
        key = (row.metrics or {}).get("cluster_key")
        if key and key not in by_key:
            by_key[key] = row
    return by_key


async def _filter_historical_duplicates(db: AsyncSession, limit: int = 600) -> int:
    rows = (
        await db.execute(
            select(Signal)
            .where(Signal.id.like("live-%"))
            .order_by(Signal.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    groups: dict[str, list[Signal]] = {}
    for signal in rows:
        source = (signal.sources or [""])[0]
        title = _normalized_title(signal.title)
        if not source or not title:
            continue
        groups.setdefault(f"{source}:{title}", []).append(signal)

    duplicate_signal_ids: list[str] = []
    for signals in groups.values():
        if len(signals) <= 1:
            continue
        keeper = max(signals, key=lambda item: (item.score, item.created_at))
        for signal in signals:
            if signal.id == keeper.id:
                continue
            signal.score = min(signal.score, 45)
            signal.level = "C"
            signal.convergence = "历史重复已降级"
            signal.risk = "高风险"
            signal.time_label = "已复核"
            duplicate_signal_ids.append(signal.id)

    if duplicate_signal_ids:
        opportunities = (
            await db.execute(select(Opportunity).where(Opportunity.signal_id.in_(duplicate_signal_ids)))
        ).scalars().all()
        for opportunity in opportunities:
            opportunity.score = min(opportunity.score, 40)
            opportunity.level = "C"
            opportunity.status = "filtered"
            opportunity.risk_level = "high"
            opportunity.bear_case = "历史去重维护判定该机会对应重复信号，已降级为过滤状态。"
    return len(duplicate_signal_ids)


async def _backfill_opportunity_scorecards(db: AsyncSession, limit: int = 300) -> int:
    opportunities = (
        await db.execute(
            select(Opportunity)
            .where(Opportunity.id.like("op-live-%"))
            .where(Opportunity.status != "filtered")
            .order_by(Opportunity.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    updated = 0
    for opportunity in opportunities:
        dimensions = opportunity.dimensions or {}
        if dimensions.get("agent") == SCORING_AGENT.name:
            continue
        signal = await db.get(Signal, opportunity.signal_id)
        if signal is None:
            continue
        scorecard = SCORING_AGENT.score(
            source=(signal.sources or ["unknown"])[0],
            topic=signal.type,
            circle=signal.circle,
            base_score=signal.score,
            crowding_score=opportunity.crowding_score,
            metrics={"evidence_count": len(signal.sources or [])},
            sources=signal.sources or [],
        )
        opportunity.score = scorecard.score
        opportunity.level = scorecard.level
        opportunity.dimensions = scorecard.dimensions
        opportunity.risk_level = scorecard.risk_level
        opportunity.validation_score = scorecard.validation_score
        opportunity.risk_factors = scorecard.risk_factors
        updated += 1
    return updated


async def _backfill_chinese_localization(db: AsyncSession, limit: int = 500) -> int:
    rows = (
        await db.execute(
            select(CleanItem)
            .order_by(CleanItem.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    updated = 0
    for clean in rows:
        metrics = clean.metrics or {}
        if metrics.get("translation_agent") == TRANSLATION_AGENT.name and metrics.get("translated_to") == "zh":
            continue
        original_title = str(metrics.get("title_original") or clean.title or "")
        original_content = str(metrics.get("content_original") or clean.summary or "")
        record = SourceRecord(
            source=clean.source,
            source_item_id=clean.raw_item_id,
            title=original_title,
            url=clean.url,
            content=original_content,
            published_at=clean.published_at,
            metrics=metrics,
            payload={},
        )
        localized = TRANSLATION_AGENT.localize(record)
        translation_meta = TRANSLATION_AGENT.metadata(record, localized)
        clean.title = _normalize_text(localized.title)[:300]
        clean.summary = _normalize_text(f"{localized.title}. {localized.content}")[:600]
        clean.metrics = {**metrics, **translation_meta}

        raw = await db.get(RawItem, clean.raw_item_id)
        if raw is not None:
            raw.payload = {**(raw.payload or {}), **translation_meta}

        signal = await db.get(Signal, _hash_id("live", clean.raw_item_id, 20))
        if signal is not None:
            signal.title = clean.title[:240]
        updated += 1
    return updated


async def _backfill_opportunity_evidence_ids(db: AsyncSession, limit: int = 500) -> int:
    opportunities = (
        await db.execute(
            select(Opportunity)
            .where(Opportunity.id.like("op-live-%"))
            .where(Opportunity.status != "filtered")
            .order_by(Opportunity.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    updated = 0
    for opportunity in opportunities:
        dimensions = opportunity.dimensions or {}
        if dimensions.get("clean_item_id") and dimensions.get("raw_item_id"):
            continue
        signal = await db.get(Signal, opportunity.signal_id)
        clean = None
        if signal is not None and signal.title:
            clean = (
                await db.execute(
                    select(CleanItem)
                    .where(CleanItem.title == signal.title)
                    .order_by(CleanItem.created_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
        if clean is None:
            continue
        opportunity.dimensions = {
            **dimensions,
            "clean_item_id": clean.id,
            "raw_item_id": clean.raw_item_id,
            "source_record_id": clean.raw_item_id,
        }
        updated += 1
    return updated


async def _store_records_batch(db: AsyncSession, records: list[SourceRecord]) -> dict[str, Any]:
    accepted_records: list[SourceRecord] = []
    rejected_records: list[SourceRecord] = []
    rejected: list[dict[str, str]] = []
    rejected_by_source: dict[str, int] = {}
    for record in records:
        reason = _quality_rejection_reason(record)
        if reason:
            rejected_records.append(record)
            rejected.append({"source": record.source, "id": record.source_item_id, "reason": reason})
            rejected_by_source[record.source] = rejected_by_source.get(record.source, 0) + 1
        else:
            accepted_records.append(record)

    deduped_records: list[SourceRecord] = []
    seen_raw_ids: set[str] = set()
    seen_cluster_keys: set[str] = set()
    for record in accepted_records:
        raw_id = _hash_id("raw", f"{record.source}:{record.source_item_id}", 18)
        cluster_key = _cluster_key(record)
        if raw_id in seen_raw_ids:
            rejected.append({"source": record.source, "id": record.source_item_id, "reason": "duplicate_in_batch"})
            rejected_by_source[record.source] = rejected_by_source.get(record.source, 0) + 1
            continue
        if cluster_key in seen_cluster_keys:
            rejected.append({"source": record.source, "id": record.source_item_id, "reason": "duplicate_cluster_in_batch"})
            rejected_by_source[record.source] = rejected_by_source.get(record.source, 0) + 1
            continue
        seen_raw_ids.add(raw_id)
        seen_cluster_keys.add(cluster_key)
        deduped_records.append(record)
    accepted_records = deduped_records

    raw_ids = [_hash_id("raw", f"{r.source}:{r.source_item_id}", 18) for r in accepted_records]
    clean_ids = [_hash_id("clean", raw_id, 18) for raw_id in raw_ids]
    signal_ids = [_hash_id("live", raw_id, 20) for raw_id in raw_ids]
    opportunity_ids = [_hash_id("op-live", clean_id, 18) for clean_id in clean_ids]
    cluster_keys = [_cluster_key(r) for r in accepted_records]

    existing_raw = await _existing_ids(db, RawItem, raw_ids)
    existing_clean = await _existing_ids(db, CleanItem, clean_ids)
    existing_signal = await _existing_ids(db, Signal, signal_ids)
    existing_opportunity = await _existing_ids(db, Opportunity, opportunity_ids)
    existing_cluster_clean = await _existing_clean_by_cluster(db, cluster_keys)

    new_raw = 0
    new_clean = 0
    new_signals = 0
    new_opportunities = 0
    merged_signals = 0
    merged_opportunities = 0

    for record, raw_id, clean_id, signal_id, opportunity_id, cluster_key in zip(
        accepted_records, raw_ids, clean_ids, signal_ids, opportunity_ids, cluster_keys
    ):
        canonical_url = _canonical_url(record.url)
        normalized_title = _normalized_title(record.title)
        localized = TRANSLATION_AGENT.localize(record)
        translation_meta = TRANSLATION_AGENT.metadata(record, localized)
        if raw_id not in existing_raw:
            db.add(
                RawItem(
                    id=raw_id,
                    source=record.source,
                    source_item_id=record.source_item_id,
                    title=record.title[:300],
                    url=canonical_url or record.url,
                    content=_normalize_text(record.content),
                    payload={
                        **record.payload,
                        **translation_meta,
                        "canonical_url": canonical_url,
                        "normalized_title": normalized_title,
                        "cluster_key": cluster_key,
                    },
                    published_at=record.published_at,
                    fetched_at=_utcnow(),
                )
            )
            new_raw += 1
        else:
            raw = await db.get(RawItem, raw_id)
            if raw is not None:
                raw.fetched_at = _utcnow()
                raw.payload = {
                    **(raw.payload or {}),
                    **record.payload,
                    **translation_meta,
                    "canonical_url": canonical_url,
                    "normalized_title": normalized_title,
                    "cluster_key": cluster_key,
                }

        clean_text = _normalize_text(f"{localized.title}. {localized.content}")
        keywords = _extract_keywords(clean_text)
        topic, circle, region, gap = _classify(record, keywords)
        existing_cluster = existing_cluster_clean.get(cluster_key)
        target_clean_id = existing_cluster.id if existing_cluster is not None else clean_id
        target_raw_item_id = existing_cluster.raw_item_id if existing_cluster is not None else raw_id
        clean = CleanItem(
            id=target_clean_id,
            raw_item_id=target_raw_item_id,
            source=record.source,
            title=_normalize_text(localized.title)[:300],
            summary=clean_text[:600],
            url=canonical_url or record.url,
            topic=topic,
            circle=circle,
            region=region,
            keywords=keywords,
            entities=_extract_entities(record.title),
            metrics={
                **record.metrics,
                **translation_meta,
                "gap": gap,
                "canonical_url": canonical_url,
                "normalized_title": normalized_title,
                "cluster_key": cluster_key,
                "evidence_count": 1,
            },
            published_at=record.published_at,
            created_at=_utcnow(),
        )
        existing_clean_row = existing_cluster
        if existing_clean_row is None:
            existing_clean_row = await db.get(CleanItem, clean_id)

        if existing_clean_row is not None:
            existing_metrics = existing_clean_row.metrics or {}
            existing_sources = set(existing_metrics.get("evidence_sources") or [existing_clean_row.source])
            existing_sources.add(record.source)
            existing_clean_row.metrics = {
                **existing_metrics,
                "gap": existing_metrics.get("gap") or gap,
                "canonical_url": existing_metrics.get("canonical_url") or canonical_url,
                "normalized_title": existing_metrics.get("normalized_title") or normalized_title,
                "cluster_key": cluster_key,
                "evidence_count": max(int(existing_metrics.get("evidence_count", 1) or 1), len(existing_sources)),
                "evidence_sources": sorted(existing_sources),
                "language": existing_metrics.get("language") or translation_meta["language"],
                "translated_to": "zh",
                "translation_provider": existing_metrics.get("translation_provider") or translation_meta["translation_provider"],
                "translation_agent": TRANSLATION_AGENT.name,
                "title_original": existing_metrics.get("title_original") or record.title,
                "content_original": existing_metrics.get("content_original") or record.content,
                "title_zh": existing_metrics.get("title_zh") or localized.title,
                "content_zh": existing_metrics.get("content_zh") or localized.content,
            }
            existing_clean_row.source = existing_clean_row.source or record.source
            existing_clean_row.url = existing_clean_row.url or canonical_url or record.url
            existing_clean_row.published_at = existing_clean_row.published_at or record.published_at
            if len(localized.title or "") > len(existing_clean_row.title or ""):
                existing_clean_row.title = _normalize_text(localized.title)[:300]
            if len(clean_text) > len(existing_clean_row.summary or ""):
                existing_clean_row.summary = clean_text[:600]
            clean = existing_clean_row
        elif clean_id not in existing_clean:
            db.add(clean)
            new_clean += 1

        score, level, crowding_score = _score_record(record)
        target_signal_id = _hash_id("live", clean.raw_item_id, 20)
        signal = await db.get(Signal, target_signal_id)
        if signal is not None:
            if _merge_signal(signal, clean, record, score):
                merged_signals += 1
        elif signal_id not in existing_signal:
            db.add(_signal_for(clean, score, level, crowding_score))
            new_signals += 1

        target_opportunity_id = _hash_id("op-live", clean.id, 18)
        opportunity = await db.get(Opportunity, target_opportunity_id)
        if opportunity is not None:
            _merge_opportunity(opportunity, score, len(signal.sources or []) if signal is not None else 1)
            if await db.get(OpportunityAnalysis, opportunity.id) is None:
                db.add(_opportunity_analysis_for(clean, opportunity))
            merged_opportunities += 1
        elif score >= OPPORTUNITY_MIN_SCORE and opportunity_id not in existing_opportunity:
            opportunity = _opportunity_for(clean, score, level, crowding_score)
            db.add(opportunity)
            if await db.get(OpportunityAnalysis, opportunity.id) is None:
                db.add(_opportunity_analysis_for(clean, opportunity))
            new_opportunities += 1

    rejected_raw_ids = [_hash_id("raw", f"{r.source}:{r.source_item_id}", 18) for r in rejected_records]
    rejected_clean_ids = [_hash_id("clean", raw_id, 18) for raw_id in rejected_raw_ids]
    rejected_signal_ids = [_hash_id("live", raw_id, 20) for raw_id in rejected_raw_ids]
    rejected_opportunity_ids = [_hash_id("op-live", clean_id, 18) for clean_id in rejected_clean_ids]
    if rejected_signal_ids:
        rejected_signals = (
            await db.execute(select(Signal).where(Signal.id.in_(rejected_signal_ids)))
        ).scalars().all()
        for signal in rejected_signals:
            signal.level = "C"
            signal.score = min(signal.score, 45)
            signal.convergence = "已过滤噪声"
            signal.risk = "高风险"
            signal.time_label = "已复核"
    if rejected_opportunity_ids:
        rejected_opportunities = (
            await db.execute(select(Opportunity).where(Opportunity.id.in_(rejected_opportunity_ids)))
        ).scalars().all()
        for opportunity in rejected_opportunities:
            opportunity.level = "C"
            opportunity.score = min(opportunity.score, 40)
            opportunity.status = "filtered"
            opportunity.risk_level = "high"
            opportunity.bear_case = "质量过滤器判定该条更像噪声、梗图、薄讨论或低价值内容，不建议作为机会执行。"

    return {
        "accepted": len(accepted_records),
        "rejected": len(rejected),
        "rejected_items": rejected[:20],
        "new_raw": new_raw,
        "new_clean": new_clean,
        "new_signals": new_signals,
        "new_opportunities": new_opportunities,
        "merged_signals": merged_signals,
        "merged_opportunities": merged_opportunities,
        "rejected_by_source": rejected_by_source,
    }


async def _ensure_source_catalog(db: AsyncSession) -> None:
    for source, status, notes in [*GATED_SOURCE_CATALOG, *get_connector_catalog()]:
        row = (
            await db.execute(select(SourceStatus).where(SourceStatus.source == source))
        ).scalar_one_or_none()
        if row is None:
            row = SourceStatus(
                id=_hash_id("src-catalog", source, 10),
                source=source,
                status=status,
                freshness="fresh" if status == "healthy" else "not_configured",
                signal_count_24h=0,
                notes=notes,
                last_checked=_utcnow(),
            )
            db.add(row)
        elif row.signal_count_24h == 0 or status != "healthy":
            row.status = status
            row.freshness = "fresh" if status == "healthy" else "not_configured"
            row.notes = notes
            row.last_checked = _utcnow()


async def run_real_pipeline(
    db: AsyncSession,
    limit_per_source: int | None = None,
    target_sources: list[str] | None = None,
) -> dict[str, Any]:
    limit_per_source = limit_per_source or settings.pipeline_limit_per_source
    await _ensure_source_catalog(db)
    source_fetchers: dict[str, Callable[[int], Awaitable[list[SourceRecord]]]] = {
        "HackerNews": _fetch_hacker_news,
        "HackerNews: Startup": lambda limit: _fetch_hacker_news_query(
            "HackerNews: Startup", "startup automation ecommerce", limit
        ),
        "arXiv": _fetch_arxiv,
        "Apple App Store": _fetch_apple_app_store,
    }
    for source, query_text in GITHUB_QUERY_SOURCES:
        source_fetchers[source] = lambda limit, source=source, query_text=query_text: _fetch_github_query(
            source, query_text, limit
        )
    for source, subreddit in REDDIT_SUBREDDIT_SOURCES:
        source_fetchers[source] = lambda limit, source=source, subreddit=subreddit: _fetch_reddit_subreddit(
            source, subreddit, limit
        )
    for source, url, category in RSS_SOURCES:
        source_fetchers[source] = lambda limit, source=source, url=url, category=category: _fetch_rss_feed(
            source, url, category, limit
        )
    for connector in get_source_connectors():
        source_fetchers[connector.name] = connector.fetch

    requested_sources = [source for source in dict.fromkeys(target_sources or []) if source]
    if requested_sources:
        requested_set = set(requested_sources)
        source_fetchers = {
            source: fetcher
            for source, fetcher in source_fetchers.items()
            if source in requested_set
        }

    summary: dict[str, Any] = {
        "sources": {},
        "target_sources": requested_sources,
        "missing_target_sources": [
            source for source in requested_sources if source not in source_fetchers
        ],
        "raw_inserted": 0,
        "clean_inserted": 0,
        "signals_inserted": 0,
        "opportunities_inserted": 0,
        "signals_merged": 0,
        "opportunities_merged": 0,
        "opportunities_total": 0,
        "rejected": 0,
        "errors": [],
        "configured_catalog_sources": len(GATED_SOURCE_CATALOG) + len(get_connector_catalog()),
        "historical_duplicates_filtered": 0,
        "opportunities_scorecards_backfilled": 0,
        "chinese_localization_backfilled": 0,
        "opportunity_evidence_ids_backfilled": 0,
        "translation_agent": TRANSLATION_AGENT.name,
        "translation_provider": "local_glossary_free",
    }
    for source in summary["missing_target_sources"]:
        await _upsert_source_status(
            db,
            source,
            "warning",
            0,
            "该数据源未接入实时采集器，不能通过刷新变成可用",
        )
        summary["sources"][source] = {
            "fetched": 0,
            "accepted": 0,
            "rejected": 0,
            "error": "source is not wired to a live collector",
        }
        summary["errors"].append(
            {"source": source, "error": "source is not wired to a live collector"}
        )

    async def fetch_source(source: str, fetcher):
        try:
            records = await asyncio.wait_for(fetcher(limit_per_source), timeout=SOURCE_TASK_TIMEOUT)
            return source, records, None
        except TimeoutError as exc:
            return source, [], RuntimeError(f"source fetch timed out after {SOURCE_TASK_TIMEOUT}s")
        except Exception as exc:
            return source, [], exc

    fetch_results = await asyncio.gather(
        *(fetch_source(source, fetcher) for source, fetcher in source_fetchers.items())
    )

    all_records: list[SourceRecord] = []
    records_by_source: dict[str, list[SourceRecord]] = {}
    for source, records, exc in fetch_results:
        records_by_source[source] = records
        all_records.extend(records)
        if exc is not None:
            await _upsert_source_status(db, source, "warning", 0, f"真实采集失败: {exc}")
            summary["sources"][source] = {"fetched": 0, "accepted": 0, "rejected": 0, "error": str(exc)}
            summary["errors"].append({"source": source, "error": str(exc)})

    batch = await _store_records_batch(db, all_records)
    if requested_sources:
        historical_duplicates_filtered = 0
        opportunities_scorecards_backfilled = 0
        chinese_localization_backfilled = 0
        opportunity_evidence_ids_backfilled = 0
    else:
        historical_duplicates_filtered = await _filter_historical_duplicates(db)
        opportunities_scorecards_backfilled = await _backfill_opportunity_scorecards(db)
        chinese_localization_backfilled = await _backfill_chinese_localization(db)
        opportunity_evidence_ids_backfilled = await _backfill_opportunity_evidence_ids(db)

    rejected_by_source: dict[str, int] = batch["rejected_by_source"]

    accepted_by_source: dict[str, int] = {}
    for record in all_records:
        if _quality_rejection_reason(record) is None:
            accepted_by_source[record.source] = accepted_by_source.get(record.source, 0) + 1

    for source, records in records_by_source.items():
        if source in summary["sources"] and "error" in summary["sources"][source]:
            continue
        accepted = accepted_by_source.get(source, 0)
        rejected_count = rejected_by_source.get(source, 0)
        await _upsert_source_status(
            db,
            source,
            "healthy",
            accepted,
            f"真实采集成功，拉取 {len(records)} 条，保留 {accepted} 条，过滤 {rejected_count} 条",
        )
        summary["sources"][source] = {
            "fetched": len(records),
            "accepted": accepted,
            "rejected": rejected_count,
        }

    summary["raw_inserted"] = batch["new_raw"]
    summary["clean_inserted"] = batch["new_clean"]
    summary["signals_inserted"] = batch["new_signals"]
    summary["opportunities_inserted"] = batch["new_opportunities"]
    summary["signals_merged"] = batch["merged_signals"]
    summary["opportunities_merged"] = batch["merged_opportunities"]
    summary["rejected"] = batch["rejected"]
    summary["rejected_items"] = batch["rejected_items"]
    summary["historical_duplicates_filtered"] = historical_duplicates_filtered
    summary["opportunities_scorecards_backfilled"] = opportunities_scorecards_backfilled
    summary["chinese_localization_backfilled"] = chinese_localization_backfilled
    summary["opportunity_evidence_ids_backfilled"] = opportunity_evidence_ids_backfilled

    summary["opportunities_total"] = await db.scalar(
        select(func.count(Opportunity.id)).where(Opportunity.id.like("op-live-%"))
    )
    return summary
