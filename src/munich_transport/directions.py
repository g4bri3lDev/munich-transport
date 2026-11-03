"""Line directions from MVV's timetable, bundled with the library.

`scripts/build_directions.py` derives them from MVV's GTFS feed, which covers
every line, including those missing from MVG's schedule catalog such as the
S-Bahn. Data: Münchner Verkehrs- und Tarifverbund GmbH (MVV), CC BY 4.0.
"""

from __future__ import annotations

import gzip
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from functools import cache
from importlib import resources

from .exceptions import ParseError
from .models import StationDirectionOption, normalize_line_label

type _Entry = Sequence[object]


@dataclass(frozen=True, slots=True)
class DirectionDataset:
    """The line directions serving each station, by MVG global id.

    Each entry is a line label, transport type, direction key and name, and
    for a branch of a rail line also the end stations the branch serves.
    """

    feed_version: str
    valid_until: date | None
    stations: Mapping[str, Sequence[_Entry]] = field(default_factory=dict)

    def options(self, global_id: str) -> list[StationDirectionOption]:
        """Return the station's directions as selectable options.

        A branch excludes the end stations of the other branches of its line
        and direction, and its id adds its name to the direction's id.
        """

        entries = [_parse_entry(entry) for entry in self.stations.get(global_id, ())]
        branch_termini: dict[tuple[str, str], set[str]] = {}
        for label, _, key, _, termini in entries:
            branch_termini.setdefault((normalize_line_label(label), key), set()).update(
                termini
            )

        options = []
        for label, transport_type, key, name, termini in entries:
            option_id = f"{transport_type}:{label}:{key}"
            if termini:
                option_id = f"{option_id}:{name}"
            excluded = branch_termini[(normalize_line_label(label), key)] - set(termini)
            options.append(
                StationDirectionOption(
                    id=option_id,
                    schedule_kind=transport_type,
                    line_label=label,
                    direction_key=key,
                    directions=(name,),
                    raw_directions=(name,),
                    schedule_codes=(),
                    excluded_destinations=tuple(sorted(excluded)),
                )
            )
        return options


@cache
def load_direction_dataset() -> DirectionDataset:
    """Return the bundled dataset.

    Reads and parses a file on first use, so async callers should run it in
    an executor.
    """

    data = json.loads(
        gzip.decompress(
            resources.files(__package__)
            .joinpath("data/directions.json.gz")
            .read_bytes()
        )
    )
    end_date = data.get("feed_end_date")
    return DirectionDataset(
        feed_version=data["feed_version"],
        valid_until=(
            datetime.strptime(end_date, "%Y%m%d").date() if end_date else None
        ),
        stations=data["stations"],
    )


def _parse_entry(entry: _Entry) -> tuple[str, str, str, str, tuple[str, ...]]:
    label, transport_type, key, name, *rest = entry
    termini = rest[0] if rest else ()
    if not (
        isinstance(label, str)
        and isinstance(transport_type, str)
        and isinstance(key, str)
        and isinstance(name, str)
        and isinstance(termini, list | tuple)
    ):
        raise ParseError(f"Not a line direction: {entry!r}")
    return label, transport_type, key, name, tuple(str(item) for item in termini)
