"""Shared typing aliases and defaults."""

from __future__ import annotations

from typing import Final

type JsonObject = dict[str, object]
type JsonArray = list[object]
type JsonValue = JsonObject | JsonArray | str | int | float | bool | None

DEFAULT_TRANSPORT_TYPES: Final[tuple[str, ...]] = (
    "SCHIFF",
    "UBAHN",
    "TRAM",
    "SBAHN",
    "BUS",
    "REGIONAL_BUS",
    "BAHN",
)

DEFAULT_DEPARTURE_TRANSPORT_TYPES: Final[tuple[str, ...]] = (
    "UBAHN",
    "TRAM",
    "SBAHN",
    "BUS",
    "REGIONAL_BUS",
    "BAHN",
)
