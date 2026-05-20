"""Public async client API."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from .exceptions import ParseError
from .models import (
    Departure,
    Disruption,
    Line,
    Location,
    Route,
    Station,
    StationDirection,
    StationDirectionOption,
    StationSchedule,
)
from .parser import (
    parse_departures,
    parse_disruptions,
    parse_lines,
    parse_locations,
    parse_nearby_stations,
    parse_routes,
    parse_station,
    parse_station_schedules,
)
from .schedules import build_station_direction_options, group_station_schedules
from .transport import AiohttpTransport, Transport
from .types import DEFAULT_DEPARTURE_TRANSPORT_TYPES, DEFAULT_TRANSPORT_TYPES

RouteType = Literal["LEAST_TIME"]
ChangeSpeed = Literal["SLOW", "NORMAL", "FAST"]


class MunichTransportClient:
    """High-level client for MVG transport data."""

    def __init__(self, transport: Transport | None = None) -> None:
        self._transport = transport or AiohttpTransport()

    async def search_locations(self, query: str) -> list[Location]:
        payload = await self._transport.get_json(
            "/api/bgw-pt/v3/locations",
            params={"query": query},
        )
        return parse_locations(payload)

    async def station(self, global_id: str) -> Station:
        payload = await self._transport.get_json(f"/.rest/zdm/stations/{global_id}")
        return parse_station(payload)

    async def station_schedules(self, global_id: str) -> list[StationSchedule]:
        station = await self.station(global_id)
        if station.abbreviation is None:
            raise ParseError("Station response did not include an abbreviation")

        return await self.station_schedules_by_abbreviation(station.abbreviation)

    async def station_schedules_by_abbreviation(
        self,
        abbreviation: str,
    ) -> list[StationSchedule]:
        payload = await self._transport.get_json(
            "/.rest/aushang/stations",
            params={"id": abbreviation},
        )
        return parse_station_schedules(payload)

    async def station_direction_groups(self, global_id: str) -> list[StationDirection]:
        schedules = await self.station_schedules(global_id)
        return group_station_schedules(schedules)

    async def station_direction_groups_by_abbreviation(
        self,
        abbreviation: str,
    ) -> list[StationDirection]:
        schedules = await self.station_schedules_by_abbreviation(abbreviation)
        return group_station_schedules(schedules)

    async def station_direction_options(
        self,
        global_id: str,
    ) -> list[StationDirectionOption]:
        schedules = await self.station_schedules(global_id)
        return build_station_direction_options(schedules)

    async def station_direction_options_by_abbreviation(
        self,
        abbreviation: str,
    ) -> list[StationDirectionOption]:
        schedules = await self.station_schedules_by_abbreviation(abbreviation)
        return build_station_direction_options(schedules)

    async def nearby_stations(self, latitude: float, longitude: float) -> list[Station]:
        payload = await self._transport.get_json(
            "/api/bgw-pt/v3/stations/nearby",
            params={
                "latitude": str(latitude),
                "longitude": str(longitude),
            },
        )
        return parse_nearby_stations(payload)

    async def departures(
        self,
        global_id: str,
        *,
        limit: int = 100,
        transport_types: tuple[str, ...] = DEFAULT_DEPARTURE_TRANSPORT_TYPES,
    ) -> list[Departure]:
        payload = await self._transport.get_json(
            "/api/bgw-pt/v3/departures",
            params={
                "globalId": global_id,
                "limit": str(limit),
                "transportTypes": ",".join(transport_types),
            },
        )
        return parse_departures(payload)

    async def lines(self, global_id: str) -> list[Line]:
        payload = await self._transport.get_json(f"/api/bgw-pt/v3/lines/{global_id}")
        return parse_lines(payload)

    async def routes(
        self,
        origin_global_id: str,
        destination_global_id: str,
        *,
        routing_time: datetime | None = None,
        is_arrival_time: bool = False,
        transport_types: tuple[str, ...] = DEFAULT_TRANSPORT_TYPES,
        change_speed: ChangeSpeed = "NORMAL",
        route_type: RouteType = "LEAST_TIME",
    ) -> list[Route]:
        payload = await self._transport.get_json(
            "/api/bgw-pt/v3/routes",
            params={
                "originStationGlobalId": origin_global_id,
                "destinationStationGlobalId": destination_global_id,
                "routingDateTime": _format_routing_time(routing_time),
                "routingDateTimeIsArrival": str(is_arrival_time).lower(),
                "transportTypes": ",".join(transport_types),
                "changeSpeed": change_speed,
                "routeType": route_type,
            },
        )
        return parse_routes(payload)

    async def messages(self) -> list[Disruption]:
        payload = await self._transport.get_json("/api/bgw-pt/v3/messages")
        return parse_disruptions(payload)


def _format_routing_time(value: datetime | None) -> str:
    moment = value or datetime.now(tz=UTC)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC).isoformat(timespec="milliseconds").replace(
        "+00:00",
        "Z",
    )
