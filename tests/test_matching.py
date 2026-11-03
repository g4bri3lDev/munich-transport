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
S1 = Line(label="S1", transport_type="SBAHN")
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

TO_AIRPORT = StationDirectionOption(
    id="SBAHN:S1:R:Flughafen München",
    schedule_kind="SBAHN",
    line_label="S1",
    direction_key="R",
    directions=("Flughafen München",),
    raw_directions=("Flughafen München",),
    schedule_codes=(),
    excluded_destinations=("Freising",),
)


def departure(
    minutes: int,
    *,
    line: Line = U3,
    direction_key: str | None = "H",
    cancelled: bool = False,
    destination: str = "Fürstenried West",
    platform: int | None = None,
) -> Departure:
    time = NOW + timedelta(minutes=minutes)
    return Departure(
        planned_departure=time,
        realtime_departure=time,
        line=line,
        destination=destination,
        realtime=True,
        cancelled=cancelled,
        direction_key=direction_key,
        platform=platform,
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


def test_normal_terminus_is_first_direction() -> None:
    assert FUERSTENRIED_WEST.normal_terminus == "Sendlinger Tor / Fürstenried West"
    assert MOOSACH.normal_terminus == "Moosach Bf"


def test_normal_terminus_falls_back_to_first_direction() -> None:
    option = StationDirectionOption.from_id("SUBWAY:U3:H")

    assert option.normal_terminus is None


def test_option_matches_line_and_direction_key() -> None:
    assert FUERSTENRIED_WEST.matches(departure(1))
    assert not FUERSTENRIED_WEST.matches(departure(1, direction_key="R"))
    assert not FUERSTENRIED_WEST.matches(departure(1, line=U6))


def test_option_ignores_spaces_in_line_labels() -> None:
    option = StationDirectionOption.from_id("BAHN:RE 9:R")

    assert option.matches(departure(1, line=Line("RE9", "BAHN"), direction_key="R"))
    assert not option.matches(
        departure(1, line=Line("RE 90", "BAHN"), direction_key="R")
    )


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


def test_dict_round_trips_every_field() -> None:
    assert StationDirectionOption.from_dict(FUERSTENRIED_WEST.to_dict()) == (
        FUERSTENRIED_WEST
    )


def test_dict_round_trips_branches() -> None:
    assert StationDirectionOption.from_dict(TO_AIRPORT.to_dict()) == TO_AIRPORT


def test_from_dict_reads_options_stored_before_branches() -> None:
    stored = FUERSTENRIED_WEST.to_dict()
    del stored["excluded_destinations"]

    assert StationDirectionOption.from_dict(stored) == FUERSTENRIED_WEST


def test_branch_leaves_out_the_other_branch() -> None:
    def s1(destination: str) -> Departure:
        return departure(
            1, line=S1, direction_key="R", destination=destination, platform=1
        )

    assert TO_AIRPORT.matches(s1("Flughafen München"))
    assert not TO_AIRPORT.matches(s1("Freising"))
    # Trips cut short, for example by construction, count for every branch.
    assert TO_AIRPORT.matches(s1("Neufahrn"))
    # Before the split, both halves leave as one train.
    assert TO_AIRPORT.matches(s1("Flughafen München / Freising"))
    assert not TO_AIRPORT.matches(
        departure(1, line=S1, direction_key="H", destination="Flughafen München")
    )


def test_from_id_matches_every_branch() -> None:
    option = StationDirectionOption.from_id(TO_AIRPORT.id)

    assert option.direction_key == "R"
    assert option.matches(
        departure(1, line=S1, direction_key="R", destination="Freising")
    )


def test_from_dict_keeps_options_without_direction_key() -> None:
    option = StationDirectionOption(
        id="NIGHT_LINE:N40:Kieferngarten",
        schedule_kind="NIGHT_LINE",
        line_label="N40",
        direction_key=None,
        directions=("Kieferngarten",),
        raw_directions=("Kieferngarten",),
        schedule_codes=(),
    )

    restored = StationDirectionOption.from_dict(option.to_dict())

    assert restored.direction_key is None
    assert restored.matches(departure(1, line=Line("N40", "NIGHT_LINE")))


def test_from_dict_rejects_malformed_data() -> None:
    with pytest.raises(ValueError, match="direction option"):
        StationDirectionOption.from_dict({"id": "SUBWAY:U3:H"})


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


def test_select_departures_merges_split_train_halves() -> None:
    departures = [
        departure(5, line=S1, direction_key="R", destination="Freising", platform=2),
        departure(
            5, line=S1, direction_key="R", destination="Flughafen München", platform=2
        ),
        departure(25, line=S1, direction_key="R", destination="Freising", platform=2),
    ]

    selected = select_departures(departures, [])

    assert [d.destination for d in selected] == [
        "Flughafen München / Freising",
        "Freising",
    ]


def test_select_departures_only_merges_trains_with_a_platform() -> None:
    bus = Line(label="809", transport_type="BUS")
    departures = [
        departure(5, line=U6, destination="Fröttmaning", platform=1),
        departure(5, line=U6, destination="Garching, Forschungszentrum", platform=1),
        departure(5, line=bus, direction_key="R", destination="Entraching"),
        departure(5, line=bus, direction_key="R", destination="Hechenwang"),
        departure(5, line=S1, direction_key="R", destination="Freising"),
        departure(5, line=S1, direction_key="R", destination="Flughafen München"),
    ]

    selected = select_departures(departures, [])

    assert len(selected) == len(departures)


def test_select_departures_keeps_simultaneous_departures_apart() -> None:
    departures = [
        departure(5, line=S1, direction_key="R", destination="Freising", platform=2),
        departure(5, line=S1, direction_key="R", destination="Pasing", platform=1),
        departure(5, direction_key=None, destination="Moosach"),
        departure(5, direction_key=None, destination="Fürstenried West"),
        departure(
            5,
            line=S1,
            direction_key="R",
            destination="Erding",
            platform=2,
            cancelled=True,
        ),
    ]

    selected = select_departures(departures, [], include_cancelled=True)

    assert sorted(d.destination for d in selected) == [
        "Erding",
        "Freising",
        "Fürstenried West",
        "Moosach",
        "Pasing",
    ]


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
