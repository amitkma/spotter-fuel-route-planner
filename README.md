# Spotter Fuel Route Planner

A Django 6.1 API that takes a start and a finish location in the USA and returns:

- the driving route, as GeoJSON plus a link to an interactive map,
- the most cost-effective fuel stops along it, for a vehicle with a **500 mile range**,
- the **total money spent on fuel**, at **10 miles per gallon**,

using the fuel prices in `data/fuel-prices-for-be-assessment.csv`.

**Speed and API usage:** a new route makes exactly **one** call to the routing API (OSRM,
free, no key) and takes about 1–1.5 s, nearly all of it spent waiting for OSRM. A repeat
of the same route is served from cache in about **50 ms** with **zero** external calls.
Start and finish given as `City, ST` or `lat,lng` are geocoded offline.

<!-- markdownlint-disable MD013 -->

| Trip (default settings) | Distance | Stops | Fuel cost |
| --- | --- | --- | --- |
| New York, NY → Los Angeles, CA | 2,810 mi | 7 | $860.04 |
| Seattle, WA → Miami, FL | 3,303 mi | 9 | $1,033.92 |
| Chicago, IL → Houston, TX | 1,083 mi | 3 | $319.79 |

<!-- markdownlint-enable MD013 -->

## Quick start

Requires Python 3.13+.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements/development.txt
make setup          # migrate + load places and fuel stations (fully offline, ~4 s)
make run            # http://localhost:8000
```

Or with Docker: `docker compose up --build`. It runs gunicorn, with Redis as the shared
route cache.

| URL | What |
| --- | --- |
| `GET/POST /api/v1/trips/plan/` | The API |
| `/trips/map/?start=…&finish=…` | Interactive map (Leaflet + OpenStreetMap) |
| `/api/docs/` | Swagger UI (OpenAPI schema at `/api/schema/`) |
| `/api/status/` | Health check |

A Postman collection with ready-made requests is in `docs/postman_collection.json`.

## API

```http
GET /api/v1/trips/plan/?start=New York, NY&finish=Los Angeles, CA
POST /api/v1/trips/plan/   {"start": "Chicago, IL", "finish": "Houston, TX"}
```

| Field | Required | Description |
| --- | --- | --- |
| `start`, `finish` | yes | `City, ST` / `City, State` / `City ST`, or `lat,lng`. Other free-text addresses fall back to Nominatim. |
| `stop_penalty` | no | USD the optimiser charges per stop (default `5`). `0` returns the absolute cheapest plan. See below. |

Response (shortened):

```jsonc
{
  "start":  {"query": "New York, NY", "name": "New York, NY", "lat": 40.66271, "lng": -73.93868, "resolved_by": "gazetteer"},
  "finish": {"query": "Los Angeles, CA", "name": "Los Angeles, CA", "lat": 34.01939, "lng": -118.41083, "resolved_by": "gazetteer"},
  "route":  {"distance_miles": 2810.4, "duration_hours": 50.31},
  "fuel": {
    "vehicle_range_miles": 500.0, "miles_per_gallon": 10.0,
    "total_gallons": 281.0, "total_cost": 860.04, "average_price_per_gallon": 3.061,
    "stations_on_route": 459, "stop_penalty": 5.0,
    "stops": [
      {"sequence": 1, "opis_id": 52322, "name": "BOLLA MARKET", "address": "I-95, EXIT 13",
       "city": "Elizabeth", "state": "NJ", "lat": 40.66637, "lng": -74.1935, "price_per_gallon": 3.099,
       "route_mile": 15.1, "off_route_miles": 5.6, "gallons": 39.6, "cost": 122.72},
      "… 6 more stops"
    ]
  },
  "map": {
    "url": "http://localhost:8000/trips/map/?start=New+York%2C+NY&finish=Los+Angeles%2C+CA",
    "geojson": {"type": "FeatureCollection", "features": ["route LineString", "start", "finish", "one Point per stop"]}
  },
  "assumptions": ["…"],
  "meta": {"external_api_calls": {"osrm": 1}, "route_cache_hit": false, "took_ms": 1486.5}
}
```

`map.geojson` can be pasted into [geojson.io](https://geojson.io) or loaded by any map
library. `meta.external_api_calls` shows exactly which third-party calls a request made.

Errors use one format (`drf-standardized-errors`):

| Status | When |
| --- | --- |
| 400 | Missing or invalid input, unknown location, or a location outside the USA |
| 422 | No drivable route, or a stretch of road longer than 500 miles with no station |
| 502 | The routing or geocoding provider is down |

## How it works

```text
 start, finish
      │  resolve_location()   offline gazetteer (48k US places) ── no API call
      ▼
 get_route()                  OSRM /route (1 call), cached 24 h by rounded coordinates
      │
      ▼  densify the polyline to 0.25 mi, KD-tree on 3D unit vectors
 StationIndex.along_route()   stations ≤ 10 mi from the road, with their mile marker
      │
      ▼
 plan_fuel_stops()            exact DP over (station, fuel level), vectorised in numpy
      │
      ▼
 TripPlanSerializer           stops, totals, GeoJSON, map link
```

### Data: geocoding 6,626 stations without an API

The price list has an address and city for each station but **no coordinates**. Geocoding
~6.6k stations online would be slow and would break Nominatim's usage policy, so the import
does it offline:

1. `scripts/build_places_dataset.py` builds `data/us_places.csv.gz` (670 KB, 48k places)
   from the public-domain **US Census Bureau Gazetteer**: incorporated places, CDPs and
   county subdivisions.
2. `import_fuel_stations` keeps US rows only (620 Canadian rows are skipped). It removes
   duplicate OPIS IDs, keeping the cheapest row, and places each station at its city's
   centroid. Names are normalised so that `St. Louis`, `Saint Louis` and `ST LOUIS` match.
3. The 182 small towns that aren't in the gazetteer were geocoded once with Nominatim (rate
   limited). The results are committed in `data/geocoded_cities.json`, so a fresh import is
   100% offline and every one of the 6,626 US stations has coordinates.

Truck stops are at highway exits, so a city centroid is close enough to decide whether a
stop is on the route (default corridor: 10 miles).

### Speed

- Stations live in memory as numpy arrays, loaded once per process. Matching them to a
  coast-to-coast route is a single vectorised KD-tree query (a few ms), not a DB query.
- The optimiser plans a 3,000-mile route in about 3 ms.
- Routes are cached (Redis when `REDIS_URL` is set, in-process otherwise), so the API and
  the map page can share one routing call.
- The geometry returned to clients is simplified (Ramer–Douglas–Peucker), about 2.6k points
  coast to coast instead of tens of thousands. Matching uses the full geometry.

### The optimiser

Given the stations along the route (mile marker, price), `plan_fuel_stops` finds the plan
with the lowest **fuel cost + `stop_penalty` × stops**. It's a dynamic program over
(station, fuel left) with fuel in 1-mile units. A prefix-minimum trick makes each station a
few numpy vector operations ([optimizer.py](spotter/features/trip/optimizer.py) has the
recurrence). Tests check it against a brute-force solver on random routes.

Why a stop penalty: the strictly cheapest plan for New York → Los Angeles has **23 stops**,
several of them buying 1 gallon to save a few cents ($852.35). A $5 penalty brings that
down to 7 stops for $860.04 (+$7.69, +0.9%). That's a plan a driver would actually follow. The penalty only
steers the optimisation and is never added to the reported cost. Pass `stop_penalty=0` to
get the absolute cheapest plan.

### Assumptions

- 500 mile range on a full tank, 10 mpg. Both are settings (`VEHICLE_RANGE_MILES`,
  `VEHICLE_MPG`).
- The trip **starts with an empty tank**, so the total covers every mile driven (total
  gallons = distance ÷ 10). The vehicle leaves on a 25-mile reserve so it can pick a good
  station near the start instead of being forced into the first one. That reserve is billed
  at the first stop's price.
- The plan arrives at the destination with an empty tank.
- Detours from the highway to a station aren't added to the distance.

## Project structure

The code is organised by feature (`apis` / `services` / `selectors` / `serializers` per
feature app), with third-party providers isolated in `integrations/` behind an interface:

```text
config/                      settings split into base / development / production / test
  settings/components/       drf, cache, logging, routing (vehicle + providers), spectacular
spotter/
  core/                      BaseModel, exceptions, geo maths (numpy), types
  features/
    places/                  offline US gazetteer: model, import command, location resolution
    fuelstation/             stations: model, CSV import + geocoding, in-memory spatial index
    trip/                    API, map view, trip service, fuel-stop optimiser
integrations/
  routing/                   RoutingProvider interface + OSRM implementation
  geocoding/nominatim/       Nominatim client (fallback only)
data/                        price list, bundled gazetteer, committed geocoding cache
templates/trip/map.html      Leaflet map page
scripts/                     rebuilds the gazetteer from Census files
```

Swapping the routing provider (for example to a self-hosted OSRM, Valhalla or GraphHopper)
means one class implementing `RoutingProvider.get_route()` and the `ROUTING_PROVIDER`
setting.

## Development

```bash
make run-tests      # tests + coverage report
make lint           # ruff, isort, mypy
pre-commit install  # same checks on commit
```

All settings are environment variables; see `.env.example`.
