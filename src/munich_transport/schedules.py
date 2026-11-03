"""Helpers for station schedule catalog grouping."""

from __future__ import annotations

import re
from collections import Counter, OrderedDict
from collections.abc import Iterable
from dataclasses import replace

from .models import (
    Departure,
    Line,
    StationDirection,
    StationDirectionOption,
    StationSchedule,
    normalize_line_label,
)
from .models import (
    # Kept importable from here, where it was defined before.
    direction_names_match as direction_names_match,
)

NON_SERVICE_SCHEDULE_KINDS: frozenset[str] = frozenset(
    {
        "CONTEXT_MAP",
        "STATION_OVERVIEW_MAP",
    }
)

_VALIDITY_SUFFIX_RE = re.compile(
    r"(?:,\s*(?:gültig|nicht gültig|nur gültig)\b|"
    r"\s+\((?:gültig|nicht gültig|nur gültig|vom)\b).*$",
)
_PARENTHETICAL_NOTE_RE = re.compile(r"\s*\([^)]*\)")
_SPLITTING_TRANSPORT_TYPES: frozenset[str] = frozenset({"SBAHN", "BAHN"})


def group_station_schedules(
    schedules: list[StationSchedule],
    *,
    include_non_service: bool = False,
) -> list[StationDirection]:
    """Group MVG schedule rows into selectable line/direction options.

    MVG publishes temporary timetable variants with separate schedule codes.
    The observed station PDF filename convention maps `H` and `I` to one live
    direction and `R` and `S` to the opposite live direction.
    """

    grouped: OrderedDict[
        tuple[str, str, str | None, str | None],
        list[StationSchedule],
    ] = OrderedDict()

    for schedule in schedules:
        if (
            not include_non_service
            and schedule.schedule_kind in NON_SERVICE_SCHEDULE_KINDS
        ):
            continue

        key = (
            schedule.schedule_kind,
            schedule.line_label,
            schedule.direction_key,
            None if schedule.direction_key is not None else schedule.direction,
        )
        grouped.setdefault(key, []).append(schedule)

    return [
        StationDirection(
            schedule_kind=kind,
            line_label=line_label,
            direction_key=direction_key,
            directions=_unique(schedule.direction for schedule in entries),
            schedule_codes=_unique(
                schedule.schedule_code
                for schedule in entries
                if schedule.schedule_code is not None
            ),
            schedules=tuple(entries),
        )
        for (kind, line_label, direction_key, _), entries in grouped.items()
    ]


def build_station_direction_options(
    schedules: list[StationSchedule],
) -> list[StationDirectionOption]:
    """Build compact line/direction options suitable for integration config."""

    return [
        _build_direction_option(group) for group in group_station_schedules(schedules)
    ]


def build_departure_direction_options(
    departures: Iterable[Departure],
) -> list[StationDirectionOption]:
    """Build compact line/direction options from live departure data.

    This is a fallback for stops that do not expose MVG's station schedule
    catalog metadata. When no live direction key exists, destinations are kept
    separate so unrelated directions on the same line do not collapse together.
    Destinations are listed most frequent first, with the halves of split
    trains counted as one destination such as "Flughafen München / Freising".
    """

    grouped: dict[tuple[str, str, str | None, str | None], list[Departure]] = {}
    for departure in merge_split_departures(departures):
        direction_key = departure.direction_key
        destination_key = None if direction_key is not None else departure.destination
        key = (
            departure.line.transport_type,
            normalize_line_label(departure.line.label),
            direction_key,
            destination_key,
        )
        grouped.setdefault(key, []).append(departure)

    return [
        _build_departure_direction_option(
            schedule_kind,
            group_departures[0].line.label,
            direction_key,
            group_departures,
        )
        for (
            schedule_kind,
            _,
            direction_key,
            _,
        ), group_departures in sorted(
            grouped.items(),
            key=lambda item: (
                item[0][0],
                item[0][1],
                item[0][2] or "",
                item[0][3] or "",
            ),
        )
    ]


def build_line_direction_option(line: Line) -> StationDirectionOption:
    """Build one option for every direction of a line.

    Used for lines a station serves that have neither catalog schedules nor
    sampled departures, such as lines that only run on some days.
    """

    return StationDirectionOption(
        id=f"{line.transport_type}:{line.label}:",
        schedule_kind=line.transport_type,
        line_label=line.label,
        direction_key=None,
        directions=(),
        raw_directions=(),
        schedule_codes=(),
    )


def select_departures(
    departures: Iterable[Departure],
    options: Iterable[StationDirectionOption],
    *,
    include_cancelled: bool = False,
) -> list[Departure]:
    """Return departures on any of the given options, soonest first.

    An empty set of options selects every departure. Halves of a train that
    splits further down the line are merged into one departure.
    """

    selected = tuple(options)
    return sorted(
        merge_split_departures(
            departure
            for departure in departures
            if (include_cancelled or not departure.cancelled)
            and (not selected or any(option.matches(departure) for option in selected))
        ),
        key=lambda departure: departure.realtime_departure,
    )


def merge_split_departures(departures: Iterable[Departure]) -> list[Departure]:
    """Merge the halves of trains that split further down the line.

    MVG lists each half as its own departure, with the same line, direction,
    platform and planned time but a different destination. The merged
    departure names both in a stable order, as in "Flughafen München / Freising".
    Only trains with a known platform are merged, since buses and the U-Bahn
    do not split and can leave twice in the same minute.
    """

    merged: dict[object, Departure] = {}
    for departure in departures:
        key: object = (
            (
                normalize_line_label(departure.line.label),
                departure.direction_key,
                departure.platform,
                departure.planned_departure,
                departure.cancelled,
            )
            if _may_split(departure)
            else departure
        )
        first = merged.get(key)
        if first is None:
            merged[key] = departure
        else:
            destinations = {*first.destination.split(" / "), departure.destination}
            merged[key] = replace(first, destination=" / ".join(sorted(destinations)))
    return list(merged.values())


def _may_split(departure: Departure) -> bool:
    return (
        departure.line.transport_type in _SPLITTING_TRANSPORT_TYPES
        and departure.direction_key is not None
        and departure.platform is not None
    )


def _build_direction_option(group: StationDirection) -> StationDirectionOption:
    directions = _unique(
        _display_direction(direction) for direction in group.directions
    )
    # Temporary variants name the construction terminus and the regular one,
    # as in "Sendlinger Tor / Fürstenried West", so the regular terminus is the
    # first direction without one.
    regular = next(
        (direction for direction in directions if "/" not in direction), None
    )
    if regular is not None:
        directions = (regular, *(d for d in directions if d != regular))

    return StationDirectionOption(
        id=_direction_option_id(group),
        schedule_kind=group.schedule_kind,
        line_label=group.line_label,
        direction_key=group.direction_key,
        directions=directions,
        raw_directions=group.directions,
        schedule_codes=group.schedule_codes,
    )


def _build_departure_direction_option(
    schedule_kind: str,
    line_label: str,
    direction_key: str | None,
    departures: list[Departure],
) -> StationDirectionOption:
    directions = tuple(
        destination
        for destination, _ in Counter(
            departure.destination for departure in departures
        ).most_common()
    )
    suffix = direction_key or directions[0]
    return StationDirectionOption(
        id=f"{schedule_kind}:{line_label}:{suffix}",
        schedule_kind=schedule_kind,
        line_label=line_label,
        direction_key=direction_key,
        directions=directions,
        raw_directions=directions,
        schedule_codes=(),
    )


def _direction_option_id(group: StationDirection) -> str:
    if group.direction_key is not None:
        suffix = group.direction_key
    elif group.schedule_codes:
        suffix = ",".join(group.schedule_codes)
    else:
        suffix = group.directions[0]
    return f"{group.schedule_kind}:{group.line_label}:{suffix}"


def _display_direction(direction: str) -> str:
    without_validity = _VALIDITY_SUFFIX_RE.sub("", direction)
    return _PARENTHETICAL_NOTE_RE.sub("", without_validity).strip()


def _unique[T](values: Iterable[T]) -> tuple[T, ...]:
    return tuple(dict.fromkeys(values))
