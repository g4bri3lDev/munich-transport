from __future__ import annotations

from datetime import UTC, datetime

from munich_transport.client import MunichTransportClient
from munich_transport.directions import DirectionDataset
from munich_transport.models import Station
from munich_transport.types import DIRECTION_SAMPLE_OFFSETS_MINUTES, JsonValue

NO_TIMETABLE = DirectionDataset(feed_version="test", valid_until=None)
NO_SAMPLED_DEPARTURES: tuple[JsonValue, ...] = ([],) * (
    len(DIRECTION_SAMPLE_OFFSETS_MINUTES) - 1
)


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
    client = MunichTransportClient(transport, direction_dataset=NO_TIMETABLE)

    assert await client.search_locations("Marienplatz") == []
    assert transport.calls == [
        ("/api/bgw-pt/v3/locations", {"query": "Marienplatz"}),
    ]


async def test_departures_uses_global_id_limit_and_products() -> None:
    transport = FakeTransport([])
    client = MunichTransportClient(transport, direction_dataset=NO_TIMETABLE)

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


async def test_departures_passes_offset_only_when_set() -> None:
    transport = FakeTransport(([], []))
    client = MunichTransportClient(transport, direction_dataset=NO_TIMETABLE)

    await client.departures("de:09162:7", transport_types=("SBAHN",))
    await client.departures(
        "de:09162:7", transport_types=("SBAHN",), offset_minutes=180
    )

    assert [params for _, params in transport.calls] == [
        {"globalId": "de:09162:7", "limit": "100", "transportTypes": "SBAHN"},
        {
            "globalId": "de:09162:7",
            "limit": "100",
            "transportTypes": "SBAHN",
            "offsetInMinutes": "180",
        },
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
    client = MunichTransportClient(transport, direction_dataset=NO_TIMETABLE)

    schedules = await client.station_schedules("de:09162:2")

    assert schedules[0].line_label == "U3"
    assert schedules[0].direction.startswith("Sendlinger Tor")
    assert transport.calls == [
        ("/.rest/zdm/stations/de:09162:2", None),
        ("/.rest/aushang/stations", {"id": "MP"}),
    ]


async def test_station_schedules_by_abbreviation_uses_aushang_directly() -> None:
    transport = FakeTransport([])
    client = MunichTransportClient(transport, direction_dataset=NO_TIMETABLE)

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
    client = MunichTransportClient(transport, direction_dataset=NO_TIMETABLE)

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
                        "Implerstraße / Moosach Bf (gültig vom 18.05. - 18.09.2026)"
                    ),
                },
            ],
            [{"label": "U3", "transportType": "UBAHN"}],
        )
    )
    client = MunichTransportClient(transport, direction_dataset=NO_TIMETABLE)

    options = await client.station_direction_options("de:09162:410")

    assert len(options) == 1
    assert options[0].id == "SUBWAY:U3:R"
    assert options[0].directions == ("Moosach Bf", "Implerstraße / Moosach Bf")


async def test_station_direction_options_falls_back_without_abbreviation() -> None:
    transport = FakeTransport(
        (
            {
                "id": "de:09274:3590",
                "name": "Oberglaim",
                "place": "Ergolding",
                "divaId": 3590,
                "products": ["BUS"],
                "latitude": 48.58163,
                "longitude": 12.15263,
            },
            [],
            [
                {
                    "plannedDepartureTime": 1779275760000,
                    "realtime": True,
                    "delayInMinutes": 0,
                    "realtimeDepartureTime": 1779275760000,
                    "transportType": "REGIONAL_BUS",
                    "label": "534",
                    "divaId": "12534",
                    "network": "mvv",
                    "destination": "Pfarrkofen (Ergolding)",
                    "cancelled": False,
                    "messages": [],
                    "infos": [],
                    "lineId": "mvv:12534: :H:j26",
                },
                {
                    "plannedDepartureTime": 1779279360000,
                    "realtime": True,
                    "delayInMinutes": 0,
                    "realtimeDepartureTime": 1779279360000,
                    "transportType": "REGIONAL_BUS",
                    "label": "534",
                    "divaId": "12534",
                    "network": "mvv",
                    "destination": "Landshut ü. Ergolding",
                    "cancelled": False,
                    "messages": [],
                    "infos": [],
                    "lineId": "mvv:12534: :R:j26",
                },
            ],
            *NO_SAMPLED_DEPARTURES,
        )
    )
    client = MunichTransportClient(transport, direction_dataset=NO_TIMETABLE)

    options = await client.station_direction_options("de:09274:3590")

    assert [option.id for option in options] == [
        "REGIONAL_BUS:534:H",
        "REGIONAL_BUS:534:R",
    ]
    assert transport.calls[:3] == [
        ("/.rest/zdm/stations/de:09274:3590", None),
        ("/api/bgw-pt/v3/lines/de:09274:3590", None),
        (
            "/api/bgw-pt/v3/departures",
            {
                "globalId": "de:09274:3590",
                "limit": "100",
                "transportTypes": "UBAHN,TRAM,SBAHN,BUS,REGIONAL_BUS,BAHN",
            },
        ),
    ]


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
    client = MunichTransportClient(transport, direction_dataset=NO_TIMETABLE)

    options = await client.station_direction_options_by_abbreviation("BP")

    assert options[0].id == "SUBWAY:U3:R"
    assert transport.calls == [
        ("/.rest/aushang/stations", {"id": "BP"}),
    ]


async def test_routes_formats_datetime_as_utc_browser_parameter() -> None:
    transport = FakeTransport([])
    client = MunichTransportClient(transport, direction_dataset=NO_TIMETABLE)

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


async def test_direction_options_for_station_uses_catalog_without_lookup() -> None:
    transport = FakeTransport(
        (
            [
                {
                    "uri": "https://www.mvg.de/aushangfahrplan/U3_R_BP_51.pdf",
                    "scheduleKind": "SUBWAY",
                    "scheduleName": "U3",
                    "direction": "Moosach Bf, gültig ab 14.12.2025",
                },
            ],
            [{"label": "U3", "transportType": "UBAHN"}],
        )
    )
    client = MunichTransportClient(transport, direction_dataset=NO_TIMETABLE)
    station = Station(
        global_id="de:09162:410",
        name="Bonner Platz",
        place="München",
        latitude=48.16,
        longitude=11.58,
        abbreviation="BP",
    )

    options = await client.direction_options_for_station(station)

    assert [option.id for option in options] == ["SUBWAY:U3:R"]
    assert transport.calls == [
        ("/.rest/aushang/stations", {"id": "BP"}),
        ("/api/bgw-pt/v3/lines/de:09162:410", None),
    ]


async def test_direction_options_for_station_falls_back_to_departures() -> None:
    transport = FakeTransport(
        (
            [],
            [
                {
                    "plannedDepartureTime": 1779275760000,
                    "realtime": True,
                    "delayInMinutes": 0,
                    "realtimeDepartureTime": 1779275760000,
                    "transportType": "REGIONAL_BUS",
                    "label": "534",
                    "divaId": "12534",
                    "network": "mvv",
                    "destination": "Pfarrkofen (Ergolding)",
                    "cancelled": False,
                    "messages": [],
                    "infos": [],
                    "lineId": "mvv:12534: :H:j26",
                },
            ],
            *NO_SAMPLED_DEPARTURES,
        )
    )
    client = MunichTransportClient(transport, direction_dataset=NO_TIMETABLE)
    station = Station(
        global_id="de:09274:3590",
        name="Oberglaim",
        place="Ergolding",
        latitude=48.58,
        longitude=12.15,
    )

    options = await client.direction_options_for_station(station)

    assert [option.id for option in options] == ["REGIONAL_BUS:534:H"]
    assert [path for path, _ in transport.calls] == [
        "/api/bgw-pt/v3/lines/de:09274:3590",
        *["/api/bgw-pt/v3/departures"] * len(DIRECTION_SAMPLE_OFFSETS_MINUTES),
    ]


async def test_direction_options_for_station_adds_lines_missing_from_catalog() -> None:
    transport = FakeTransport(
        (
            [
                {
                    "uri": "https://www.mvg.de/aushangfahrplan/16_H_HAC_1.pdf",
                    "scheduleKind": "TRAM",
                    "scheduleName": "16",
                    "direction": "Effnerplatz",
                },
            ],
            [
                {"label": "16", "transportType": "TRAM"},
                {"label": "S7", "transportType": "SBAHN"},
                {"label": "S8", "transportType": "SBAHN"},
            ],
            [
                _departure_payload("S8", "R", "Pasing"),
                _departure_payload("S8", "H", "Flughafen München"),
            ],
            [_departure_payload("S8", "R", "Herrsching", minutes=180)],
            [_departure_payload("S8", "R", "Herrsching", minutes=360)],
            *([],) * (len(DIRECTION_SAMPLE_OFFSETS_MINUTES) - 3),
        )
    )
    client = MunichTransportClient(transport, direction_dataset=NO_TIMETABLE)
    station = Station(
        global_id="de:09162:7",
        name="Hackerbrücke",
        place="München",
        latitude=48.14,
        longitude=11.55,
        abbreviation="HAC",
    )

    options = await client.direction_options_for_station(station)

    assert [option.id for option in options] == [
        "TRAM:16:H",
        "SBAHN:S8:H",
        "SBAHN:S8:R",
        "SBAHN:S7:",
    ]
    assert options[2].directions == ("Herrsching", "Pasing")
    assert [params for path, params in transport.calls[2:]] == [
        {
            "globalId": "de:09162:7",
            "limit": "100",
            "transportTypes": "SBAHN",
            **({"offsetInMinutes": str(offset)} if offset else {}),
        }
        for offset in DIRECTION_SAMPLE_OFFSETS_MINUTES
    ]


async def test_direction_options_for_station_samples_each_transport_type() -> None:
    samples = len(DIRECTION_SAMPLE_OFFSETS_MINUTES)
    transport = FakeTransport(
        (
            [],
            [
                {"label": "S1", "transportType": "SBAHN"},
                {"label": "RE4", "transportType": "BAHN"},
                {"label": "S2", "transportType": "SBAHN"},
            ],
            *([],) * (2 * samples),
        )
    )
    client = MunichTransportClient(transport, direction_dataset=NO_TIMETABLE)
    station = Station(
        global_id="de:09162:5",
        name="Ostbahnhof",
        place="München",
        latitude=48.13,
        longitude=11.6,
        abbreviation="OB",
    )

    options = await client.direction_options_for_station(station)

    assert [option.id for option in options] == [
        "SBAHN:S1:",
        "BAHN:RE4:",
        "SBAHN:S2:",
    ]
    assert [
        params and params["transportTypes"] for _, params in transport.calls[2:]
    ] == (["SBAHN"] * samples + ["BAHN"] * samples)


async def test_direction_options_for_station_ignores_replacement_services() -> None:
    samples = len(DIRECTION_SAMPLE_OFFSETS_MINUTES)
    transport = FakeTransport(
        (
            [
                {"label": "S2", "transportType": "SBAHN"},
                {"label": "SEV S2", "transportType": "BUS", "sev": True},
                {"label": "S8", "transportType": "SBAHN"},
            ],
            [
                _departure_payload("S2", "R", "Petershausen"),
                _departure_payload(
                    "S2", "R", "Erding", transport_type="BUS", replacement_service=True
                ),
                _departure_payload(
                    "S8",
                    "H",
                    "Flughafen München",
                    transport_type="BUS",
                    replacement_service=True,
                ),
            ],
            *([],) * (samples - 1),
        )
    )
    client = MunichTransportClient(transport, direction_dataset=NO_TIMETABLE)
    station = Station(
        global_id="de:09162:1460",
        name="Markt Schwaben",
        place="Markt Schwaben",
        latitude=48.19,
        longitude=11.87,
    )

    options = await client.direction_options_for_station(station)

    assert [(option.id, option.directions) for option in options] == [
        ("SBAHN:S2:R", ("Petershausen",)),
        ("SBAHN:S8:", ()),
    ]
    assert {
        params and params["transportTypes"] for _, params in transport.calls[1:]
    } == {"SBAHN"}


def _departure_payload(
    label: str,
    direction_key: str,
    destination: str,
    *,
    transport_type: str = "SBAHN",
    replacement_service: bool = False,
    minutes: int = 0,
) -> JsonValue:
    timestamp = 1792683240000 + minutes * 60_000
    return {
        "plannedDepartureTime": timestamp,
        "realtime": True,
        "realtimeDepartureTime": timestamp,
        "transportType": transport_type,
        "label": label,
        "destination": destination,
        "cancelled": False,
        "sev": replacement_service,
        "lineId": f"ddb:920{label}: :{direction_key}:j26",
    }


async def test_direction_options_for_station_adds_timetable_directions() -> None:
    transport = FakeTransport(
        (
            [
                {
                    "uri": "https://www.mvg.de/aushangfahrplan/27_R_KA_1.pdf",
                    "scheduleKind": "TRAM",
                    "scheduleName": "27",
                    "direction": "Petuelring",
                },
                {
                    "uri": "https://www.mvg.de/aushangfahrplan/28_R_KA_1.pdf",
                    "scheduleKind": "TRAM",
                    "scheduleName": "28",
                    "direction": "Scheidplatz",
                },
            ],
            [
                {"label": "27", "transportType": "TRAM"},
                {"label": "28", "transportType": "TRAM"},
                {"label": "RE9", "transportType": "BAHN"},
            ],
        )
    )
    timetable = DirectionDataset(
        feed_version="test",
        valid_until=None,
        stations={
            "de:09162:1": [
                ["27", "TRAM", "R", "Petuelring"],
                ["28", "TRAM", "H", "Sendlinger Tor"],
                ["28", "TRAM", "R", "Scheidplatz"],
                ["RE 9", "BAHN", "R", "Ulm Hbf"],
            ],
        },
    )
    client = MunichTransportClient(transport, direction_dataset=timetable)
    station = Station(
        global_id="de:09162:1",
        name="Karlsplatz (Stachus)",
        place="München",
        latitude=48.14,
        longitude=11.57,
        abbreviation="KA",
    )

    options = await client.direction_options_for_station(station)

    # The catalog names its directions; the timetable adds the ones it lacks.
    assert [(option.id, option.directions) for option in options] == [
        ("TRAM:27:R", ("Petuelring",)),
        ("TRAM:28:R", ("Scheidplatz",)),
        ("TRAM:28:H", ("Sendlinger Tor",)),
        ("BAHN:RE 9:R", ("Ulm Hbf",)),
    ]
    # Every line is known, so no departures are sampled.
    assert len(transport.calls) == 2


async def test_direction_options_for_station_keeps_catalog_transport_type() -> None:
    transport = FakeTransport(
        (
            [
                {
                    "uri": "https://www.mvg.de/aushangfahrplan/N79_H_HHS_1.pdf",
                    "scheduleKind": "NIGHT_LINE",
                    "scheduleName": "N79",
                    "direction": "Haar / Ludwig-Moser-Str.",
                },
            ],
            [{"label": "N79", "transportType": "BUS"}],
        )
    )
    timetable = DirectionDataset(
        feed_version="test",
        valid_until=None,
        stations={
            "de:09162:1": [
                ["N79", "BUS", "H", "Haar, Ludwig-Moser-Straße"],
                ["N79", "BUS", "R", "Neuperlach Süd"],
            ],
        },
    )
    client = MunichTransportClient(transport, direction_dataset=timetable)
    station = Station(
        global_id="de:09162:1",
        name="Hochäckerstraße",
        place="München",
        latitude=48.1,
        longitude=11.65,
        abbreviation="HHS",
    )

    options = await client.direction_options_for_station(station)

    # The timetable has no night lines, so its direction joins the catalog's.
    assert [(option.id, option.schedule_kind) for option in options] == [
        ("NIGHT_LINE:N79:H", "NIGHT_LINE"),
        ("NIGHT_LINE:N79:R", "NIGHT_LINE"),
    ]


async def test_direction_options_for_station_offers_each_branch() -> None:
    transport = FakeTransport(([{"label": "S1", "transportType": "SBAHN"}],))
    timetable = DirectionDataset(
        feed_version="test",
        valid_until=None,
        stations={
            "de:09178:2660": [
                ["S1", "SBAHN", "H", "Leuchtenbergring"],
                ["S1", "SBAHN", "R", "Flughafen München", ["Flughafen München"]],
                ["S1", "SBAHN", "R", "Freising", ["Freising"]],
            ],
        },
    )
    client = MunichTransportClient(transport, direction_dataset=timetable)
    station = Station(
        global_id="de:09178:2660",
        name="Neufahrn",
        place="Neufahrn",
        latitude=48.32,
        longitude=11.66,
    )

    options = await client.direction_options_for_station(station)

    assert [
        (option.id, option.directions, option.excluded_destinations)
        for option in options
    ] == [
        ("SBAHN:S1:H", ("Leuchtenbergring",), ()),
        (
            "SBAHN:S1:R:Flughafen München",
            ("Flughafen München",),
            ("Freising",),
        ),
        ("SBAHN:S1:R:Freising", ("Freising",), ("Flughafen München",)),
    ]


async def test_bundled_timetable_has_s_bahn_branches() -> None:
    client = MunichTransportClient(
        FakeTransport(([],)),
    )
    station = Station(
        global_id="de:09174:6800",
        name="Dachau Bahnhof",
        place="Dachau",
        latitude=48.25,
        longitude=11.43,
    )

    options = await client.direction_options_for_station(station)

    assert {
        option.id: option.excluded_destinations
        for option in options
        if option.line_label == "S2"
    } == {
        "SBAHN:S2:H": (),
        "SBAHN:S2:R:Altomünster": ("Petershausen",),
        "SBAHN:S2:R:Petershausen": ("Altomünster",),
    }


async def test_bundled_timetable_has_directions_sharing_a_poster() -> None:
    # Prinz-Eugen-Park's 17 poster is headed "16/17 St. Emmeram", so the
    # catalog has no 16 towards St. Emmeram.
    transport = FakeTransport(
        (
            [
                {
                    "uri": "https://www.mvg.de/aushangfahrplan/16_R_PEP_4.pdf",
                    "scheduleKind": "TRAM",
                    "scheduleName": "16",
                    "direction": "Romanplatz",
                },
                {
                    "uri": "https://www.mvg.de/aushangfahrplan/17_H_PEP_3.pdf",
                    "scheduleKind": "TRAM",
                    "scheduleName": "17",
                    "direction": "St. Emmeram",
                },
                {
                    "uri": "https://www.mvg.de/aushangfahrplan/17_R_PEP_4.pdf",
                    "scheduleKind": "TRAM",
                    "scheduleName": "17",
                    "direction": "Amalienburgstraße",
                },
            ],
            [
                {"label": "16", "transportType": "TRAM"},
                {"label": "17", "transportType": "TRAM"},
            ],
        )
    )
    client = MunichTransportClient(transport)
    station = Station(
        global_id="de:09162:632",
        name="Prinz-Eugen-Park",
        place="München",
        latitude=48.16,
        longitude=11.63,
        abbreviation="PEP",
    )

    options = await client.direction_options_for_station(station)

    assert {
        option.id: option.directions
        for option in options
        if option.schedule_kind == "TRAM"
    } == {
        "TRAM:16:H": ("St. Emmeram",),
        "TRAM:16:R": ("Romanplatz",),
        "TRAM:17:H": ("St. Emmeram",),
        "TRAM:17:R": ("Amalienburgstraße",),
    }
