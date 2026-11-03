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

# Live departures reach only about half an hour ahead, so lines missing from
# the schedule catalog are discovered by sampling departures across a day.
DIRECTION_SAMPLE_OFFSETS_MINUTES: Final[tuple[int, ...]] = tuple(range(0, 24 * 60, 180))
