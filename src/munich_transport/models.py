"""Domain models returned by the public client API."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime


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
    """Compact config-flow option for a station line/direction group."""

    id: str
    schedule_kind: str
    line_label: str
    direction_key: str | None
    directions: tuple[str, ...]
    raw_directions: tuple[str, ...]
    schedule_codes: tuple[str, ...]

    @classmethod
    def from_id(cls, option_id: str) -> StationDirectionOption:
        """Rebuild an option from its stable id when the catalog is unavailable.

        The result can match departures but has no direction names. The id's
        last part is read as the direction key, which is what catalog options
        with a live direction use.
        """

        parts = option_id.split(":", maxsplit=2)
        if len(parts) != 3:
            raise ValueError(f"Not a direction option id: {option_id!r}")

        schedule_kind, line_label, direction_key = parts
        return cls(
            id=option_id,
            schedule_kind=schedule_kind,
            line_label=line_label,
            direction_key=direction_key or None,
            directions=(),
            raw_directions=(),
            schedule_codes=(),
        )

    @property
    def normal_terminus(self) -> str | None:
        """Return the regular terminus, skipping temporary "A / B" variants."""

        for direction in self.directions:
            if "/" not in direction:
                return direction
        return self.directions[0] if self.directions else None

    def matches(self, departure: Departure) -> bool:
        """Return whether a live departure runs on this line and direction.

        Without a direction key every departure of the line matches, since
        catalog direction names and live destinations are spelled differently.
        """

        if departure.line.label != self.line_label:
            return False
        if self.direction_key is None:
            return True
        return departure.direction_key == self.direction_key


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
            not self.station_global_ids
            or station_global_id in self.station_global_ids
        )
