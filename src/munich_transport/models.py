"""Domain models returned by the public client API."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime

_NON_WORD_RE = re.compile(r"[^\w\s]")
_STATION_SUFFIX_TOKENS: frozenset[str] = frozenset(
    {"bahnhof", "bf", "bhf", "hbf", "hauptbahnhof"}
)


@dataclass(frozen=True, slots=True)
class Location:
    """A search result from MVG location lookup."""

    name: str
    place: str | None
    latitude: float
    longitude: float
    kind: str
    global_id: str | None = None
    diva_id: int | None = None
    transport_types: tuple[str, ...] = ()
    tariff_zones: str | None = None
    aliases: str | None = None
    has_zoom_data: bool | None = None
    distance_meters: int | None = None


@dataclass(frozen=True, slots=True)
class Station:
    """A public transport station."""

    global_id: str
    name: str
    place: str | None
    latitude: float
    longitude: float
    diva_id: int | None = None
    abbreviation: str | None = None
    tariff_zones: str | None = None
    transport_types: tuple[str, ...] = ()
    has_zoom_data: bool | None = None
    distance_meters: int | None = None


@dataclass(frozen=True, slots=True)
class StationSchedule:
    """A station timetable PDF entry from MVG's aushang endpoint."""

    schedule_kind: str
    line_label: str
    direction: str
    pdf_url: str
    schedule_code: str | None = None
    station_abbreviation: str | None = None
    stop_number: str | None = None
    direction_key: str | None = None


@dataclass(frozen=True, slots=True)
class StationDirection:
    """A selectable line/direction group for a station."""

    schedule_kind: str
    line_label: str
    direction_key: str | None
    directions: tuple[str, ...]
    schedule_codes: tuple[str, ...]
    schedules: tuple[StationSchedule, ...]


@dataclass(frozen=True, slots=True)
class StationDirectionOption:
    """Compact config-flow option for a station line/direction group.

    Where a rail line's branches part, each branch is an option of its own
    that excludes the destinations of the other branches.
    """

    id: str
    schedule_kind: str
    line_label: str
    direction_key: str | None
    directions: tuple[str, ...]
    raw_directions: tuple[str, ...]
    schedule_codes: tuple[str, ...]
    excluded_destinations: tuple[str, ...] = ()

    @classmethod
    def from_id(cls, option_id: str) -> StationDirectionOption:
        """Rebuild an option from its stable id when the catalog is unavailable.

        The result can match departures but has no direction names. The id's
        third part is read as the direction key, which is what catalog options
        with a live direction use. A branch named after it is not known from
        the id, so the result matches every branch.
        """

        parts = option_id.split(":", maxsplit=2)
        if len(parts) != 3:
            raise ValueError(f"Not a direction option id: {option_id!r}")

        schedule_kind, line_label, suffix = parts
        direction_key = suffix.split(":", maxsplit=1)[0]
        return cls(
            id=option_id,
            schedule_kind=schedule_kind,
            line_label=line_label,
            direction_key=direction_key or None,
            directions=(),
            raw_directions=(),
            schedule_codes=(),
        )

    def to_dict(self) -> dict[str, str | list[str] | None]:
        """Return a JSON-safe form that `from_dict` restores exactly.

        Unlike the id, it keeps the direction names and a missing direction
        key, so a stored selection works without the catalog or live data.
        """

        return {
            "id": self.id,
            "schedule_kind": self.schedule_kind,
            "line_label": self.line_label,
            "direction_key": self.direction_key,
            "directions": list(self.directions),
            "raw_directions": list(self.raw_directions),
            "schedule_codes": list(self.schedule_codes),
            "excluded_destinations": list(self.excluded_destinations),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> StationDirectionOption:
        """Restore an option stored with `to_dict`."""

        try:
            direction_key = data["direction_key"]
            return cls(
                id=_str(data["id"]),
                schedule_kind=_str(data["schedule_kind"]),
                line_label=_str(data["line_label"]),
                direction_key=None if direction_key is None else _str(direction_key),
                directions=_str_tuple(data["directions"]),
                raw_directions=_str_tuple(data["raw_directions"]),
                schedule_codes=_str_tuple(data["schedule_codes"]),
                excluded_destinations=_str_tuple(data.get("excluded_destinations", [])),
            )
        except (KeyError, TypeError) as error:
            raise ValueError(f"Not a stored direction option: {data!r}") from error

    @property
    def normal_terminus(self) -> str | None:
        """Return the regular terminus, which the option builders list first."""

        return self.directions[0] if self.directions else None

    def matches(self, departure: Departure) -> bool:
        """Return whether a live departure runs on this line and direction.

        Without a direction key every departure of the line matches, since
        catalog direction names and live destinations are spelled differently.
        A branch matches every destination but those of the other branches,
        so trips cut short by construction count for every branch.
        """

        if normalize_line_label(departure.line.label) != normalize_line_label(
            self.line_label
        ):
            return False
        if self.direction_key is not None and (
            departure.direction_key != self.direction_key
        ):
            return False
        return not self.excluded_destinations or not all(
            any(
                direction_names_match(destination, excluded)
                for excluded in self.excluded_destinations
            )
            # Halves of split trains are merged as "Flughafen München / Freising".
            for destination in departure.destination.split(" / ")
        )


@dataclass(frozen=True, slots=True)
class Line:
    """A transit line."""

    label: str
    transport_type: str
    network: str | None = None
    diva_id: str | None = None
    train_type: str | None = None
    destination: str | None = None
    replacement_service: bool = False


@dataclass(frozen=True, slots=True)
class Notice:
    """Short operational notice attached to a result."""

    message: str
    kind: str | None = None
    network: str | None = None


@dataclass(frozen=True, slots=True)
class Departure:
    """A station departure."""

    planned_departure: datetime
    realtime_departure: datetime
    line: Line
    destination: str
    realtime: bool
    cancelled: bool
    station_global_id: str | None = None
    stop_point_global_id: str | None = None
    line_id: str | None = None
    direction_key: str | None = None
    platform: int | None = None
    platform_changed: bool | None = None
    delay_minutes: int | None = None
    occupancy: str | None = None
    messages: tuple[str, ...] = ()
    notices: tuple[Notice, ...] = ()


@dataclass(frozen=True, slots=True)
class RouteStop:
    """A stop in a route leg."""

    name: str
    place: str | None
    latitude: float
    longitude: float
    station_global_id: str | None = None
    station_diva_id: int | None = None
    planned_departure: datetime | None = None
    departure_delay_minutes: int | None = None
    arrival_delay_minutes: int | None = None
    platform: int | None = None
    platform_changed: bool | None = None
    transport_types: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RouteLeg:
    """One leg of a planned route."""

    origin: RouteStop
    destination: RouteStop
    line: Line
    distance_meters: float | None = None
    realtime: bool = False
    no_change_required: bool = False
    intermediate_stops: tuple[RouteStop, ...] = ()
    messages: tuple[str, ...] = ()
    notices: tuple[Notice, ...] = ()
    path_polyline: str | None = None


@dataclass(frozen=True, slots=True)
class Route:
    """A complete journey option."""

    unique_id: int
    legs: tuple[RouteLeg, ...]
    distance_meters: float | None = None
    ticket_zones: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class Disruption:
    """A service message or disruption."""

    title: str
    description_html: str
    kind: str
    provider: str | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    lines: tuple[Line, ...] = ()
    station_global_ids: tuple[str, ...] = ()

    def is_active(self, at: datetime) -> bool:
        """Return whether the message is valid at the given time."""

        if self.valid_from is not None and self.valid_from > at:
            return False
        return self.valid_to is None or self.valid_to >= at

    def affects_station(self, global_id: str, line_labels: Iterable[str]) -> bool:
        """Return whether the message concerns a station served by these lines.

        Messages naming stations only concern those stations. Messages naming
        neither stations nor lines are network-wide.
        """

        if self.station_global_ids:
            return global_id in self.station_global_ids
        if not self.lines:
            return True
        labels = set(line_labels)
        return any(line.label in labels for line in self.lines)

    def affects_line(self, line_label: str, station_global_id: str) -> bool:
        """Return whether the message names this line at this station.

        Network-wide messages without lines do not count, so a line is not
        reported as disrupted by general announcements.
        """

        if not any(line.label == line_label for line in self.lines):
            return False
        return (
            not self.station_global_ids or station_global_id in self.station_global_ids
        )


def normalize_line_label(label: str) -> str:
    """Return a line label without spaces, as MVG spells both "RE 9" and "RE9"."""

    return "".join(label.split())


def direction_names_match(name: str, other: str) -> bool:
    """Return whether two spellings of a direction name the same place.

    Ignores case, punctuation and station suffixes such as "Bf." or "Hbf",
    and accepts one name contained in the other, so "Giesing" matches
    "Giesing Bf." and "Tierpark (Alemannenstr)" matches
    "Tierpark (Alemannenstr.)".
    """

    tokens = _direction_tokens(name)
    other_tokens = _direction_tokens(other)
    if not tokens or not other_tokens:
        return False
    return _contains_token_sequence(tokens, other_tokens) or _contains_token_sequence(
        other_tokens, tokens
    )


def _direction_tokens(value: str) -> tuple[str, ...]:
    normalized = _NON_WORD_RE.sub(" ", value.casefold())
    return tuple(
        token for token in normalized.split() if token not in _STATION_SUFFIX_TOKENS
    )


def _contains_token_sequence(
    tokens: tuple[str, ...],
    search_tokens: tuple[str, ...],
) -> bool:
    length = len(search_tokens)
    return any(
        tokens[index : index + length] == search_tokens
        for index in range(len(tokens) - length + 1)
    )


def _str(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError(f"Expected a string, got {value!r}")
    return value


def _str_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list | tuple):
        raise TypeError(f"Expected a list, got {value!r}")
    return tuple(_str(item) for item in value)
