"""Build the bundled line directions dataset from MVV's GTFS feed.

MVG's schedule catalog only lists printed timetables, so it misses lines MVG
does not run, such as the S-Bahn, and lines that share a timetable with
another. The feed has every trip with its stops, so this derives, for every
station, the lines and directions that serve it and a name for each. Where
the branches of a rail line part, each branch is a direction of its own with
the end stations it serves:

    python scripts/build_directions.py gesamt_gtfs.zip

The feed is MVV's "Gesamt-Soll-Fahrplandaten", published under CC BY 4.0 at
https://www.mvv-muenchen.de/fileadmin/mediapool/developer/opendata/gesamt_gtfs.zip
"""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import math
import re
import zipfile
from collections import Counter, defaultdict
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_OUTPUT = (
    Path(__file__).parent.parent
    / "src"
    / "munich_transport"
    / "data"
    / "directions.json.gz"
)
ATTRIBUTION = "Münchner Verkehrs- und Tarifverbund GmbH (MVV), CC BY 4.0"

# An end station names a direction only if at least this share of the trips
# through the station ends there, so rare extensions do not rename a line.
MIN_TERMINUS_SHARE = 0.1
# Two end stations are the halves of split trains when the rarer one leaves
# together with the other at least this often.
MIN_SPLIT_SHARE = 0.5
# An end station lies on the way to another when going there first is at most
# this much longer than going straight; express trains skip stations, so
# shared stops alone do not show that two end stations are on one branch.
MAX_DETOUR = 1.2
# Only rail lines get a direction per branch: buses and trams have many route
# variants, and MVG's catalog names their directions.
_BRANCHING_TRANSPORT_TYPES = frozenset({"SBAHN", "BAHN"})

_DIRECTION_KEY_RE = re.compile(r"-([HR])-")


@dataclass(frozen=True, slots=True)
class _Route:
    label: str
    transport_type: str


@dataclass(slots=True)
class _Direction:
    """Trips of one line and direction through one station."""

    termini: Counter[str] = field(default_factory=Counter)
    # Stations after this one, by the end station of the trips through them.
    downstream: defaultdict[str, set[str]] = field(
        default_factory=lambda: defaultdict(set)
    )
    # End stations by departure time and platform: split trains leave both
    # halves from one platform at once. The halves have calendars of their
    # own, so the service is not part of the key.
    departures: defaultdict[tuple[str, str], set[str]] = field(
        default_factory=lambda: defaultdict(set)
    )

    def passed(self) -> set[str]:
        """Return the stations trips pass on the way to their end station."""

        return {
            station
            for terminus, stations in self.downstream.items()
            for station in stations
            if station != terminus
        }

    def branch(self, termini: set[str]) -> _Direction:
        """Return only the trips that end at one of these stations."""

        branch = _Direction()
        branch.termini.update(
            {terminus: self.termini[terminus] for terminus in termini}
        )
        for terminus in termini:
            branch.downstream[terminus] = self.downstream[terminus]
        for departure, ends in self.departures.items():
            if ends & termini:
                branch.departures[departure] = ends & termini
        return branch


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("feed", type=Path, help="MVV GTFS zip file")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    dataset = build_dataset(args.feed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    text = (
        json.dumps(dataset, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        + "\n"
    )
    # A fixed timestamp keeps the file unchanged when the feed is.
    args.output.write_bytes(gzip.compress(text.encode(), mtime=0))
    stations = dataset["stations"]
    assert isinstance(stations, dict)
    print(f"Wrote {len(stations)} stations to {args.output}")
    return 0


def build_dataset(feed: Path) -> dict[str, object]:
    """Return every station's line directions, keyed by MVG global id."""

    with zipfile.ZipFile(feed) as archive:
        (feed_info,) = _rows(archive, "feed_info.txt")
        routes = {
            row["route_id"]: route
            for row in _rows(archive, "routes.txt")
            if (route := _route(row)) is not None
        }
        stations, names, coordinates = _stations(archive)
        trips = {
            row["trip_id"]: (routes[row["route_id"]], match.group(1))
            for row in _rows(archive, "trips.txt")
            if row["route_id"] in routes
            and (match := _DIRECTION_KEY_RE.search(row["trip_id"]))
        }
        stop_times: defaultdict[str, list[tuple[int, str, str, str]]] = defaultdict(
            list
        )
        for row in _rows(archive, "stop_times.txt"):
            if row["trip_id"] in trips:
                stop_times[row["trip_id"]].append(
                    (
                        int(row["stop_sequence"]),
                        stations[row["stop_id"]],
                        row["stop_id"],
                        row["departure_time"],
                    )
                )

    directions: defaultdict[tuple[str, _Route, str], _Direction] = defaultdict(
        _Direction
    )
    for trip_id, stops in stop_times.items():
        route, direction_key = trips[trip_id]
        stops.sort()
        terminus = stops[-1][1]
        for index, (_, station, platform, departure_time) in enumerate(stops[:-1]):
            # Loop lines pass their end station on the way; that is no direction.
            if station == terminus:
                continue
            direction = directions[(station, route, direction_key)]
            direction.termini[terminus] += 1
            direction.downstream[terminus].update(
                stop[1] for stop in stops[index + 1 :]
            )
            direction.departures[(departure_time, platform)].add(terminus)

    by_station: defaultdict[str, list[list[str]]] = defaultdict(list)
    for (station, route, direction_key), direction in sorted(
        directions.items(),
        key=lambda item: (item[0][0], item[0][1].label, item[0][2]),
    ):
        branches = (
            _branches(direction, station, coordinates)
            if route.transport_type in _BRANCHING_TRANSPORT_TYPES
            else []
        )
        if len(branches) < 2:
            by_station[station].append(
                [
                    route.label,
                    route.transport_type,
                    direction_key,
                    _direction_name(direction, names),
                ]
            )
            continue
        for termini in branches:
            by_station[station].append(
                [
                    route.label,
                    route.transport_type,
                    direction_key,
                    _direction_name(direction.branch(termini), names),
                    sorted(names[terminus] for terminus in termini),
                ]
            )

    return {
        "attribution": ATTRIBUTION,
        "feed_version": feed_info["feed_version"],
        "feed_end_date": feed_info["feed_end_date"],
        "stations": dict(by_station),
    }


def _direction_name(direction: _Direction, names: dict[str, str]) -> str:
    """Name a direction after where the line goes, not where most trips end.

    That is the outermost end station that a fair share of trips reach, and
    for split trains both halves.
    """

    total = sum(direction.termini.values())
    frequent = [
        terminus
        for terminus, count in direction.termini.most_common()
        if count >= total * MIN_TERMINUS_SHARE
    ]
    passed = direction.passed()
    outer = [terminus for terminus in frequent if terminus not in passed]
    candidates = outer or frequent
    terminus = candidates[0]
    for other in candidates[1:]:
        if _split_halves(direction, terminus, other):
            return " / ".join(sorted((names[terminus], names[other])))
    return names[terminus]


def _branches(
    direction: _Direction,
    station: str,
    coordinates: dict[str, tuple[float, float]],
) -> list[set[str]]:
    """Return the end stations of each branch a fair share of trips take.

    Two end stations are on one branch when trips to them share a station
    after this one, or when one lies on the way to the other. Rarely served
    branches are left out, so their trips belong to every branch.
    """

    termini = list(direction.termini)
    branch_of = {terminus: {terminus} for terminus in termini}
    for index, first in enumerate(termini):
        for second in termini[index + 1 :]:
            if branch_of[first] is branch_of[second]:
                continue
            if direction.downstream[first] & direction.downstream[second] or (
                _on_the_way(coordinates, station, first, second)
                or _on_the_way(coordinates, station, second, first)
            ):
                merged = branch_of[first] | branch_of[second]
                for terminus in merged:
                    branch_of[terminus] = merged

    total = sum(direction.termini.values())
    branches = {id(branch): branch for branch in branch_of.values()}.values()
    return sorted(
        (
            branch
            for branch in branches
            if sum(direction.termini[terminus] for terminus in branch)
            >= total * MIN_TERMINUS_SHARE
        ),
        key=lambda branch: -sum(direction.termini[terminus] for terminus in branch),
    )


def _on_the_way(
    coordinates: dict[str, tuple[float, float]],
    start: str,
    via: str,
    end: str,
) -> bool:
    def distance(first: str, second: str) -> float:
        (lat1, lon1), (lat2, lon2) = coordinates[first], coordinates[second]
        x = (lon2 - lon1) * math.cos(math.radians((lat1 + lat2) / 2))
        return math.hypot(x, lat2 - lat1)

    return distance(start, via) + distance(via, end) <= MAX_DETOUR * distance(
        start, end
    )


def _split_halves(direction: _Direction, first: str, second: str) -> bool:
    # Departures repeat on many days, so this counts departure times rather
    # than trips.
    firsts = seconds = together = 0
    for termini in direction.departures.values():
        firsts += first in termini
        seconds += second in termini
        together += first in termini and second in termini
    return together >= min(firsts, seconds) * MIN_SPLIT_SHARE


def _route(row: dict[str, str]) -> _Route | None:
    """Return the route's line, or None for replacement services."""

    label = row["route_short_name"]
    route_id = row["route_id"]
    if "SEV" in label or "_SEV" in route_id:
        return None
    if route_id.startswith("ddb-92-"):
        transport_type = "SBAHN"
    elif row["route_type"] == "2":
        transport_type = "BAHN"
    elif row["route_type"] == "1":
        transport_type = "UBAHN"
    elif row["route_type"] == "0":
        transport_type = "TRAM"
    elif route_id.startswith("de:mvg:"):
        transport_type = "BUS"
    else:
        transport_type = "REGIONAL_BUS"
    return _Route(label=label, transport_type=transport_type)


def _stations(
    archive: zipfile.ZipFile,
) -> tuple[dict[str, str], dict[str, str], dict[str, tuple[float, float]]]:
    """Map every stop to its station, and every station to its name and place."""

    stations: dict[str, str] = {}
    names: dict[str, str] = {}
    coordinates: dict[str, tuple[float, float]] = {}
    for row in _rows(archive, "stops.txt"):
        stations[row["stop_id"]] = row["parent_station"] or row["stop_id"]
        if not row["parent_station"]:
            names[row["stop_id"]] = row["stop_name"]
            coordinates[row["stop_id"]] = (
                float(row["stop_lat"]),
                float(row["stop_lon"]),
            )
    return stations, names, coordinates


def _rows(archive: zipfile.ZipFile, name: str) -> Iterator[dict[str, str]]:
    with archive.open(name) as file:
        yield from csv.DictReader(io.TextIOWrapper(file, encoding="utf-8-sig"))


if __name__ == "__main__":
    raise SystemExit(main())
