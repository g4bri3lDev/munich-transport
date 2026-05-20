# Home Assistant Request Strategy

The Home Assistant integration should minimize MVG traffic by sharing fetched
data across entities. The Python client stays transport-focused; request
scheduling, caching horizons, disabled entities, and entity lifecycle belong in
the integration.

## Core Model

Fetch live departures once per station refresh, then let each line/direction
entity filter that shared result locally.

```text
Station departure coordinator
  every 30-60 seconds, with jitter:
    GET /api/bgw-pt/v3/departures?globalId=<station>&limit=100

Line/direction entities
  no direct API calls
  filter coordinator data by line label and direction key
```

This avoids one MVG request per selected line/direction pair. A station with
ten configured sensors should still issue one departure request per refresh,
not ten.

## Coordinators

Use one `DataUpdateCoordinator` per station for live departures. Store it in
`hass.data`, keyed by station `global_id`, so multiple config entries or
entities for the same station share one polling loop.

Entities should set `should_poll = False` and read from coordinator data. They
should not call the client directly during entity updates.

Use separate coordinators or caches for slower-moving data:

- station metadata: resolve during setup and persist in config/options
- station schedule catalog: refresh on reload, daily, or by manual service
- global messages: one shared coordinator, refreshed every 5-15 minutes
- line metadata: avoid unless the UI truly needs it

## Direction Selection

Line/direction pairings should come from the station schedule catalog, not from
whatever live departures happen to be running during setup.

Store compact selectors from `station_direction_options()`:

```text
SUBWAY:U3:H
SUBWAY:U3:R
NIGHT_LINE:N40:H
```

At runtime, match live departures against the selected line label and
`direction_key`. Temporary termini are represented by the same direction key as
their normal direction, so existing selections continue to work during
construction schedules.

## Request Coalescing

The integration should collapse in-flight requests. If a station refresh is
already running, any later refresh request for the same station should await the
existing task instead of starting a second HTTP request.

`DataUpdateCoordinator` already provides most of this behavior when all entities
for a station are wired to the same coordinator.

## Backoff

Handle transient failures centrally at the station coordinator level. Do not let
each entity independently retry.

For MVG responses with `429`, `502`, `503`, or `504`:

- honor `Retry-After` when present
- otherwise use exponential backoff with a reasonable cap
- keep the previous successful coordinator data available while the station is
  temporarily unavailable
- log transient failures at a controlled rate

This makes outage behavior visible without multiplying load during an MVG-side
problem.

## Startup Behavior

Avoid setup-time request spikes:

- stagger initial station refreshes with small randomized delays
- do not fetch schedules, messages, lines, and departures for every entity at
  once
- skip live refreshes for disabled entities
- reuse existing station coordinators when adding another selector for the same
  station

## Library Boundary

The library may expose helpers such as stable direction options, parsed
direction keys, retry metadata, and explicit transient-error flags. It should
not decide Home Assistant polling intervals or entity caching policy.

The integration owns the request budget because it knows how many stations,
entities, disabled entities, and config entries exist.
