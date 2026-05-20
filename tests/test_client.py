from __future__ import annotations

from datetime import UTC, datetime

from munich_transport.client import MunichTransportClient
from munich_transport.types import JsonValue


class FakeTransport:
    def __init__(self, payload: JsonValue | tuple[JsonValue, ...]) -> None:
        self.payloads = list(payload) if isinstance(payload, tuple) else [payload]
        self.calls: list[tuple[str, dict[str, str] | None]] = []

    async def get_json(
        self,
        path: str,
        *,
        params: dict[str, str] | None = None,
    ) -> JsonValue:
        self.calls.append((path, params))
        return self.payloads.pop(0)


async def test_search_locations_uses_official_locations_endpoint() -> None:
    transport = FakeTransport([])
    client = MunichTransportClient(transport)

    assert await client.search_locations("Marienplatz") == []
    assert transport.calls == [
        ("/api/bgw-pt/v3/locations", {"query": "Marienplatz"}),
    ]


async def test_departures_uses_global_id_limit_and_products() -> None:
    transport = FakeTransport([])
    client = MunichTransportClient(transport)

    departures = await client.departures(
        "de:09162:2",
        limit=5,
        transport_types=("UBAHN",),
    )

    assert departures == []
    assert transport.calls == [
        (
            "/api/bgw-pt/v3/departures",
            {
                "globalId": "de:09162:2",
                "limit": "5",
                "transportTypes": "UBAHN",
            },
        ),
    ]


async def test_station_schedules_resolves_abbreviation_before_aushang() -> None:
    transport = FakeTransport(
        (
            {
                "id": "de:09162:2",
                "name": "Marienplatz",
                "place": "München",
                "divaId": 2,
                "abbreviation": "MP",
                "tariffZones": "m",
                "products": ["SBAHN", "UBAHN", "BUS"],
                "latitude": 48.137245,
                "longitude": 11.575421,
            },
            [
                {
                    "uri": "https://www.mvg.de/aushangfahrplan/U3_I_MP_52.pdf",
                    "scheduleKind": "SUBWAY",
                    "scheduleName": "U3",
                    "direction": (
                        "Sendlinger Tor / Fürstenried West "
                        "(gültig vom 18.05. - 18.09.2026)"
                    ),
                },
            ],
        )
    )
    client = MunichTransportClient(transport)

    schedules = await client.station_schedules("de:09162:2")

    assert schedules[0].line_label == "U3"
    assert schedules[0].direction.startswith("Sendlinger Tor")
    assert transport.calls == [
        ("/.rest/zdm/stations/de:09162:2", None),
        ("/.rest/aushang/stations", {"id": "MP"}),
    ]


async def test_station_schedules_by_abbreviation_uses_aushang_directly() -> None:
    transport = FakeTransport([])
    client = MunichTransportClient(transport)

    assert await client.station_schedules_by_abbreviation("BP") == []
    assert transport.calls == [
        ("/.rest/aushang/stations", {"id": "BP"}),
    ]


async def test_station_direction_groups_returns_selectable_groups() -> None:
    transport = FakeTransport(
        (
            {
                "id": "de:09162:410",
                "name": "Bonner Platz",
                "place": "München",
                "divaId": 410,
                "abbreviation": "BP",
                "tariffZones": "m",
                "products": ["UBAHN"],
                "latitude": 48.166878,
                "longitude": 11.579666,
            },
            [
                {
                    "uri": "https://www.mvg.de/aushangfahrplan/U3_H_BP_52.pdf",
                    "scheduleKind": "SUBWAY",
                    "scheduleName": "U3",
                    "direction": "Fürstenried West, gültig ab 14.12.2025",
                },
                {
                    "uri": "https://www.mvg.de/aushangfahrplan/U3_I_BP_52.pdf",
                    "scheduleKind": "SUBWAY",
                    "scheduleName": "U3",
                    "direction": (
                        "Sendlinger Tor / Fürstenried West "
                        "(gültig vom 18.05. - 18.09.2026)"
                    ),
                },
            ],
        )
    )
    client = MunichTransportClient(transport)

    groups = await client.station_direction_groups("de:09162:410")

    assert len(groups) == 1
    assert groups[0].line_label == "U3"
    assert groups[0].direction_key == "H"
    assert groups[0].schedule_codes == ("H", "I")


async def test_station_direction_options_returns_config_options() -> None:
    transport = FakeTransport(
        (
            {
                "id": "de:09162:410",
                "name": "Bonner Platz",
                "place": "München",
                "divaId": 410,
                "abbreviation": "BP",
                "tariffZones": "m",
                "products": ["UBAHN"],
                "latitude": 48.166878,
                "longitude": 11.579666,
            },
            [
                {
                    "uri": "https://www.mvg.de/aushangfahrplan/U3_R_BP_51.pdf",
                    "scheduleKind": "SUBWAY",
                    "scheduleName": "U3",
                    "direction": "Moosach Bf, gültig ab 14.12.2025",
                },
                {
                    "uri": "https://www.mvg.de/aushangfahrplan/U3_S_BP_51.pdf",
                    "scheduleKind": "SUBWAY",
                    "scheduleName": "U3",
                    "direction": (
                        "Implerstraße / Moosach Bf "
                        "(gültig vom 18.05. - 18.09.2026)"
                    ),
                },
            ],
        )
    )
    client = MunichTransportClient(transport)

    options = await client.station_direction_options("de:09162:410")

    assert len(options) == 1
    assert options[0].id == "SUBWAY:U3:R"
    assert options[0].directions == ("Moosach Bf", "Implerstraße / Moosach Bf")


async def test_direction_options_by_abbreviation_avoids_station_lookup() -> None:
    transport = FakeTransport(
        [
            {
                "uri": "https://www.mvg.de/aushangfahrplan/U3_R_BP_51.pdf",
                "scheduleKind": "SUBWAY",
                "scheduleName": "U3",
                "direction": "Moosach Bf, gültig ab 14.12.2025",
            },
        ]
    )
    client = MunichTransportClient(transport)

    options = await client.station_direction_options_by_abbreviation("BP")

    assert options[0].id == "SUBWAY:U3:R"
    assert transport.calls == [
        ("/.rest/aushang/stations", {"id": "BP"}),
    ]


async def test_routes_formats_datetime_as_utc_browser_parameter() -> None:
    transport = FakeTransport([])
    client = MunichTransportClient(transport)

    await client.routes(
        "de:09162:2",
        "de:09162:6",
        routing_time=datetime(2026, 5, 20, 11, 19, 37, 296000, tzinfo=UTC),
    )

    assert transport.calls[0][0] == "/api/bgw-pt/v3/routes"
    assert transport.calls[0][1] == {
        "originStationGlobalId": "de:09162:2",
        "destinationStationGlobalId": "de:09162:6",
        "routingDateTime": "2026-05-20T11:19:37.296Z",
        "routingDateTimeIsArrival": "false",
        "transportTypes": "SCHIFF,UBAHN,TRAM,SBAHN,BUS,REGIONAL_BUS,BAHN",
        "changeSpeed": "NORMAL",
        "routeType": "LEAST_TIME",
    }
