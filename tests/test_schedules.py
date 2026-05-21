from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from munich_transport.models import Departure, Line, StationSchedule
from munich_transport.parser import parse_station_schedules
from munich_transport.schedules import (
    build_departure_direction_options,
    build_station_direction_options,
    group_station_schedules,
)

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> object:
    return json.loads((FIXTURES / name).read_text())


def test_group_station_schedules_combines_temporary_variants() -> None:
    schedules = [
        StationSchedule(
            schedule_kind="SUBWAY",
            line_label="U3",
            direction="Fürstenried West",
            pdf_url="https://www.mvg.de/aushangfahrplan/U3_H_BP_52.pdf",
            schedule_code="H",
            station_abbreviation="BP",
            stop_number="52",
            direction_key="H",
        ),
        StationSchedule(
            schedule_kind="SUBWAY",
            line_label="U3",
            direction="Sendlinger Tor / Fürstenried West",
            pdf_url="https://www.mvg.de/aushangfahrplan/U3_I_BP_52.pdf",
            schedule_code="I",
            station_abbreviation="BP",
            stop_number="52",
            direction_key="H",
        ),
        StationSchedule(
            schedule_kind="SUBWAY",
            line_label="U3",
            direction="Moosach Bf",
            pdf_url="https://www.mvg.de/aushangfahrplan/U3_R_BP_51.pdf",
            schedule_code="R",
            station_abbreviation="BP",
            stop_number="51",
            direction_key="R",
        ),
        StationSchedule(
            schedule_kind="CONTEXT_MAP",
            line_label="P8",
            direction="Umgebungsplan U-Bahn",
            pdf_url="https://www.mvg.de/aushangfahrplan/P8_H_BP_0.pdf",
            schedule_code="H",
            station_abbreviation="BP",
            stop_number="0",
            direction_key="H",
        ),
    ]

    groups = group_station_schedules(schedules)

    assert len(groups) == 2
    assert groups[0].line_label == "U3"
    assert groups[0].direction_key == "H"
    assert groups[0].directions == (
        "Fürstenried West",
        "Sendlinger Tor / Fürstenried West",
    )
    assert groups[0].schedule_codes == ("H", "I")
    assert groups[1].direction_key == "R"
    assert groups[1].directions == ("Moosach Bf",)


def test_group_station_schedules_can_include_non_service_entries() -> None:
    schedules = [
        StationSchedule(
            schedule_kind="CONTEXT_MAP",
            line_label="P8",
            direction="Umgebungsplan U-Bahn",
            pdf_url="https://www.mvg.de/aushangfahrplan/P8_H_BP_0.pdf",
            schedule_code="H",
            station_abbreviation="BP",
            stop_number="0",
            direction_key="H",
        ),
        StationSchedule(
            schedule_kind="STATION_OVERVIEW_MAP",
            line_label="P7",
            direction="Haltestellen-Übersichtsplan Bus/Tram",
            pdf_url="https://www.mvg.de/aushangfahrplan/P7_H_SE_0.pdf",
            schedule_code="H",
            station_abbreviation="SE",
            stop_number="0",
            direction_key="H",
        ),
    ]

    assert group_station_schedules(schedules) == []

    groups = group_station_schedules(schedules, include_non_service=True)

    assert [group.line_label for group in groups] == ["P8", "P7"]


def test_build_station_direction_options_returns_config_shape() -> None:
    schedules = [
        StationSchedule(
            schedule_kind="SUBWAY",
            line_label="U3",
            direction="Fürstenried West, gültig ab 14.12.2025",
            pdf_url="https://www.mvg.de/aushangfahrplan/U3_H_BP_52.pdf",
            schedule_code="H",
            station_abbreviation="BP",
            stop_number="52",
            direction_key="H",
        ),
        StationSchedule(
            schedule_kind="SUBWAY",
            line_label="U3",
            direction="Sendlinger Tor / Fürstenried West (gültig vom 18.05.)",
            pdf_url="https://www.mvg.de/aushangfahrplan/U3_I_BP_52.pdf",
            schedule_code="I",
            station_abbreviation="BP",
            stop_number="52",
            direction_key="H",
        ),
        StationSchedule(
            schedule_kind="CONTEXT_MAP",
            line_label="P8",
            direction="Umgebungsplan U-Bahn",
            pdf_url="https://www.mvg.de/aushangfahrplan/P8_H_BP_0.pdf",
            schedule_code="H",
            station_abbreviation="BP",
            stop_number="0",
            direction_key="H",
        ),
    ]

    options = build_station_direction_options(schedules)

    assert len(options) == 1
    assert options[0].id == "SUBWAY:U3:H"
    assert options[0].line_label == "U3"
    assert options[0].direction_key == "H"
    assert options[0].directions == (
        "Fürstenried West",
        "Sendlinger Tor / Fürstenried West",
    )
    assert options[0].raw_directions == (
        "Fürstenried West, gültig ab 14.12.2025",
        "Sendlinger Tor / Fürstenried West (gültig vom 18.05.)",
    )


def test_build_departure_direction_options_groups_by_live_direction_key() -> None:
    departures = [
        _departure("534", "REGIONAL_BUS", "H", "Pfarrkofen (Ergolding)"),
        _departure("534", "REGIONAL_BUS", "H", "Rottenburg ü.Hohenthann"),
        _departure("534", "REGIONAL_BUS", "R", "Landshut ü. Ergolding"),
    ]

    options = build_departure_direction_options(departures)

    assert [option.id for option in options] == [
        "REGIONAL_BUS:534:H",
        "REGIONAL_BUS:534:R",
    ]
    assert options[0].directions == (
        "Pfarrkofen (Ergolding)",
        "Rottenburg ü.Hohenthann",
    )
    assert options[0].raw_directions == options[0].directions
    assert options[0].schedule_codes == ()


def test_build_departure_direction_options_keeps_unkeyed_destinations() -> None:
    departures = [
        _departure("N40", "NIGHT_LINE", None, "Klinikum Großhadern"),
        _departure("N40", "NIGHT_LINE", None, "Kieferngarten"),
        _departure("N40", "NIGHT_LINE", None, "Klinikum Großhadern"),
    ]

    options = build_departure_direction_options(departures)

    assert [option.id for option in options] == [
        "NIGHT_LINE:N40:Kieferngarten",
        "NIGHT_LINE:N40:Klinikum Großhadern",
    ]
    assert [option.directions for option in options] == [
        ("Kieferngarten",),
        ("Klinikum Großhadern",),
    ]


def test_build_station_direction_options_strips_parenthetical_notes() -> None:
    schedules = [
        StationSchedule(
            schedule_kind="TRAM",
            line_label="28",
            direction="Sendlinger Tor (ab Kurfürstenplatz in Linie 27 enthalten)",
            pdf_url="https://www.mvg.de/aushangfahrplan/28_H_SP_1.pdf",
            schedule_code="H",
            station_abbreviation="SP",
            stop_number="1",
            direction_key="H",
        ),
    ]

    options = build_station_direction_options(schedules)

    assert options[0].directions == ("Sendlinger Tor",)
    assert options[0].raw_directions == (
        "Sendlinger Tor (ab Kurfürstenplatz in Linie 27 enthalten)",
    )


def test_bonner_platz_characterization_groups_temporary_u3_termini() -> None:
    schedules = parse_station_schedules(
        load_fixture("station_schedules_bonner_platz.json")
    )

    options = build_station_direction_options(schedules)

    assert [option.id for option in options] == ["SUBWAY:U3:H", "SUBWAY:U3:R"]
    assert options[0].schedule_codes == ("H", "I")
    assert options[0].directions == (
        "Fürstenried West",
        "Sendlinger Tor / Fürstenried West",
    )
    assert options[1].schedule_codes == ("R", "S")
    assert options[1].directions == ("Moosach Bf", "Implerstraße / Moosach Bf")


def test_sendlinger_tor_characterization_keeps_night_line_options() -> None:
    schedules = parse_station_schedules(
        load_fixture("station_schedules_sendlinger_tor_night.json")
    )

    options = build_station_direction_options(schedules)

    assert [option.id for option in options] == [
        "NIGHT_LINE:N17:H",
        "NIGHT_LINE:N17:R",
        "NIGHT_LINE:N41:H",
        "NIGHT_LINE:N41:R",
    ]
    assert options[2].directions == ("Fürstenried West",)
    assert options[2].raw_directions == (
        "Fürstenried West, nicht gültig vom 18.05. - 18.09.2026",
        "Fürstenried West, gültig vom 18.05. - 18.09.2026",
    )


def test_machtlfinger_characterization_has_bus_and_subway_but_no_night_lines() -> None:
    schedules = parse_station_schedules(
        load_fixture("station_schedules_machtlfinger_strasse.json")
    )

    options = build_station_direction_options(schedules)

    assert [option.id for option in options] == [
        "BUS:51:H",
        "BUS:51:R",
        "SUBWAY:U3:H",
        "SUBWAY:U3:R",
    ]
    assert all(option.schedule_kind != "NIGHT_LINE" for option in options)


def test_marienplatz_characterization_schedule_catalog_has_no_s_bahn() -> None:
    schedules = parse_station_schedules(
        load_fixture("station_schedules_marienplatz.json")
    )

    assert not any(schedule.line_label.startswith("S") for schedule in schedules)


def _departure(
    line_label: str,
    transport_type: str,
    direction_key: str | None,
    destination: str,
) -> Departure:
    timestamp = datetime(2026, 5, 21, 12, 0, tzinfo=UTC)
    return Departure(
        planned_departure=timestamp,
        realtime_departure=timestamp,
        line=Line(label=line_label, transport_type=transport_type),
        destination=destination,
        realtime=True,
        cancelled=False,
        direction_key=direction_key,
    )
