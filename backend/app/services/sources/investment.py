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


SEC_FEEDS = [
    (
        "SEC EDGAR: Form D",
        "D",
        "private_offering",
        "美国私募融资/Reg D 披露，适合捕捉未上市公司融资和基金募资信号。",
    ),
    (
        "SEC EDGAR: 13F",
        "13F-HR",
        "institutional_holdings",
        "机构持仓披露，适合观察基金/资管机构季度持仓变化。",
    ),
    (
        "SEC EDGAR: S-1 IPO",
        "S-1",
        "ipo_pipeline",
        "IPO 注册文件，适合捕捉拟上市公司和新资本市场窗口。",
    ),
]
CN_INVESTMENT_FEEDS = [
    (
        "36Kr: Newsflash",
        "https://36kr.com/feed-newsflash",
        "china_vc_news",
        "36氪快讯 RSS，适合捕捉中文创投、融资、IPO 和产业资本动态。",
    ),
    (
        "36Kr: News",
        "https://www.36kr.com/feed",
        "china_business_news",
        "36氪新闻 RSS，适合补充中文新经济、创投和产业趋势。",
    ),
]


def _normalize_text(value: str | None) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    return unescape(re.sub(r"\s+", " ", text).strip())[:1800]


def _child_text(node: ElementTree.Element, *local_names: str) -> str:
    wanted = set(local_names)
    for child in list(node):
        local_name = child.tag.rsplit("}", 1)[-1]
        if local_name in wanted:
            return _normalize_text(child.text or "")
    return ""


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        try:
            parsed = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


@dataclass
class SecEdgarFeedConnector:
    name: str
    form_type: str
    category: str
    notes: str
    source_type: str = "public_atom"
    status: str = "healthy"

    async def fetch(self, limit: int) -> list[SourceRecord]:
        return await asyncio.to_thread(self._fetch_sync, limit)

    def _fetch_sync(self, limit: int) -> list[SourceRecord]:
        url = (
            "https://www.sec.gov/cgi-bin/browse-edgar"
            f"?action=getcurrent&type={quote(self.form_type)}&count={max(10, limit)}&output=atom"
        )
        text = fetch_text(url, accept="application/atom+xml,application/xml,*/*")
        root = ElementTree.fromstring(text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        records: list[SourceRecord] = []
        for rank, entry in enumerate(root.findall("atom:entry", ns)[:limit], start=1):
            title = _child_text(entry, "title")
            if not title:
                continue
            link_node = entry.find("atom:link", ns)
            link = link_node.attrib.get("href") if link_node is not None else None
            content = _child_text(entry, "summary", "content")
            accession = _child_text(entry, "accession-nunber", "accession-number", "id") or link or title
            company = title.split(" - ", 1)[0].strip()
            records.append(
                SourceRecord(
                    source=self.name,
                    source_item_id=accession,
                    title=title[:300],
                    url=link,
                    content=content,
                    published_at=_parse_datetime(_child_text(entry, "updated", "published")),
                    metrics={"rank": rank, "filings": 1},
                    payload={
                        "category": self.category,
                        "form_type": self.form_type,
                        "company": company,
                        "feed_url": url,
                    },
                )
            )
        return records


@dataclass
class InvestmentRssConnector:
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
            description = _child_text(item, "description", "summary", "content", "encoded")
            source_id = _child_text(item, "guid", "id") or link or title
            records.append(
                SourceRecord(
                    source=self.name,
                    source_item_id=source_id,
                    title=title[:300],
                    url=link or None,
                    content=description,
                    published_at=_parse_datetime(_child_text(item, "pubDate", "published", "updated")),
                    metrics={"rank": rank, "news": 1},
                    payload={
                        "category": self.category,
                        "feed_url": self.url,
                    },
                )
            )
        return records


def get_investment_connectors() -> list[Any]:
    return [
        *[
            SecEdgarFeedConnector(name=name, form_type=form_type, category=category, notes=notes)
            for name, form_type, category, notes in SEC_FEEDS
        ],
        *[
            InvestmentRssConnector(name=name, url=url, category=category, notes=notes)
            for name, url, category, notes in CN_INVESTMENT_FEEDS
        ],
    ]
