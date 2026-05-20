"""Helpers for station schedule catalog grouping."""

from __future__ import annotations

import re
from collections import OrderedDict
from collections.abc import Iterable

from .models import StationDirection, StationDirectionOption, StationSchedule

NON_SERVICE_SCHEDULE_KINDS: frozenset[str] = frozenset(
    {
        "CONTEXT_MAP",
    }
)

_VALIDITY_SUFFIX_RE = re.compile(
    r"(?:,\s*(?:gültig|nicht gültig|nur gültig)\b|"
    r"\s+\((?:gültig|nicht gültig|nur gültig|vom)\b).*$",
)


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
        _build_direction_option(group)
        for group in group_station_schedules(schedules)
    ]


def _build_direction_option(group: StationDirection) -> StationDirectionOption:
    directions = _unique(
        _display_direction(direction) for direction in group.directions
    )
    label = f"{group.line_label} Richtung {' / '.join(directions)}"

    return StationDirectionOption(
        id=_direction_option_id(group),
        label=label,
        schedule_kind=group.schedule_kind,
        line_label=group.line_label,
        direction_key=group.direction_key,
        directions=directions,
        raw_directions=group.directions,
        schedule_codes=group.schedule_codes,
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
    return _VALIDITY_SUFFIX_RE.sub("", direction).strip()


def _unique[T](values: Iterable[T]) -> tuple[T, ...]:
    return tuple(dict.fromkeys(values))
