"""Domain models returned by the public client API."""

from __future__ import annotations

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
