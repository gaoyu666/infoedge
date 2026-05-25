from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from urllib.error import HTTPError
from urllib.request import Request, urlopen


USER_AGENT = "InfoEdge/0.1 source-engine"
SOURCE_FETCH_TIMEOUT = 18


@dataclass
class SourceRecord:
    source: str
    source_item_id: str
    title: str
    url: str | None
    content: str
    published_at: datetime | None
    metrics: dict[str, Any]
    payload: dict[str, Any]


class SourceConnector(Protocol):
    name: str
    source_type: str
    status: str
    notes: str

    async def fetch(self, limit: int) -> list[SourceRecord]:
        ...


def fetch_text(url: str, *, accept: str = "application/json, text/html, */*") -> str:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": accept,
        "Accept-Language": "en-US,en;q=0.9",
    }
    request = Request(url, headers=headers)
    with urlopen(request, timeout=SOURCE_FETCH_TIMEOUT) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def request_json(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = SOURCE_FETCH_TIMEOUT,
) -> dict[str, Any]:
    body = json.dumps(payload or {}).encode("utf-8") if payload is not None else None
    request_headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }
    if body is not None:
        request_headers["Content-Type"] = "application/json"
    if headers:
        request_headers.update(headers)
    request = Request(url, data=body, headers=request_headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return json.loads(response.read().decode(charset, errors="replace"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc


async def fetch_json(url: str) -> dict[str, Any]:
    text = await asyncio.to_thread(fetch_text, url, accept="application/json, */*")
    return json.loads(text)
