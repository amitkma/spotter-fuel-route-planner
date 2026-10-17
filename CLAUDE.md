# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Django 6.1 + DRF API (Python 3.13+) that plans a US driving route and the cheapest fuel stops
along it (500 mi range, 10 mpg). README.md has the full write-up of design decisions and
assumptions.

## Commands

```bash
pip install -r requirements/development.txt   # .txt files are compiled from requirements/*.in
make setup        # migrate + import_places + import_fuel_stations --offline (no network)
make run          # runserver on :8000 (PORT=... to override)
make run-tests    # full suite with coverage (extra args: make run-tests ARGS=...)
make test foo     # python manage.py test -k foo  (name-pattern filter)
make lint         # ruff check, ruff format --check, isort --check-only, mypy
docker compose up --build   # gunicorn + Redis
```

Single test by dotted path: `python manage.py test spotter.features.trip.tests.test_optimizer`
(or `...test_optimizer.SomeTestCase.test_method`). Tests use Django's runner, not pytest.

Pre-commit also runs `makemigrations --check --dry-run` when a `models.py` changes.

## Architecture

Request flow for `GET/POST /api/v1/trips/plan/` (`spotter/features/trip/services.py:plan_trip`):

1. `places.services.resolve_location` turns `City, ST` / `lat,lng` into a point using the
   offline Census gazetteer (`Place` model, held in an in-memory index). Only other free text
   falls back to Nominatim (`integrations/geocoding/nominatim`), gated by
   `GEOCODING_ONLINE_FALLBACK`.
2. `trip.services.get_route` makes exactly one routing call via the provider named in the
   `ROUTING_PROVIDER` setting (default OSRM), cached in Django's cache (Redis if `REDIS_URL`,
   else locmem) keyed by rounded coordinates. Keeping it to one upstream call per new route is
   a design goal; `ApiCallCounter` tracks calls and they are returned in the response.
3. The polyline is densified to 0.25 mi and `fuelstation.selectors.get_station_index()` (all
   stations as numpy arrays + scipy KD-tree on 3D unit vectors) finds stations within
   `STATION_CORRIDOR_MILES` with their mile marker. No DB query happens per request.
4. `trip.optimizer.plan_fuel_stops` is an exact DP over (station, fuel level in 1-mile units),
   minimising fuel cost + `stop_penalty` × stops. Its tests compare against a brute-force solver.
   The stop penalty steers the optimisation only and is never added to the reported cost.
5. The trip starts empty with a `START_RESERVE_MILES` reserve that is billed at the first stop's
   price, so total gallons = distance / mpg.

`/trips/map/` (`trip/views.py`, `templates/trip/map.html`) renders the same plan on a Leaflet
map, sharing the route cache with the API.

### Layout conventions

- Feature apps live in `spotter/features/<feature>/` with `apis.py` (DRF views), `services.py`
  (write/business logic), `selectors.py` (read queries / in-memory indexes), `serializers.py`,
  `error_codes.py`. Shared code is in `spotter/core/` (base model, exceptions, numpy geo maths,
  `LatLng` type).
- Third-party providers are isolated in `integrations/`. A new routing provider implements
  `integrations.routing.interface.RoutingProvider.get_route()` and is selected via
  `ROUTING_PROVIDER`; providers raise `RouteNotFoundError` or `ExternalAPIException`, which the
  trip service maps to 422 `UnprocessableError` / 502 `UpstreamServiceError`.
- Errors are rendered by `drf_standardized_errors`; unknown `/api...` paths return a JSON 404
  from `spotter/apis.py`, so new API routes must be added before that catch-all in
  `spotter/urls.py`.
- Settings: `config/settings/__init__.py` picks `test.py` automatically when running tests,
  otherwise `development.py` (+ optional `local.py`) or `production.py` from `DJANGO_ENV`.
  Domain settings (vehicle range, mpg, corridor, penalty, providers) are env vars in
  `config/settings/components/routing.py`. Test settings disable the online geocoding fallback.
- The place and station indexes are process-wide singletons. Call `reset_station_index()` /
  `reset_place_index()` after re-importing data; tests should extend the mixin in
  `spotter/tests/base.py`, which clears the cache and both indexes and provides
  `create_place` / `create_station` helpers.

### Data

- `data/fuel-prices-for-be-assessment.csv` is the price list (no coordinates). The
  `import_fuel_stations` command keeps US rows, dedupes by OPIS ID (cheapest wins) and places
  each station at its city centroid from the gazetteer, with misses filled from the committed
  `data/geocoded_cities.json`.
- `data/us_places.csv.gz` is built by `scripts/build_places_dataset.py` (`make build-places`).

## Style

- Line length 100, ruff (incl. pydocstyle pep257, bandit, print ban) + isort with Django as its
  own section. Imports carry section heading comments (`# Standard library imports`,
  `# Django imports`, `# Other third-party library imports`, `# Spotter imports`,
  `# Spotter local imports`); isort adds them, so keep them when editing imports.
- mypy with the django/drf plugins; tests, scripts, migrations and `config/` are excluded.
