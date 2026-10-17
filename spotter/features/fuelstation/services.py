"""Importing + geocoding the OPIS price list."""

# Standard library imports
import csv
import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

# Django imports
from django.db import transaction

# Spotter imports
from integrations.geocoding.nominatim.client import NominatimGeocoder
from spotter.core.exceptions import ExternalAPIException
from spotter.features.fuelstation.models import FuelStation
from spotter.features.fuelstation.selectors import reset_station_index
from spotter.features.places.models import Place
from spotter.features.places.selectors import reset_place_index
from spotter.features.places.utils import US_STATES, normalize_place_name

logger = logging.getLogger(__name__)

# Nominatim policy: max 1 req/s
NOMINATIM_MIN_INTERVAL_SECONDS = 1.1


@dataclass
class ImportReport:
    """Summary of a fuel station import."""

    rows: int = 0
    skipped_non_us: int = 0
    skipped_invalid: int = 0
    duplicates: int = 0
    stations: int = 0
    geocoded: int = 0
    geocoded_online: int = 0
    not_geocoded: int = 0


def read_price_list(path: Path, report: ImportReport) -> dict[int, dict[str, str]]:
    """Read the OPIS CSV, US rows only, cheapest row per OPIS ID.

    Some stops appear twice under different names (e.g. "PILOT #1243" and "PILOT TRAVEL
    CENTER #1243"), hence the dedupe.
    """
    stations: dict[int, dict[str, str]] = {}
    with path.open(newline="", encoding="utf-8-sig") as fh:
        for raw in csv.DictReader(fh):
            report.rows += 1
            row = {k.strip(): (v or "").strip() for k, v in raw.items()}
            if row["State"] not in US_STATES:
                report.skipped_non_us += 1
                continue
            try:
                opis_id = int(row["OPIS Truckstop ID"])
                price = Decimal(row["Retail Price"])
            except (ValueError, InvalidOperation):
                report.skipped_invalid += 1
                continue
            if price <= 0:
                report.skipped_invalid += 1
                continue
            row["_price"] = str(price)
            existing = stations.get(opis_id)
            if existing is not None:
                report.duplicates += 1
                if Decimal(existing["_price"]) <= price:
                    continue
            stations[opis_id] = row
    return stations


class CityGeocoder:
    """Geocode (city, state): gazetteer first, then Nominatim.

    Nominatim results go into a JSON file that's committed, so imports run offline.
    """

    def __init__(self, cache_file: Path, online: bool, log: Callable[[str], None]) -> None:
        self.places = {
            (key, state): (lat, lng)
            for key, state, lat, lng in Place.objects.exclude(kind=Place.Kind.OVERRIDE).values_list(
                "normalized_name", "state", "lat", "lng"
            )
        }
        self.cache_file = cache_file
        self.cache: dict[str, list[float] | None] = (
            json.loads(cache_file.read_text()) if cache_file.exists() else {}
        )
        self.online = online
        self.log = log
        self._geocoder: NominatimGeocoder | None = None
        self._last_call = 0.0
        self.new_places: dict[tuple[str, str], tuple[str, float, float]] = {}

    def offline(self, city: str, state: str) -> tuple[float, float] | None:
        """Look up a city in the gazetteer."""
        return self.places.get((normalize_place_name(city), state))

    def online_lookup(self, city: str, state: str) -> tuple[float, float] | None:
        """Nominatim lookup, from the cache file if we have it."""
        cache_key = f"{city}|{state}"
        if cache_key in self.cache or not self.online:
            cached = self.cache.get(cache_key)
            if not cached:
                return None
            self.new_places[(normalize_place_name(city), state)] = (city, cached[0], cached[1])
            return (cached[0], cached[1])

        if self._geocoder is None:
            self._geocoder = NominatimGeocoder()
        wait = NOMINATIM_MIN_INTERVAL_SECONDS - (time.monotonic() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.monotonic()
        try:
            result = self._geocoder.search(f"{city}, {US_STATES[state]}")
        except ExternalAPIException as e:
            self.log(f"  ! {city}, {state}: {e}")
            return None  # don't cache failures, retry next run

        self.cache[cache_key] = [result.lat, result.lng] if result else None
        if result:
            self.new_places[(normalize_place_name(city), state)] = (city, result.lat, result.lng)
        self.log(f"  {'+' if result else '-'} {city}, {state}")
        return (result.lat, result.lng) if result else None

    def save(self) -> None:
        """Write the online-geocoding cache to disk."""
        self.cache_file.write_text(json.dumps(dict(sorted(self.cache.items())), indent=1) + "\n")


@transaction.atomic
def import_fuel_stations(
    path: Path,
    geocode_cache_file: Path,
    online_geocoding: bool = True,
    log: Callable[[str], None] = logger.info,
) -> ImportReport:
    """Replace all fuel stations with the contents of the OPIS price list at `path`.

    The CSV has no coordinates, so each station goes at its city's centroid. Truck stops are
    near highway exits anyway, so that's close enough for `STATION_CORRIDOR_MILES`.
    """
    report = ImportReport()
    rows = read_price_list(path, report)
    geocoder = CityGeocoder(geocode_cache_file, online_geocoding, log)

    cities = {(r["City"], r["State"]) for r in rows.values()}
    missing = sorted(c for c in cities if not geocoder.offline(*c))
    if missing:
        log(f"{len(missing)} cities are not in the gazetteer, trying the online cache/geocoder.")
    online_hits = {city: geocoder.online_lookup(*city) for city in missing}
    if online_geocoding:
        geocoder.save()

    stations = []
    for opis_id, row in rows.items():
        key = (row["City"], row["State"])
        coords = geocoder.offline(*key)
        source = FuelStation.GeocodeSource.GAZETTEER
        if key in online_hits:
            coords = online_hits[key]
            source = FuelStation.GeocodeSource.NOMINATIM
        if coords:
            report.geocoded += 1
            report.geocoded_online += source == FuelStation.GeocodeSource.NOMINATIM
        else:
            report.not_geocoded += 1
        stations.append(
            FuelStation(
                opis_id=opis_id,
                name=row["Truckstop Name"],
                address=row["Address"],
                city=row["City"],
                state=row["State"],
                rack_id=int(row["Rack ID"]) if row["Rack ID"].isdigit() else None,
                retail_price=Decimal(row["_price"]),
                lat=coords[0] if coords else None,
                lng=coords[1] if coords else None,
                geocode_source=source if coords else "",
            )
        )

    FuelStation.objects.all().delete()
    FuelStation.objects.bulk_create(stations, batch_size=2000)
    report.stations = len(stations)

    # also add them as places so they can be used as start/finish
    for (normalized, state), (city, lat, lng) in geocoder.new_places.items():
        Place.objects.get_or_create(
            normalized_name=normalized,
            state=state,
            defaults={"name": city, "lat": lat, "lng": lng, "kind": Place.Kind.OVERRIDE},
        )

    transaction.on_commit(reset_station_index)
    transaction.on_commit(reset_place_index)
    return report
