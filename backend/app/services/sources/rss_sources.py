from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from typing import Any
from urllib.parse import quote
from xml.etree import ElementTree

from app.services.sources.base import SourceRecord, fetch_text


TECH_RADAR_RSS_FEEDS = [
    ("TechRadar: TechCrunch", "https://techcrunch.com/feed/", "technology_news", "Global-Tech-Rader source: broad technology and startup news."),
    ("TechRadar: MIT Technology Review", "https://www.technologyreview.com/feed/", "research", "Global-Tech-Rader source: research and applied technology coverage."),
    ("TechRadar: The Verge", "https://www.theverge.com/rss/index.xml", "devices", "Global-Tech-Rader source: consumer tech and platform shifts."),
    ("TechRadar: Wired", "https://www.wired.com/feed/rss", "technology_news", "Global-Tech-Rader source: technology, security, science, and culture."),
    ("TechRadar: OpenAI Blog", "https://openai.com/blog/rss.xml", "ai_models", "Global-Tech-Rader source: OpenAI product and research announcements."),
    ("TechRadar: Google DeepMind", "https://deepmind.google/blog/rss.xml", "ai_models", "Global-Tech-Rader source: DeepMind research and model updates."),
    ("TechRadar: Google AI Blog", "https://blog.google/technology/ai/rss/", "ai_models", "Global-Tech-Rader source: Google AI product and research updates."),
    ("TechRadar: arXiv CS AI RSS", "https://export.arxiv.org/rss/cs.AI", "research", "Global-Tech-Rader source: AI research feed."),
    ("TechRadar: MIT News AI", "https://news.mit.edu/rss/topic/artificial-intelligence2", "research", "Global-Tech-Rader source: MIT AI news and research."),
    ("TechRadar: GitHub Blog", "https://github.blog/feed/", "open_source", "Global-Tech-Rader source: developer ecosystem and GitHub platform updates."),
    ("TechRadar: Hacker News RSS", "https://hnrss.org/frontpage", "open_source", "Global-Tech-Rader source: developer-frontpage RSS."),
    ("TechRadar: QbitAI", "https://www.qbitai.com/feed", "china_ai", "Global-Tech-Rader source: Chinese AI industry coverage."),
    ("TechRadar: Jiqizhixin", "https://www.jiqizhixin.com/rss", "china_ai", "Global-Tech-Rader source: Chinese AI research and industry coverage."),
    ("TechRadar: Solidot", "https://www.solidot.org/index.rss", "open_source", "Global-Tech-Rader source: Chinese open-source and tech news."),
    ("TechRadar: OSChina", "https://www.oschina.net/news/rss", "open_source", "Global-Tech-Rader source: Chinese developer ecosystem news."),
    ("TechRadar: ifanr", "https://www.ifanr.com/feed", "devices", "Global-Tech-Rader source: consumer tech and product news."),
    ("TechRadar: SSPAI", "https://sspai.com/feed", "devices", "Global-Tech-Rader source: apps, productivity, and consumer tech."),
    ("TechRadar: Huxiu", "https://www.huxiu.com/rss/0.xml", "china_business", "Global-Tech-Rader source: Chinese business and tech analysis."),
    ("TechRadar: ITHome", "https://www.ithome.com/rss/", "devices", "Global-Tech-Rader source: Chinese hardware and tech news."),
    ("TechRadar: AWS Blog", "https://aws.amazon.com/blogs/aws/feed/", "cloud", "Global-Tech-Rader source: cloud platform launches and infrastructure signals."),
    ("TechRadar: Google Cloud", "https://cloudblog.withgoogle.com/rss/", "cloud", "Global-Tech-Rader source: cloud platform launches and enterprise AI signals."),
    ("TechRadar: Reuters Business", "https://www.reuters.com/business/feed/", "policy_finance", "Global-Tech-Rader source: business, policy, and macro technology context."),
    ("TechRadar: Canary Media", "https://www.canarymedia.com/feed", "new_energy", "Global-Tech-Rader source: clean energy and climate-tech coverage."),
    ("TechRadar: Electrek", "https://electrek.co/feed/", "new_energy", "Global-Tech-Rader source: EV, battery, and clean-energy products."),
    ("TechRadar: KrebsOnSecurity", "https://krebsonsecurity.com/feed/", "cybersecurity", "Global-Tech-Rader source: cybersecurity incidents and research."),
    ("TechRadar: STAT News", "https://www.statnews.com/feed/", "healthcare", "Global-Tech-Rader source: healthcare, biotech, and medical innovation."),
    ("TrendRadar: Yahoo Finance RSS", "https://finance.yahoo.com/news/rssindex", "finance_news", "TrendRadar source: Yahoo Finance market news RSS."),
]
DISABLED_RSS_FEEDS = {
    "TechRadar: Huxiu": "Current public RSS endpoint times out from this environment; configure a proxy or relay before live collection.",
    "TechRadar: Jiqizhixin": "Current public URL returns an HTML data-service page instead of RSS; configure a valid feed/relay before live collection.",
    "TechRadar: Reuters Business": "Reuters public RSS endpoint returns HTTP 401 from this environment; configure licensed/API access before live collection.",
}


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


@dataclass
class GenericRssConnector:
    name: str
    url: str
    category: str
    notes: str
    source_type: str = "public_rss"
    status: str = "healthy"
    enabled: bool = True

    async def fetch(self, limit: int) -> list[SourceRecord]:
        text = await asyncio.to_thread(fetch_text, self.url, accept="application/rss+xml,application/atom+xml,application/xml,*/*")
        return self.records_from_text(text, limit)

    def records_from_text(self, text: str, limit: int) -> list[SourceRecord]:
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
            published = _parse_datetime(_child_text(item, "pubDate", "published", "updated", "dc:date"))
            source_id = _child_text(item, "guid", "id") or link or f"{title}:{rank}"
            records.append(
                SourceRecord(
                    source=self.name,
                    source_item_id=str(source_id),
                    title=title[:300],
                    url=link or None,
                    content=_child_text(item, "description", "summary", "content", "encoded"),
                    published_at=published,
                    metrics={"rank": rank, "feed_item": 1},
                    payload={"category": self.category, "feed_url": self.url},
                )
            )
        return records


def get_tech_radar_connectors() -> list[GenericRssConnector]:
    connectors: list[GenericRssConnector] = []
    for name, url, category, notes in TECH_RADAR_RSS_FEEDS:
        disabled_reason = DISABLED_RSS_FEEDS.get(name)
        connectors.append(
            GenericRssConnector(
                name=name,
                url=url,
                category=category,
                notes=f"{notes} {disabled_reason}" if disabled_reason else notes,
                status="needs_config" if disabled_reason else "healthy",
                enabled=disabled_reason is None,
            )
        )
    return connectors
