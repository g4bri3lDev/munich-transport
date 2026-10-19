from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from munich_transport.models import (
    Departure,
    Disruption,
    Line,
    StationDirectionOption,
)
from munich_transport.schedules import direction_names_match, select_departures

NOW = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)
U3 = Line(label="U3", transport_type="UBAHN")
U6 = Line(label="U6", transport_type="UBAHN")
BONNER_PLATZ = "de:09162:410"

FUERSTENRIED_WEST = StationDirectionOption(
    id="SUBWAY:U3:H",
    schedule_kind="SUBWAY",
    line_label="U3",
    direction_key="H",
    directions=("Sendlinger Tor / Fürstenried West", "Fürstenried West"),
    raw_directions=(),
    schedule_codes=("H", "I"),
)
MOOSACH = StationDirectionOption(
    id="SUBWAY:U3:R",
    schedule_kind="SUBWAY",
    line_label="U3",
    direction_key="R",
    directions=("Moosach Bf",),
    raw_directions=(),
    schedule_codes=("R",),
)


def departure(
    minutes: int,
    *,
    line: Line = U3,
    direction_key: str | None = "H",
    cancelled: bool = False,
) -> Departure:
    time = NOW + timedelta(minutes=minutes)
    return Departure(
        planned_departure=time,
        realtime_departure=time,
        line=line,
        destination="Fürstenried West",
        realtime=True,
        cancelled=cancelled,
        direction_key=direction_key,
    )


def disruption(
    *,
    lines: tuple[Line, ...] = (),
    stations: tuple[str, ...] = (),
    valid_from: datetime | None = None,
    valid_to: datetime | None = None,
) -> Disruption:
    return Disruption(
        title="Disruption",
        description_html="",
        kind="INCIDENT",
        valid_from=valid_from,
        valid_to=valid_to,
        lines=lines,
        station_global_ids=stations,
    )


def test_normal_terminus_skips_temporary_variants() -> None:
    assert FUERSTENRIED_WEST.normal_terminus == "Fürstenried West"
    assert MOOSACH.normal_terminus == "Moosach Bf"


def test_normal_terminus_falls_back_to_first_direction() -> None:
    option = StationDirectionOption.from_id("SUBWAY:U3:H")

    assert option.normal_terminus is None


def test_option_matches_line_and_direction_key() -> None:
    assert FUERSTENRIED_WEST.matches(departure(1))
    assert not FUERSTENRIED_WEST.matches(departure(1, direction_key="R"))
    assert not FUERSTENRIED_WEST.matches(departure(1, line=U6))


def test_option_without_direction_key_matches_whole_line() -> None:
    option = StationDirectionOption.from_id("BUS:52:")

    assert option.direction_key is None
    assert option.matches(departure(1, line=Line(label="52", transport_type="BUS")))


def test_from_id_round_trips_catalog_ids() -> None:
    option = StationDirectionOption.from_id("SUBWAY:U3:H")

    assert (option.schedule_kind, option.line_label, option.direction_key) == (
        "SUBWAY",
        "U3",
        "H",
    )
    assert option.matches(departure(1))


def test_from_id_rejects_malformed_ids() -> None:
    with pytest.raises(ValueError, match="Not a direction option id"):
        StationDirectionOption.from_id("U3")


def test_select_departures_filters_sorts_and_skips_cancelled() -> None:
    departures = [
        departure(8),
        departure(3, cancelled=True),
        departure(1, direction_key="R"),
        departure(5),
        departure(2, line=U6),
    ]

    selected = select_departures(departures, [FUERSTENRIED_WEST])

    assert [d.realtime_departure - NOW for d in selected] == [
        timedelta(minutes=5),
        timedelta(minutes=8),
    ]


def test_select_departures_can_keep_cancelled() -> None:
    departures = [departure(3, cancelled=True), departure(5)]

    selected = select_departures(
        departures, [FUERSTENRIED_WEST], include_cancelled=True
    )

    assert [d.cancelled for d in selected] == [True, False]


def test_select_departures_without_options_selects_everything() -> None:
    departures = [departure(2, line=U6), departure(1)]

    assert select_departures(departures, []) == [departures[1], departures[0]]


@pytest.mark.parametrize(
    ("name", "other", "expected"),
    [
        ("Tierpark (Alemannenstr)", "Tierpark (Alemannenstr.)", True),
        ("Garching, Forschungszentrum", "Garching-Forschungszentrum", True),
        ("Giesing", "Giesing Bf.", True),
        ("Moosach Bahnhof", "Moosach Bf", True),
        ("Goetheplatz", "Goetheplatz / Klinikum Großhadern", True),
        ("Fröttmaning", "Garching, Forschungszentrum", False),
        ("Hbf", "Hauptbahnhof", False),
    ],
)
def test_direction_names_match(name: str, other: str, expected: bool) -> None:
    assert direction_names_match(name, other) is expected


def test_disruption_is_active_within_validity() -> None:
    hour = timedelta(hours=1)

    assert disruption().is_active(NOW)
    assert disruption(valid_from=NOW - hour, valid_to=NOW + hour).is_active(NOW)
    assert not disruption(valid_from=NOW + hour).is_active(NOW)
    assert not disruption(valid_to=NOW - hour).is_active(NOW)


def test_disruption_affects_station() -> None:
    assert disruption(stations=(BONNER_PLATZ,)).affects_station(BONNER_PLATZ, [])
    assert not disruption(stations=("de:09162:1",), lines=(U3,)).affects_station(
        BONNER_PLATZ, ["U3"]
    )
    assert disruption(lines=(U3,)).affects_station(BONNER_PLATZ, ["U3"])
    assert not disruption(lines=(U6,)).affects_station(BONNER_PLATZ, ["U3"])
    assert disruption().affects_station(BONNER_PLATZ, ["U3"])


def test_disruption_affects_line() -> None:
    assert disruption(lines=(U3,)).affects_line("U3", BONNER_PLATZ)
    assert disruption(lines=(U3,), stations=(BONNER_PLATZ,)).affects_line(
        "U3", BONNER_PLATZ
    )
    assert not disruption(lines=(U3,), stations=("de:09162:1",)).affects_line(
        "U3", BONNER_PLATZ
    )
    assert not disruption(lines=(U6,)).affects_line("U3", BONNER_PLATZ)
    # Network-wide announcements do not mark every line as disrupted.
    assert not disruption().affects_line("U3", BONNER_PLATZ)
