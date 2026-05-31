from __future__ import annotations

import json
import unittest

from app.services.real_pipeline import GATED_SOURCE_CATALOG
from app.services.sources.registry import get_connector_catalog, get_source_connectors


class SourceExpansionTests(unittest.TestCase):
    def test_new_public_connectors_are_registered_for_live_collection(self) -> None:
        names = {connector.name for connector in get_source_connectors()}

        self.assertIn("TechRadar: OpenAI Blog", names)
        self.assertIn("TechRadar: MIT Technology Review", names)
        self.assertIn("NASA EONET: Natural Events", names)
        self.assertIn("NOAA/NWS: Severe Weather Alerts", names)
        self.assertIn("NOAA SWPC: Space Weather", names)
        self.assertIn("CelesTrak: Active Satellites", names)

    def test_blocked_hotlists_are_cataloged_but_not_live_without_relay(self) -> None:
        catalog_names = {name for name, _status, _notes in get_connector_catalog()}
        live_names = {connector.name for connector in get_source_connectors()}

        self.assertIn("TrendRadar: Baidu Hot Search", catalog_names)
        self.assertNotIn("TrendRadar: Baidu Hot Search", live_names)

    def test_gated_sources_are_cataloged_but_not_live_without_credentials(self) -> None:
        catalog_names = {name for name, _status, _notes in GATED_SOURCE_CATALOG}
        live_names = {connector.name for connector in get_source_connectors()}

        for source in [
            "AkShare",
            "Tushare",
            "YFinance",
            "Longbridge OpenAPI",
            "OpenSky Network",
            "AISStream",
            "Shodan",
            "NASA FIRMS",
            "Wingbits",
        ]:
            self.assertIn(source, catalog_names)
            self.assertNotIn(source, live_names)

    def test_trendradar_hotlist_payload_is_normalized(self) -> None:
        from app.services.sources.hotlists import TrendRadarHotlistConnector

        connector = TrendRadarHotlistConnector(
            name="TrendRadar: Baidu Hot Search",
            platform_id="baidu",
            platform_name="Baidu Hot Search",
        )
        records = connector.records_from_payload(
            {
                "status": "success",
                "items": [
                    {
                        "title": "AI agents are trending",
                        "url": "https://example.com/story",
                        "mobileUrl": "https://m.example.com/story",
                        "hot": "12345",
                    }
                ],
            },
            limit=5,
        )

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].source, "TrendRadar: Baidu Hot Search")
        self.assertEqual(records[0].source_item_id, "baidu:AI agents are trending")
        self.assertEqual(records[0].url, "https://example.com/story")
        self.assertEqual(records[0].metrics["rank"], 1)
        self.assertEqual(records[0].metrics["hotness"], 12345)

    def test_trendradar_hotlist_payload_handles_edges(self) -> None:
        from app.services.sources.hotlists import TrendRadarHotlistConnector

        connector = TrendRadarHotlistConnector(
            name="TrendRadar: Zhihu Hot",
            platform_id="zhihu",
            platform_name="Zhihu",
        )
        records = connector.records_from_payload(
            {
                "status": "cache",
                "items": [
                    "not-a-dict",
                    {"title": "", "hot": "999"},
                    {"title": "<b>Agent tools</b> adoption", "mobileUrl": "https://m.example.com/a", "hot": "1.2k"},
                    {"title": "Ignored by limit", "hot": "2m"},
                ],
            },
            limit=3,
        )

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].title, "Agent tools adoption")
        self.assertEqual(records[0].url, "https://m.example.com/a")
        self.assertEqual(records[0].metrics["hotness"], 1200)

        with self.assertRaisesRegex(RuntimeError, "status=error"):
            connector.records_from_payload({"status": "error", "items": []}, limit=5)

    def test_world_public_json_connectors_normalize_payloads(self) -> None:
        from app.services.sources.public_intel import (
            CelesTrakSatelliteConnector,
            NasaEonetConnector,
            NoaaSwpcConnector,
            NoaaWeatherAlertsConnector,
        )

        eonet = NasaEonetConnector()
        eonet_records = eonet.records_from_payload(
            {
                "events": [
                    {
                        "id": "EONET_1",
                        "title": "Wildfire in sample region",
                        "description": "Detected thermal event",
                        "categories": [{"title": "Wildfires"}],
                        "geometry": [{"date": "2026-05-23T10:00:00Z"}],
                    }
                ]
            },
            limit=5,
        )
        self.assertEqual(eonet_records[0].payload["category"], "Wildfires")

        weather = NoaaWeatherAlertsConnector()
        weather_records = weather.records_from_payload(
            {
                "features": [
                    {
                        "id": "alert-1",
                        "properties": {
                            "event": "Severe Thunderstorm Warning",
                            "headline": "Storm warning headline",
                            "areaDesc": "Sample County",
                            "severity": "Severe",
                            "sent": "2026-05-23T10:00:00Z",
                            "uri": "https://api.weather.gov/alerts/alert-1",
                        },
                    }
                ]
            },
            limit=5,
        )
        self.assertEqual(weather_records[0].metrics["severity_score"], 4)

        satellites = CelesTrakSatelliteConnector()
        satellite_records = satellites.records_from_payload(
            json.loads(
                '[{"OBJECT_NAME":"ISS (ZARYA)","NORAD_CAT_ID":25544,'
                '"LAUNCH_DATE":"1998-11-20","DECAY_DATE":null}]'
            ),
            limit=5,
        )
        self.assertEqual(satellite_records[0].source_item_id, "25544")

        swpc = NoaaSwpcConnector()
        swpc_records = swpc.records_from_payload(
            [{"time_tag": "2026-05-24T09:00:00", "Kp": 1.33, "station_count": 8}],
            limit=1,
        )
        self.assertEqual(swpc_records[0].metrics["kp_index"], 1.33)

    def test_world_public_json_connectors_handle_malformed_payloads(self) -> None:
        from app.services.sources.public_intel import (
            CelesTrakSatelliteConnector,
            NasaEonetConnector,
            NoaaSwpcConnector,
            NoaaWeatherAlertsConnector,
        )

        eonet = NasaEonetConnector()
        eonet_records = eonet.records_from_payload(
            {
                "events": [
                    {"id": "skip-empty-title", "title": ""},
                    {"id": "fallback-category", "title": "Flood watch", "geometry": [{"date": "not-a-date"}]},
                ]
            },
            limit=5,
        )
        self.assertEqual(len(eonet_records), 1)
        self.assertEqual(eonet_records[0].payload["category"], "natural_event")
        self.assertIsNone(eonet_records[0].published_at)

        weather = NoaaWeatherAlertsConnector()
        weather_records = weather.records_from_payload(
            {
                "features": [
                    {"id": "skip-empty-event", "properties": {}},
                    {"id": "unknown-severity", "properties": {"event": "Advisory", "severity": "Mystery"}},
                ]
            },
            limit=5,
        )
        self.assertEqual(len(weather_records), 1)
        self.assertEqual(weather_records[0].metrics["severity_score"], 1)

        swpc = NoaaSwpcConnector()
        swpc_records = swpc.records_from_payload(
            [["time_tag", "Kp"], ["2026-05-24T09:00:00", "bad-number"], ["2026-05-24T12:00:00", "4.67"]],
            limit=2,
        )
        self.assertEqual([record.metrics["kp_index"] for record in swpc_records], [4.67, 0.0])

        satellites = CelesTrakSatelliteConnector()
        satellite_records = satellites.records_from_satcat_csv(
            "\n".join(
                [
                    "OBJECT_NAME,NORAD_CAT_ID,OBJECT_TYPE,LAUNCH_DATE,DECAY_DATE",
                    "DEBRIS,1,DEB,2020-01-01,",
                    "DECAYED PAYLOAD,2,PAY,2020-01-01,2021-01-01",
                    "ACTIVE PAYLOAD,3,PAY,2020-01-01,",
                    "ACTIVE ROCKET BODY,4,R/B,2020-01-01,",
                ]
            ),
            limit=5,
        )
        self.assertEqual([record.source_item_id for record in satellite_records], ["3", "4"])


if __name__ == "__main__":
    unittest.main()
