"""Source-connector registry. READ-ONLY connectors only in v1 (no apply path)."""

from __future__ import annotations

from typing import Any

from aeroapply.connectors.base import SourceConnector
from aeroapply.connectors.greenhouse import GreenhouseConnector

_FACTORIES: dict[str, type[Any]] = {"greenhouse": GreenhouseConnector}


def get_connector(key: str, **kwargs: Any) -> SourceConnector:
    try:
        factory = _FACTORIES[key]
    except KeyError:
        raise ValueError(f"unknown source connector: {key!r}") from None
    connector: SourceConnector = factory(**kwargs)
    return connector


def available() -> list[str]:
    return sorted(_FACTORIES)


__all__ = ["get_connector", "available"]
