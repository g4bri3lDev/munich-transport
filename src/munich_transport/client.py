"""Public async client API."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime
from typing import Literal

from .directions import DirectionDataset, load_direction_dataset
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
    normalize_line_label,
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
from .schedules import (
    build_departure_direction_options,
    build_line_direction_option,
    build_station_direction_options,
    group_station_schedules,
)
from .transport import AiohttpTransport, Transport
from .types import (
    DEFAULT_DEPARTURE_TRANSPORT_TYPES,
    DEFAULT_TRANSPORT_TYPES,
    DIRECTION_SAMPLE_OFFSETS_MINUTES,
)

RouteType = Literal["LEAST_TIME"]
ChangeSpeed = Literal["SLOW", "NORMAL", "FAST"]

_MAX_CONCURRENT_SAMPLES = 8


class MunichTransportClient:
    """High-level client for MVG transport data."""

    def __init__(
        self,
        transport: Transport | None = None,
        *,
        direction_dataset: DirectionDataset | None = None,
    ) -> None:
        """Create a client.

        `direction_dataset` replaces the bundled line directions, which are
        loaded on first use otherwise.
        """

        self._transport = transport or AiohttpTransport()
        self._direction_dataset = direction_dataset

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
        return await self.direction_options_for_station(await self.station(global_id))

    async def direction_options_for_station(
        self,
        station: Station,
    ) -> list[StationDirectionOption]:
        """Return selectable directions without looking the station up again.

        Uses the schedule catalog when the station has an abbreviation. The
        catalog only lists MVG's own lines, and not every direction of them,
        so the bundled timetable adds the lines and directions it misses, such
        as the S-Bahn, or a line sharing another line's poster where they run
        together. Added directions of a catalog line take its transport type,
        which the catalog distinguishes for night lines. Lines in neither get
        options from live departures sampled across a day, and lines without a
        sampled departure get one option for all their directions.

        Replacement services are left out: their departures carry the label of
        the line they replace, so that line's options match them, but their
        direction keys are not always the line's, so they do not shape options.
        """

        catalog_options = (
            await self.station_direction_options_by_abbreviation(station.abbreviation)
            if station.abbreviation is not None
            else []
        )
        catalog_keys: dict[str, set[str | None]] = {}
        catalog_kinds: dict[str, str] = {}
        for option in catalog_options:
            label = normalize_line_label(option.line_label)
            catalog_keys.setdefault(label, set()).add(option.direction_key)
            catalog_kinds.setdefault(label, option.schedule_kind)
        timetable_options = [
            _with_schedule_kind(
                option, catalog_kinds.get(normalize_line_label(option.line_label))
            )
            for option in (await self._directions()).options(station.global_id)
            if (keys := catalog_keys.get(normalize_line_label(option.line_label)))
            is None
            # Catalog options without a direction key match every direction.
            or (None not in keys and option.direction_key not in keys)
        ]
        known = catalog_keys.keys() | {
            normalize_line_label(option.line_label) for option in timetable_options
        }
        missing_lines = {
            normalize_line_label(line.label): line
            for line in await self.lines(station.global_id)
            if not line.replacement_service
            and normalize_line_label(line.label) not in known
        }
        if (catalog_options or timetable_options) and not missing_lines:
            return [*catalog_options, *timetable_options]

        # Sampling each transport type on its own keeps frequent ones from
        # filling the capped responses and hiding rare lines.
        transport_type_groups: list[tuple[str, ...]] = [
            (transport_type,)
            for transport_type in dict.fromkeys(
                line.transport_type for line in missing_lines.values()
            )
        ] or [DEFAULT_DEPARTURE_TRANSPORT_TYPES]
        departures = await self._sample_departures(
            station.global_id, transport_type_groups
        )
        departure_options = build_departure_direction_options(
            departure
            for departure in departures
            if not departure.line.replacement_service
            and normalize_line_label(departure.line.label) not in known
        )
        sampled = {
            normalize_line_label(option.line_label) for option in departure_options
        }
        return [
            *catalog_options,
            *timetable_options,
            *departure_options,
            *(
                build_line_direction_option(line)
                for label, line in missing_lines.items()
                if label not in sampled
            ),
        ]

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
        offset_minutes: int = 0,
    ) -> list[Departure]:
        params = {
            "globalId": global_id,
            "limit": str(limit),
            "transportTypes": ",".join(transport_types),
        }
        if offset_minutes:
            params["offsetInMinutes"] = str(offset_minutes)
        payload = await self._transport.get_json(
            "/api/bgw-pt/v3/departures",
            params=params,
        )
        return parse_departures(payload)

    async def _sample_departures(
        self,
        global_id: str,
        transport_type_groups: list[tuple[str, ...]],
    ) -> list[Departure]:
        limit = asyncio.Semaphore(_MAX_CONCURRENT_SAMPLES)

        async def sample(
            transport_types: tuple[str, ...], offset: int
        ) -> list[Departure]:
            async with limit:
                return await self.departures(
                    global_id,
                    transport_types=transport_types,
                    offset_minutes=offset,
                )

        samples = await asyncio.gather(
            *(
                sample(transport_types, offset)
                for transport_types in transport_type_groups
                for offset in DIRECTION_SAMPLE_OFFSETS_MINUTES
            )
        )
        return [departure for departures in samples for departure in departures]

    async def _directions(self) -> DirectionDataset:
        if self._direction_dataset is None:
            self._direction_dataset = await asyncio.to_thread(load_direction_dataset)
        return self._direction_dataset

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


def _with_schedule_kind(
    option: StationDirectionOption, schedule_kind: str | None
) -> StationDirectionOption:
    if schedule_kind is None or schedule_kind == option.schedule_kind:
        return option
    return replace(
        option,
        id=schedule_kind + option.id.removeprefix(option.schedule_kind),
        schedule_kind=schedule_kind,
    )


def _format_routing_time(value: datetime | None) -> str:
    moment = value or datetime.now(tz=UTC)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return (
        moment.astimezone(UTC)
        .isoformat(timespec="milliseconds")
        .replace(
            "+00:00",
            "Z",
        )
    )
