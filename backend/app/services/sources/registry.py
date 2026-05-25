from __future__ import annotations

from app.services.sources.base import SourceConnector
from app.services.sources.connectors import get_connector_instances


def get_source_connectors() -> list[SourceConnector]:
    return [connector for connector in get_connector_instances() if getattr(connector, "enabled", True)]


def get_connector_catalog() -> list[tuple[str, str, str]]:
    return [(connector.name, connector.status, connector.notes) for connector in get_connector_instances()]
