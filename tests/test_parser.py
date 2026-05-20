from __future__ import annotations

import json
from pathlib import Path

import pytest

from munich_transport.exceptions import ParseError
from munich_transport.parser import (
    parse_departures,
    parse_disruptions,
    parse_lines,
    parse_locations,
    parse_routes,
    parse_station,
)

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> object:
    return json.loads((FIXTURES / name).read_text())


def test_parse_locations_keeps_station_and_address_results() -> None:
    locations = parse_locations(load_fixture("locations_marienplatz.json"))

    assert locations[0].global_id == "de:09162:2"
    assert locations[0].transport_types == ("SBAHN", "UBAHN", "BUS")
    assert locations[1].kind == "ADDRESS"
    assert locations[1].global_id is None


def test_parse_station_detail() -> None:
    station = parse_station(load_fixture("station_marienplatz.json"))

    assert station.global_id == "de:09162:2"
    assert station.abbreviation == "MP"
    assert station.transport_types == ("SBAHN", "UBAHN", "BUS")


def test_parse_departures_with_notices() -> None:
    departures = parse_departures(load_fixture("departures_marienplatz.json"))

    assert departures[0].line.label == "132"
    assert departures[0].destination == "Implerstraße"
    assert departures[0].delay_minutes == 2
    assert departures[1].platform == 1
    assert departures[1].notices[0].message == "Polizeieinsatz"


def test_parse_lines() -> None:
    lines = parse_lines(load_fixture("lines_marienplatz.json"))

    assert [line.label for line in lines] == ["U3", "S8"]


def test_parse_routes() -> None:
    routes = parse_routes(load_fixture("routes_marienplatz_hauptbahnhof.json"))

    assert routes[0].unique_id == -1237819603061240
    assert routes[0].legs[0].origin.name == "Marienplatz"
    assert routes[0].legs[0].line.transport_type == "PEDESTRIAN"


def test_parse_disruptions() -> None:
    disruptions = parse_disruptions(load_fixture("messages.json"))

    assert disruptions[0].kind == "INCIDENT"
    assert disruptions[0].lines[0].label == "U3"


def test_parse_error_for_wrong_top_level_shape() -> None:
    with pytest.raises(ParseError):
        parse_locations({"not": "a list"})
