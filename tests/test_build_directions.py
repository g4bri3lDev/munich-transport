from __future__ import annotations

import importlib.util
import sys
import zipfile
from pathlib import Path
from types import ModuleType

SCRIPT = Path(__file__).parent.parent / "scripts" / "build_directions.py"

# Stations as (id, name, latitude, longitude). The S1 runs north from Center
# through Trunk to Junction, where it splits for Airport and, via Village,
# for Town. The RE runs south from Center to Lake, some trips ending at Shore
# on the way and the others skipping it.
STATIONS = (
    ("center", "Center", 48.10, 11.50),
    ("trunk", "Trunk", 48.20, 11.50),
    ("junction", "Junction", 48.30, 11.50),
    ("airport", "Airport", 48.32, 11.70),
    ("village", "Village", 48.35, 11.48),
    ("town", "Town", 48.40, 11.45),
    ("shore", "Shore", 48.00, 11.50),
    ("lake", "Lake", 47.80, 11.50),
)


def test_names_directions_after_where_the_line_goes(tmp_path: Path) -> None:
    stations = _build(tmp_path)

    assert stations["center"] == [
        ["RE 6", "BAHN", "H", "Lake"],
        ["S1", "SBAHN", "R", "Airport / Town"],
    ]
    assert stations["trunk"] == [["S1", "SBAHN", "R", "Airport / Town"]]
    assert stations["village"] == [["S1", "SBAHN", "R", "Town"]]


def test_offers_each_branch_where_trains_part(tmp_path: Path) -> None:
    stations = _build(tmp_path)

    assert stations["junction"] == [
        ["S1", "SBAHN", "R", "Airport", ["Airport"]],
        ["S1", "SBAHN", "R", "Town", ["Town"]],
    ]


def test_express_trains_do_not_make_a_branch(tmp_path: Path) -> None:
    stations = _build(tmp_path)

    # Express trips to Lake skip Shore, but Shore lies on the way.
    assert ["RE 6", "BAHN", "H", "Lake"] in stations["center"]
    assert len(stations["center"]) == 2


def _build(tmp_path: Path) -> dict[str, list[list[object]]]:
    feed = tmp_path / "gtfs.zip"
    trips: list[tuple[str, str, list[tuple[str, str]]]] = []
    for hour in range(6, 10):
        # The halves leave Center and Trunk together, and Junction apart.
        trips.append(
            (
                "ddb-92-S1",
                f"s1-R-airport-{hour}",
                [
                    ("center", f"{hour:02}:00:00"),
                    ("trunk", f"{hour:02}:10:00"),
                    ("junction", f"{hour:02}:20:00"),
                    ("airport", f"{hour:02}:30:00"),
                ],
            )
        )
        trips.append(
            (
                "ddb-92-S1",
                f"s1-R-town-{hour}",
                [
                    ("center", f"{hour:02}:00:00"),
                    ("trunk", f"{hour:02}:10:00"),
                    ("junction", f"{hour:02}:22:00"),
                    ("village", f"{hour:02}:30:00"),
                    ("town", f"{hour:02}:40:00"),
                ],
            )
        )
        trips.append(
            (
                "ddb-90-RE6",
                f"re6-H-lake-{hour}",
                [("center", f"{hour:02}:05:00"), ("lake", f"{hour:02}:45:00")],
            )
        )
    trips.append(
        (
            "ddb-90-RE6",
            "re6-H-shore",
            [("center", "11:05:00"), ("shore", "11:20:00")],
        )
    )

    with zipfile.ZipFile(feed, "w") as archive:
        archive.writestr(
            "feed_info.txt",
            "feed_publisher_name,feed_version,feed_end_date\nMVV,1,20261213\n",
        )
        archive.writestr(
            "routes.txt",
            "route_id,route_short_name,route_type\nddb-92-S1,S1,0\nddb-90-RE6,RE 6,2\n",
        )
        archive.writestr(
            "stops.txt",
            "stop_id,stop_name,stop_lat,stop_lon,parent_station\n"
            + "".join(
                f"{stop_id},{name},{latitude},{longitude},\n"
                for stop_id, name, latitude, longitude in STATIONS
            ),
        )
        archive.writestr(
            "trips.txt",
            "route_id,service_id,trip_id\n"
            + "".join(
                f"{route_id},{trip_id}-service,{trip_id}\n"
                for route_id, trip_id, _ in trips
            ),
        )
        archive.writestr(
            "stop_times.txt",
            "trip_id,departure_time,stop_id,stop_sequence\n"
            + "".join(
                f"{trip_id},{time},{stop_id},{sequence}\n"
                for _, trip_id, stops in trips
                for sequence, (stop_id, time) in enumerate(stops, start=1)
            ),
        )

    dataset = _script().build_dataset(feed)
    assert dataset["feed_version"] == "1"
    stations: dict[str, list[list[object]]] = dataset["stations"]
    return stations


def _script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("build_directions", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Dataclasses look their module up while being defined.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
