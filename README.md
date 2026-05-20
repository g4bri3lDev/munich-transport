# Munich Transport

Async Python client for Munich public transport data.

This package is intentionally independent from Home Assistant. A Home Assistant
integration can later use it as a thin adapter.

## Endpoint Source

The endpoint shapes in this package are based on network traffic captured from
the official MVG website with Chrome DevTools MCP. External client
implementations and the legacy integration are not used as references.

## Station Schedule Catalog

`MunichTransportClient.station_schedules(global_id)` returns the station
timetable PDF entries shown on the MVG station page's "Infos" tab. These
entries include MVG line/direction variants and temporary validity text, such
as construction termini.

The station schedule catalog is separate from live departures. Use it for
stable user-selectable line/direction options, and use `departures()` for
current realtime results. MVG does not expose every operator through this
catalog; for example, S-Bahn lines can appear in `lines()` and `departures()`
without appearing in `station_schedules()`.

### Direction Grouping

MVG schedule PDF filenames include a schedule code:

```text
U3_H_BP_52.pdf
U3_I_BP_52.pdf
U3_R_BP_51.pdf
U3_S_BP_51.pdf
```

The library parses this into `StationSchedule.schedule_code`,
`station_abbreviation`, `stop_number`, and `direction_key`. Temporary variants
are normalized so `H` and `I` share direction key `H`, while `R` and `S` share
direction key `R`.

Use `MunichTransportClient.station_direction_groups(global_id)` to build
user-selectable line/direction options:

```python
groups = await client.station_direction_groups("de:09162:410")
for group in groups:
    print(group.line_label, group.direction_key, group.directions)
```

For Bonner Platz this produces two U3 options:

```text
U3 H: Fürstenried West / Sendlinger Tor / Fürstenried West
U3 R: Moosach Bf / Implerstraße / Moosach Bf
```

At runtime, fetch live departures and match the stored selector against
`Departure.line.label` and `Departure.direction_key`. The raw MVG `lineId` is
also exposed as `Departure.line_id`.

```python
selected_line = "U3"
selected_direction_key = "H"

departures = await client.departures("de:09162:410")
matching = [
    departure
    for departure in departures
    if departure.line.label == selected_line
    and departure.direction_key == selected_direction_key
]
```

## Development

```bash
uv sync
uv run pytest
uv run ruff check .
uv run mypy
```

Live endpoint smoke test:

```bash
uv run python scripts/smoke_mvg.py
```

Bounded probe for transient response headers:

```bash
uv run python scripts/probe_retry_after.py --max-attempts 100 --delay 1.0
```
