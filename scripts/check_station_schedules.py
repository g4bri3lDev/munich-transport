"""Live check for MVG station schedule catalog data.

This script intentionally lives outside the regular pytest suite because it
depends on the live MVG website.
"""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Iterable, Sequence

from munich_transport import AiohttpTransport, MunichTransportClient
from munich_transport.models import Location
from munich_transport.schedules import group_station_schedules


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    station = parser.add_mutually_exclusive_group(required=False)
    station.add_argument(
        "--query",
        default="Marienplatz",
        help="Station search query to resolve before checking schedules.",
    )
    station.add_argument(
        "--global-id",
        help="Station global id to check directly, for example de:09162:2.",
    )
    parser.add_argument("--limit", type=int, default=8, help="Departures to sample.")
    parser.add_argument("--timeout", type=float, default=15.0)
    args = parser.parse_args(argv)

    return asyncio.run(
        _run(
            query=args.query,
            global_id=args.global_id,
            departure_limit=args.limit,
            timeout_seconds=args.timeout,
        )
    )


async def _run(
    *,
    query: str | None,
    global_id: str | None,
    departure_limit: int,
    timeout_seconds: float,
) -> int:
    async with AiohttpTransport(timeout=timeout_seconds) as transport:
        client = MunichTransportClient(transport)
        resolved_global_id = global_id or await _resolve_station(client, query or "")

        station = await client.station(resolved_global_id)
        schedules = await client.station_schedules(resolved_global_id)
        lines = await client.lines(resolved_global_id)
        departures = await client.departures(
            resolved_global_id,
            limit=departure_limit,
        )

    print(f"station: {station.name} ({station.global_id})")
    print(f"abbreviation: {station.abbreviation}")
    print(f"products: {', '.join(station.transport_types)}")
    print()
    print(f"station schedule entries: {len(schedules)}")
    for schedule in schedules:
        print(
            f"- {schedule.schedule_kind} {schedule.line_label} "
            f"[code={schedule.schedule_code or '-'} "
            f"direction_key={schedule.direction_key or '-'}] "
            f"-> {schedule.direction} ({schedule.pdf_url})"
        )

    print()
    print("selectable direction groups:")
    for group in group_station_schedules(schedules):
        directions = " / ".join(group.directions)
        codes = ",".join(group.schedule_codes)
        print(
            f"- {group.schedule_kind} {group.line_label} "
            f"[direction_key={group.direction_key or '-'} codes={codes}] "
            f"-> {directions}"
        )

    print()
    print(f"served line labels: {', '.join(_unique(line.label for line in lines))}")
    print(
        "sample departure pairs: "
        + ", ".join(
            f"{departure.line.label}[{departure.direction_key or '-'}] "
            f"-> {departure.destination}"
            for departure in departures
        )
    )

    if not schedules:
        print()
        print("error: station schedule catalog returned no entries")
        return 1
    return 0


async def _resolve_station(client: MunichTransportClient, query: str) -> str:
    locations = await client.search_locations(query)
    for location in locations:
        if location.kind == "STATION" and location.global_id is not None:
            _print_resolved_location(location)
            return location.global_id
    raise RuntimeError(f"No station result found for {query!r}")


def _print_resolved_location(location: Location) -> None:
    place = f", {location.place}" if location.place else ""
    print(f"resolved query to: {location.name}{place} ({location.global_id})")
    print()


def _unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(values))


if __name__ == "__main__":
    raise SystemExit(main())
