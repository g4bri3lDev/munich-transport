# Endpoint Discovery

Captured from `https://www.mvg.de/verbindungen.html` and station pages using
Chrome DevTools MCP on 2026-05-20.

## Official MVG Browser Calls Observed

- `GET /api/bgw-pt/v3/locations?query=Marienplatz`
- `GET /api/bgw-pt/v3/stations/nearby?latitude=...&longitude=...`
- `GET /api/bgw-pt/v3/departures?globalId=de:09162:2&limit=100&transportTypes=UBAHN,TRAM,SBAHN,BUS,REGIONAL_BUS,BAHN`
- `GET /api/bgw-pt/v3/routes?originStationGlobalId=de:09162:2&destinationStationGlobalId=de:09162:6&routingDateTime=2026-05-20T11:19:37.296Z&routingDateTimeIsArrival=false&transportTypes=SCHIFF,UBAHN,TRAM,SBAHN,BUS,REGIONAL_BUS,BAHN&changeSpeed=NORMAL&routeType=LEAST_TIME`
- `GET /api/bgw-pt/v3/lines/de:09162:2`
- `GET /api/bgw-pt/v3/messages`
- `GET /.rest/zdm/stations/de:09162:2`

The production client uses only JSON transport-data endpoints. Map tiles,
analytics, web component bundles, images, and station marketing content are out
of scope.
