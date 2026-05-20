"""Pure conversion from MVG JSON responses to domain models."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from typing import cast
from urllib.parse import urlsplit

from .exceptions import ParseError
from .models import (
    Departure,
    Disruption,
    Line,
    Location,
    Notice,
    Route,
    RouteLeg,
    RouteStop,
    Station,
    StationSchedule,
)


def parse_locations(payload: object) -> list[Location]:
    items = _as_list(payload, "locations response")
    return [_parse_location(_as_mapping(item, "location")) for item in items]


def parse_station(payload: object) -> Station:
    data = _as_mapping(payload, "station response")
    return Station(
        global_id=_required_str(data, "id"),
        name=_required_str(data, "name"),
        place=_optional_str(data, "place"),
        latitude=_required_float(data, "latitude"),
        longitude=_required_float(data, "longitude"),
        diva_id=_optional_int(data, "divaId"),
        abbreviation=_optional_str(data, "abbreviation"),
        tariff_zones=_optional_str(data, "tariffZones"),
        transport_types=_str_tuple(data.get("products")),
    )


def parse_nearby_stations(payload: object) -> list[Station]:
    items = _as_list(payload, "nearby stations response")
    return [
        _parse_station_search_result(_as_mapping(item, "nearby station"))
        for item in items
    ]


def parse_station_schedules(payload: object) -> list[StationSchedule]:
    items = _as_list(payload, "station schedules response")
    return [
        _parse_station_schedule(_as_mapping(item, "station schedule"))
        for item in items
    ]


def parse_departures(payload: object) -> list[Departure]:
    items = _as_list(payload, "departures response")
    return [_parse_departure(_as_mapping(item, "departure")) for item in items]


def parse_lines(payload: object) -> list[Line]:
    items = _as_list(payload, "lines response")
    return [_parse_line(_as_mapping(item, "line")) for item in items]


def parse_routes(payload: object) -> list[Route]:
    items = _as_list(payload, "routes response")
    return [_parse_route(_as_mapping(item, "route")) for item in items]


def parse_disruptions(payload: object) -> list[Disruption]:
    items = _as_list(payload, "messages response")
    return [_parse_disruption(_as_mapping(item, "message")) for item in items]


def _parse_location(data: Mapping[str, object]) -> Location:
    return Location(
        name=_required_str(data, "name"),
        place=_optional_str(data, "place"),
        latitude=_required_float(data, "latitude"),
        longitude=_required_float(data, "longitude"),
        kind=_required_str(data, "type"),
        global_id=_optional_str(data, "globalId"),
        diva_id=_optional_int(data, "divaId"),
        transport_types=_str_tuple(data.get("transportTypes")),
        tariff_zones=_optional_str(data, "tariffZones"),
        aliases=_optional_str(data, "aliases"),
        has_zoom_data=_optional_bool(data, "hasZoomData"),
        distance_meters=_optional_int(data, "distanceInMeters"),
    )


def _parse_station_search_result(data: Mapping[str, object]) -> Station:
    return Station(
        global_id=_required_str(data, "globalId"),
        name=_required_str(data, "name"),
        place=_optional_str(data, "place"),
        latitude=_required_float(data, "latitude"),
        longitude=_required_float(data, "longitude"),
        diva_id=_optional_int(data, "divaId"),
        tariff_zones=_optional_str(data, "tariffZones"),
        transport_types=_str_tuple(data.get("transportTypes")),
        has_zoom_data=_optional_bool(data, "hasZoomData"),
        distance_meters=_optional_int(data, "distanceInMeters"),
    )


def _parse_station_schedule(data: Mapping[str, object]) -> StationSchedule:
    pdf_url = _required_str(data, "uri")
    schedule_code, station_abbreviation, stop_number = _schedule_pdf_metadata(pdf_url)
    return StationSchedule(
        schedule_kind=_required_str(data, "scheduleKind"),
        line_label=_required_str(data, "scheduleName"),
        direction=_required_str(data, "direction"),
        pdf_url=pdf_url,
        schedule_code=schedule_code,
        station_abbreviation=station_abbreviation,
        stop_number=stop_number,
        direction_key=_schedule_direction_key(schedule_code),
    )


def _parse_departure(data: Mapping[str, object]) -> Departure:
    line_id = _optional_str(data, "lineId")
    return Departure(
        planned_departure=_unix_ms(data, "plannedDepartureTime"),
        realtime_departure=_unix_ms(data, "realtimeDepartureTime"),
        line=_parse_departure_line(data),
        destination=_required_str(data, "destination"),
        realtime=_required_bool(data, "realtime"),
        cancelled=_required_bool(data, "cancelled"),
        station_global_id=_optional_str(data, "stationGlobalId"),
        stop_point_global_id=_optional_str(data, "stopPointGlobalId"),
        line_id=line_id,
        direction_key=_line_id_direction_key(line_id),
        platform=_optional_int(data, "platform"),
        platform_changed=_optional_bool(data, "platformChanged"),
        delay_minutes=_optional_int(data, "delayInMinutes"),
        occupancy=_optional_str(data, "occupancy"),
        messages=_str_tuple(data.get("messages")),
        notices=_parse_notices(data.get("infos")),
    )


def _schedule_pdf_metadata(
    pdf_url: str,
) -> tuple[str | None, str | None, str | None]:
    filename = urlsplit(pdf_url).path.rsplit("/", 1)[-1]
    if not filename.endswith(".pdf"):
        return None, None, None

    parts = filename[:-4].split("_")
    if len(parts) < 4:
        return None, None, None
    return parts[1], parts[2], parts[3]


def _schedule_direction_key(schedule_code: str | None) -> str | None:
    if schedule_code is None:
        return None
    return {"I": "H", "S": "R"}.get(schedule_code, schedule_code)


def _line_id_direction_key(line_id: str | None) -> str | None:
    if line_id is None:
        return None
    parts = line_id.split(":")
    if len(parts) < 4:
        return None
    direction_key = parts[3].strip()
    return direction_key or None


def _parse_departure_line(data: Mapping[str, object]) -> Line:
    return Line(
        label=_required_str(data, "label"),
        transport_type=_required_str(data, "transportType"),
        network=_optional_str(data, "network"),
        diva_id=_optional_str(data, "divaId"),
        train_type=_optional_str(data, "trainType"),
        destination=_optional_str(data, "destination"),
        replacement_service=_optional_bool(data, "sev") or False,
    )


def _parse_line(data: Mapping[str, object]) -> Line:
    return Line(
        label=_required_str(data, "label"),
        transport_type=_required_str(data, "transportType"),
        network=_optional_str(data, "network"),
        diva_id=_optional_str(data, "divaId"),
        train_type=_optional_str(data, "trainType"),
        destination=_optional_str(data, "destination"),
        replacement_service=_optional_bool(data, "sev") or False,
    )


def _parse_route(data: Mapping[str, object]) -> Route:
    parts = _as_list(data.get("parts"), "route parts")
    ticketing = _optional_mapping(data.get("ticketingInformation"))
    zones = ticketing.get("zones") if ticketing else None
    return Route(
        unique_id=_required_int(data, "uniqueId"),
        legs=tuple(_parse_route_leg(_as_mapping(item, "route part")) for item in parts),
        distance_meters=_optional_float(data, "distance"),
        ticket_zones=_int_tuple(zones),
    )


def _parse_route_leg(data: Mapping[str, object]) -> RouteLeg:
    return RouteLeg(
        origin=_parse_route_stop(_required_mapping(data, "from")),
        destination=_parse_route_stop(_required_mapping(data, "to")),
        line=_parse_line(_required_mapping(data, "line")),
        distance_meters=_optional_float(data, "distance"),
        realtime=_optional_bool(data, "realTime") or False,
        no_change_required=_optional_bool(data, "noChangeRequired") or False,
        intermediate_stops=tuple(
            _parse_route_stop(_as_mapping(item, "intermediate stop"))
            for item in _as_list(data.get("intermediateStops"), "intermediate stops")
        ),
        messages=_str_tuple(data.get("messages")),
        notices=_parse_notices(data.get("infos")),
        path_polyline=_optional_str(data, "pathPolyline"),
    )


def _parse_route_stop(data: Mapping[str, object]) -> RouteStop:
    return RouteStop(
        name=_required_str(data, "name"),
        place=_optional_str(data, "place"),
        latitude=_required_float(data, "latitude"),
        longitude=_required_float(data, "longitude"),
        station_global_id=_optional_str(data, "stationGlobalId"),
        station_diva_id=_optional_int(data, "stationDivaId"),
        planned_departure=_optional_datetime(data, "plannedDeparture"),
        departure_delay_minutes=_optional_int(data, "departureDelayInMinutes"),
        arrival_delay_minutes=_optional_int(data, "arrivalDelayInMinutes"),
        platform=_optional_int(data, "platform"),
        platform_changed=_optional_bool(data, "platformChanged"),
        transport_types=_str_tuple(data.get("transportTypes")),
    )


def _parse_disruption(data: Mapping[str, object]) -> Disruption:
    return Disruption(
        title=_required_str(data, "title"),
        description_html=_required_str(data, "description"),
        kind=_required_str(data, "type"),
        provider=_optional_str(data, "provider"),
        valid_from=_optional_unix_ms(data, "validFrom"),
        valid_to=_optional_unix_ms(data, "validTo"),
        lines=tuple(
            _parse_line(_as_mapping(item, "message line"))
            for item in _as_list(data.get("lines"), "message lines")
        ),
        station_global_ids=_str_tuple(data.get("stationGlobalIds")),
    )


def _parse_notices(value: object) -> tuple[Notice, ...]:
    return tuple(
        Notice(
            message=_required_str(item, "message"),
            kind=_optional_str(item, "type"),
            network=_optional_str(item, "network"),
        )
        for item in (
            _as_mapping(raw, "notice")
            for raw in _as_list(value, "notices")
        )
    )


def _optional_datetime(data: Mapping[str, object], key: str) -> datetime | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ParseError(f"Expected {key!r} to be an ISO datetime string")
    return datetime.fromisoformat(value)


def _optional_unix_ms(data: Mapping[str, object], key: str) -> datetime | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, int):
        raise ParseError(f"Expected {key!r} to be a Unix millisecond integer")
    return datetime.fromtimestamp(value / 1000, tz=UTC)


def _unix_ms(data: Mapping[str, object], key: str) -> datetime:
    value = data.get(key)
    if not isinstance(value, int):
        raise ParseError(f"Expected {key!r} to be a Unix millisecond integer")
    return datetime.fromtimestamp(value / 1000, tz=UTC)


def _required_mapping(data: Mapping[str, object], key: str) -> Mapping[str, object]:
    return _as_mapping(data.get(key), key)


def _optional_mapping(value: object) -> Mapping[str, object] | None:
    if value is None:
        return None
    return _as_mapping(value, "object")


def _as_mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ParseError(f"Expected {label} to be an object")
    return cast(Mapping[str, object], value)


def _as_list(value: object, label: str) -> list[object]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ParseError(f"Expected {label} to be a list")
    return value


def _required_str(data: Mapping[str, object], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str):
        raise ParseError(f"Expected {key!r} to be a string")
    return value


def _optional_str(data: Mapping[str, object], key: str) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ParseError(f"Expected {key!r} to be a string")
    return value


def _required_int(data: Mapping[str, object], key: str) -> int:
    value = data.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ParseError(f"Expected {key!r} to be an integer")
    return value


def _optional_int(data: Mapping[str, object], key: str) -> int | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        raise ParseError(f"Expected {key!r} to be an integer")
    return value


def _required_float(data: Mapping[str, object], key: str) -> float:
    value = data.get(key)
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise ParseError(f"Expected {key!r} to be a number")
    return float(value)


def _optional_float(data: Mapping[str, object], key: str) -> float | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise ParseError(f"Expected {key!r} to be a number")
    return float(value)


def _required_bool(data: Mapping[str, object], key: str) -> bool:
    value = data.get(key)
    if not isinstance(value, bool):
        raise ParseError(f"Expected {key!r} to be a boolean")
    return value


def _optional_bool(data: Mapping[str, object], key: str) -> bool | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, bool):
        raise ParseError(f"Expected {key!r} to be a boolean")
    return value


def _str_tuple(value: object) -> tuple[str, ...]:
    return tuple(_items_of_type(value, str, "string list"))


def _int_tuple(value: object) -> tuple[int, ...]:
    return tuple(_items_of_type(value, int, "integer list"))


def _items_of_type[T](
    value: object,
    expected_type: type[T],
    label: str,
) -> Iterable[T]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ParseError(f"Expected {label}")
    if not all(isinstance(item, expected_type) for item in value):
        raise ParseError(f"Expected {label}")
    return cast(Iterable[T], value)
