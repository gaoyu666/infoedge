from __future__ import annotations

import asyncio
import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

from app.services.sources.base import SourceRecord, fetch_text


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


async def _fetch_json_any(url: str) -> Any:
    text = await asyncio.to_thread(fetch_text, url, accept="application/json,*/*")
    return json.loads(text)


def _severity_score(value: str | None) -> int:
    return {
        "extreme": 5,
        "severe": 4,
        "moderate": 3,
        "minor": 2,
        "unknown": 1,
    }.get(str(value or "").lower(), 1)


@dataclass
class NasaEonetConnector:
    name: str = "NASA EONET: Natural Events"
    source_type: str = "public_json"
    status: str = "healthy"
    notes: str = "WorldMonitor-inspired NASA EONET natural-events feed for storms, volcanoes, floods, wildfire, and environmental disruption signals."

    async def fetch(self, limit: int) -> list[SourceRecord]:
        url = f"https://eonet.gsfc.nasa.gov/api/v3/events?{urlencode({'status': 'open', 'limit': max(10, limit)})}"
        return self.records_from_payload(await _fetch_json_any(url), limit)

    def records_from_payload(self, payload: dict[str, Any], limit: int) -> list[SourceRecord]:
        records: list[SourceRecord] = []
        for rank, item in enumerate((payload.get("events") or [])[:limit], start=1):
            title = str(item.get("title") or "")
            if not title:
                continue
            categories = item.get("categories") or []
            category = categories[0].get("title") if categories and isinstance(categories[0], dict) else "natural_event"
            geometries = item.get("geometry") or []
            published = None
            if geometries and isinstance(geometries[0], dict):
                published = _parse_datetime(geometries[0].get("date"))
            records.append(
                SourceRecord(
                    source=self.name,
                    source_item_id=str(item.get("id") or title),
                    title=title[:300],
                    url=item.get("link"),
                    content=str(item.get("description") or category or ""),
                    published_at=published,
                    metrics={"rank": rank, "event": 1},
                    payload={"category": category, "raw": item},
                )
            )
        return records


@dataclass
class NoaaWeatherAlertsConnector:
    name: str = "NOAA/NWS: Severe Weather Alerts"
    source_type: str = "public_geojson"
    status: str = "healthy"
    notes: str = "Shadowbroker/WorldMonitor-inspired active NOAA/NWS alert feed for weather and logistics disruption signals."

    async def fetch(self, limit: int) -> list[SourceRecord]:
        return self.records_from_payload(await _fetch_json_any("https://api.weather.gov/alerts/active"), limit)

    def records_from_payload(self, payload: dict[str, Any], limit: int) -> list[SourceRecord]:
        records: list[SourceRecord] = []
        for rank, feature in enumerate((payload.get("features") or [])[:limit], start=1):
            props = feature.get("properties") or {}
            event = props.get("event") or props.get("headline") or ""
            if not event:
                continue
            severity = props.get("severity")
            records.append(
                SourceRecord(
                    source=self.name,
                    source_item_id=str(feature.get("id") or props.get("id") or event),
                    title=str(props.get("headline") or event)[:300],
                    url=props.get("uri") or props.get("@id"),
                    content=" ".join(str(part or "") for part in [props.get("areaDesc"), props.get("description")] if part)[:1800],
                    published_at=_parse_datetime(props.get("sent") or props.get("effective")),
                    metrics={"rank": rank, "severity_score": _severity_score(severity)},
                    payload={"category": "weather_alert", "event": event, "severity": severity, "raw": props},
                )
            )
        return records


@dataclass
class NoaaSwpcConnector:
    name: str = "NOAA SWPC: Space Weather"
    source_type: str = "public_json"
    status: str = "healthy"
    notes: str = "Shadowbroker-inspired NOAA SWPC space-weather feed for solar storm, satellite, navigation, and grid-risk signals."

    async def fetch(self, limit: int) -> list[SourceRecord]:
        payload = await _fetch_json_any("https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json")
        return self.records_from_payload(payload, limit)

    def records_from_payload(self, payload: list[Any], limit: int) -> list[SourceRecord]:
        rows = payload[1:] if payload and isinstance(payload[0], list) else payload
        records: list[SourceRecord] = []
        for rank, row in enumerate(rows[-limit:][::-1], start=1):
            if isinstance(row, dict):
                time_tag = str(row.get("time_tag") or row.get("time") or "")
                kp_value = row.get("Kp") or row.get("kp") or 0
            elif isinstance(row, list) and len(row) >= 2:
                time_tag = str(row[0])
                kp_value = row[1]
            else:
                continue
            try:
                kp = float(kp_value)
            except (TypeError, ValueError):
                kp = 0.0
            records.append(
                SourceRecord(
                    source=self.name,
                    source_item_id=f"kp:{time_tag}",
                    title=f"Planetary K-index {kp:g}",
                    url="https://www.swpc.noaa.gov/products/planetary-k-index",
                    content=f"NOAA SWPC planetary K-index reading at {time_tag}.",
                    published_at=_parse_datetime(time_tag),
                    metrics={"rank": rank, "kp_index": kp},
                    payload={"category": "space_weather", "time_tag": time_tag},
                )
            )
        return records


@dataclass
class CelesTrakSatelliteConnector:
    name: str = "CelesTrak: Active Satellites"
    source_type: str = "public_csv"
    status: str = "healthy"
    notes: str = "Shadowbroker/WorldMonitor-inspired CelesTrak SATCAT feed for active satellite and space-infrastructure awareness."

    async def fetch(self, limit: int) -> list[SourceRecord]:
        text = await asyncio.to_thread(
            fetch_text,
            "https://celestrak.org/pub/satcat.csv",
            accept="text/csv,text/plain,*/*",
        )
        return self.records_from_satcat_csv(text, limit)

    def records_from_payload(self, payload: list[dict[str, Any]], limit: int) -> list[SourceRecord]:
        records: list[SourceRecord] = []
        for rank, item in enumerate(payload[:limit], start=1):
            name = str(item.get("OBJECT_NAME") or item.get("OBJECT_ID") or "")
            norad_id = item.get("NORAD_CAT_ID") or item.get("OBJECT_ID") or name
            if not name or not norad_id:
                continue
            records.append(
                SourceRecord(
                    source=self.name,
                    source_item_id=str(norad_id),
                    title=name[:300],
                    url=f"https://celestrak.org/satcat/table-satcat.php?CATNR={norad_id}",
                    content=f"Active satellite catalog entry. Launch date: {item.get('LAUNCH_DATE') or 'unknown'}.",
                    published_at=None,
                    metrics={"rank": rank, "satellite": 1},
                    payload={"category": "satellite", "raw": item},
                )
            )
        return records

    def records_from_satcat_csv(self, text: str, limit: int) -> list[SourceRecord]:
        rows = csv.DictReader(text.splitlines())
        active_payloads: list[dict[str, Any]] = []
        for row in rows:
            if row.get("DECAY_DATE"):
                continue
            if row.get("OBJECT_TYPE") not in {"PAY", "R/B"}:
                continue
            active_payloads.append(row)
            if len(active_payloads) >= max(limit * 4, limit):
                break
        return self.records_from_payload(active_payloads, limit)


def get_public_intel_connectors() -> list[Any]:
    return [
        NasaEonetConnector(),
        NoaaWeatherAlertsConnector(),
        NoaaSwpcConnector(),
        CelesTrakSatelliteConnector(),
    ]
