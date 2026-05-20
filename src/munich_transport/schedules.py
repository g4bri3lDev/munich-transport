"""Helpers for station schedule catalog grouping."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Iterable

from .models import StationDirection, StationSchedule

NON_SERVICE_SCHEDULE_KINDS: frozenset[str] = frozenset(
    {
        "CONTEXT_MAP",
    }
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


def _unique[T](values: Iterable[T]) -> tuple[T, ...]:
    return tuple(dict.fromkeys(values))
