"""Live smoke test for the official MVG browser endpoints.

This script intentionally lives outside the regular pytest suite because it
depends on the live MVG website.
"""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime

from munich_transport import AiohttpTransport, MunichTransportClient
from munich_transport.models import Location


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origin", default="Marienplatz")
    parser.add_argument("--destination", default="Hauptbahnhof")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=15.0)
    args = parser.parse_args(argv)

    asyncio.run(
        _run(
            origin_query=args.origin,
            destination_query=args.destination,
            departure_limit=args.limit,
            timeout_seconds=args.timeout,
        )
    )
    return 0


async def _run(
    *,
    origin_query: str,
    destination_query: str,
    departure_limit: int,
    timeout_seconds: float,
) -> None:
    async with AiohttpTransport(timeout=timeout_seconds) as transport:
        client = MunichTransportClient(transport)

        origin_locations = await client.search_locations(origin_query)
        destination_locations = await client.search_locations(destination_query)
        origin = _first_station(origin_query, origin_locations)
        destination = _first_station(destination_query, destination_locations)

        station = await client.station(origin.global_id)
        station_schedules = await client.station_schedules(origin.global_id)
        departures = await client.departures(origin.global_id, limit=departure_limit)
        lines = await client.lines(origin.global_id)
        messages = await client.messages()
        routes = await client.routes(
            origin.global_id,
            destination.global_id,
            routing_time=datetime.now(tz=UTC),
        )

    print(
        "locations "
        f"origin={len(origin_locations)} destination={len(destination_locations)}"
    )
    print(
        "station "
        f"id={station.global_id} "
        f"name={station.name!r} "
        f"products={station.transport_types}"
    )
    print(
        "station schedules "
        f"count={len(station_schedules)} "
        f"first={station_schedules[0].line_label!r} "
        f"direction={station_schedules[0].direction!r}"
    )
    print(
        "departures "
        f"count={len(departures)} first={departures[0].line.label!r} "
        f"destination={departures[0].destination!r}"
    )
    print(f"lines count={len(lines)} sample={[line.label for line in lines[:5]]}")
    print(f"messages count={len(messages)} first={messages[0].title[:80]!r}")
    print(
        "routes "
        f"count={len(routes)} first_legs={len(routes[0].legs)} "
        f"first_line={routes[0].legs[0].line.label!r}"
    )


def _first_station(query: str, locations: Sequence[Location]) -> Location:
    for location in locations:
        if location.kind == "STATION" and location.global_id is not None:
            return location
    raise RuntimeError(f"No station result found for {query!r}")


if __name__ == "__main__":
    raise SystemExit(main())
