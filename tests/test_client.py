from __future__ import annotations

from datetime import UTC, datetime

from munich_transport.client import MunichTransportClient
from munich_transport.types import JsonValue


class FakeTransport:
    def __init__(self, payload: JsonValue) -> None:
        self.payload = payload
        self.calls: list[tuple[str, dict[str, str] | None]] = []

    async def get_json(
        self,
        path: str,
        *,
        params: dict[str, str] | None = None,
    ) -> JsonValue:
        self.calls.append((path, params))
        return self.payload


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
