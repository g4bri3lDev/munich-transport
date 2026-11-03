# Munich Transport

Async Python client for Munich public transport data.

This package is intentionally independent from Home Assistant. A Home Assistant
integration can later use it as a thin adapter.

This project is not affiliated with, endorsed by, or sponsored by MVG, MVV, or
Stadtwerke München.

## Endpoint Source

The endpoint shapes in this package are based on network traffic captured from
the official MVG website with Chrome DevTools MCP. External client
implementations and the legacy integration are not used as references.

See [docs/endpoint-discovery.md](docs/endpoint-discovery.md) for the captured
browser calls and
[docs/home-assistant-request-strategy.md](docs/home-assistant-request-strategy.md)
for Home Assistant request sharing and backoff guidance.

## Station Schedule Catalog

`MunichTransportClient.station_schedules(global_id)` returns the station
timetable PDF entries shown on the MVG station page's "Infos" tab. These
entries include MVG line/direction variants and temporary validity text, such
as construction termini.

The station schedule catalog is separate from live departures. Use it for
stable user-selectable line/direction options, and use `departures()` for
current realtime results. MVG does not expose every operator through this
catalog; for example, S-Bahn lines can appear in `lines()` and `departures()`
without appearing in `station_schedules()`. See
[Bundled Timetable](#bundled-timetable) for how options cover them.

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
rich user-selectable line/direction groups:

```python
groups = await client.station_direction_groups("de:09162:410")
for group in groups:
    print(group.line_label, group.direction_key, group.directions)
```

For integration config flows, `station_direction_options()` returns a compact
shape with a stable `id` and cleaned direction strings. It intentionally does
not format UI text; adapters such as Home Assistant should localize and render
labels themselves.

```python
options = await client.station_direction_options("de:09162:410")
for option in options:
    label = f"{option.line_label} -> {' / '.join(option.directions)}"
    print(option.id, label)
```

For Bonner Platz this produces two U3 options:

```text
SUBWAY:U3:H  U3 -> Fürstenried West / Sendlinger Tor / Fürstenried West
SUBWAY:U3:R  U3 -> Moosach Bf / Implerstraße / Moosach Bf
```

`direction_options_for_station()` adds what the catalog misses from a
timetable bundled with the library: lines it does not list, such as the
S-Bahn and regional trains, and directions of its lines it lacks. The
timetable names each direction after the end station the line goes to, which
is the outermost end station that at least a tenth of the trips through the
station reach. Trains that split further down the line are named after both
halves:

```text
SBAHN:S1:H  S1 -> Leuchtenbergring
SBAHN:S1:R  S1 -> Flughafen München / Freising
```

Where the halves part, each branch is an option of its own. Its id adds the
branch's name, and it leaves out departures to the other branch's end
stations, so at Neufahrn a train to Freising is not the next train to the
airport. Departures to any other destination, such as trips cut short by
construction, count for every branch:

```text
SBAHN:S1:R:Flughafen München  S1 -> Flughafen München
SBAHN:S1:R:Freising           S1 -> Freising
```

Lines in neither, such as replacement buses or lines missing from the
timetable, get options from live departures sampled every three hours across
a day. These options group by direction key too and list the sampled
destinations most frequent first. A line without a sampled departure, such as
one that only runs on some days, gets a single option without a direction
key, like `SBAHN:S7:`, which matches every departure of the line.

Sampling takes a few dozen requests, so store the selected options with
`to_dict()` and restore them with `StationDirectionOption.from_dict()` instead
of looking them up again. The id alone is not enough for that:
`StationDirectionOption.from_id()` has no direction names, matches every
branch, and reads the id's third part as a direction key, which is a
destination for options built from departures without one.

### Bundled Timetable

`scripts/build_directions.py` builds `src/munich_transport/data/directions.json.gz`
from MVV's GTFS feed ("Gesamt-Soll-Fahrplandaten"):

```bash
curl -O https://www.mvv-muenchen.de/fileadmin/mediapool/developer/opendata/gesamt_gtfs.zip
uv run python scripts/build_directions.py gesamt_gtfs.zip
```

The client loads it in an executor on first use. Pass `direction_dataset` to
`MunichTransportClient` to use other data, such as an empty
`DirectionDataset` in tests.

Timetable data: Münchner Verkehrs- und Tarifverbund GmbH (MVV), licensed under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

If the integration already has a station abbreviation from `Station.abbreviation`,
it can avoid a station metadata request. This returns catalog options only:

```python
options = await client.station_direction_options_by_abbreviation("BP")
schedules = await client.station_schedules_by_abbreviation("BP")
```

At runtime, fetch live departures and keep those on the selected options.
`select_departures()` matches each departure's line label and direction key
(parsed from the raw MVG `lineId`, also exposed as `Departure.line_id`), drops
cancellations and sorts by realtime departure.

```python
departures = await client.departures("de:09162:410")
matching = select_departures(departures, [options[0]])
```

It also merges the halves of S-Bahn trains that split further down the line.
MVG lists each half as its own departure, so `select_departures()` returns one
departure with both destinations, such as `Flughafen München / Freising`.

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
