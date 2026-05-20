from __future__ import annotations

from munich_transport.models import StationSchedule
from munich_transport.schedules import (
    build_station_direction_options,
    group_station_schedules,
)


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
    ]

    groups = group_station_schedules(schedules, include_non_service=True)

    assert len(groups) == 1
    assert groups[0].line_label == "P8"


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
    assert options[0].label == (
        "U3 Richtung Fürstenried West / Sendlinger Tor / Fürstenried West"
    )
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
