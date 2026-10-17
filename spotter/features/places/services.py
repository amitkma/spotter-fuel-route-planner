"""Turning user input into coordinates."""

# Standard library imports
import logging
from dataclasses import dataclass, field

# Django imports
from django.conf import settings
from django.core.cache import cache
from django.utils.translation import gettext_lazy as _

# Other third-party library imports
from rest_framework.exceptions import ValidationError

# Spotter imports
from integrations.geocoding.nominatim.client import NominatimGeocoder
from spotter.core.exceptions import ExternalAPIException, UpstreamServiceError
from spotter.core.types import LatLng
from spotter.features.places.error_codes import PlacesErrorCode
from spotter.features.places.selectors import get_place, get_place_index
from spotter.features.places.utils import normalize_place_name, parse_location

logger = logging.getLogger(__name__)

# further than this from any US place = not in the US
MAX_DISTANCE_FROM_US_PLACE_MILES = 30.0


@dataclass(frozen=True, slots=True)
class ResolvedLocation:
    """A location resolved to coordinates, plus how it was resolved."""

    query: str
    name: str
    point: LatLng
    source: str  # "coordinates" | "gazetteer" | "nominatim"


@dataclass
class ApiCallCounter:
    """Counts calls made to third-party APIs while serving one request."""

    calls: dict[str, int] = field(default_factory=dict)

    def add(self, service: str) -> None:
        """Record one call to `service`."""
        self.calls[service] = self.calls.get(service, 0) + 1

    @property
    def total(self) -> int:
        """Total number of external calls."""
        return sum(self.calls.values())


def resolve_location(
    query: str, field_name: str, counter: ApiCallCounter | None = None
) -> ResolvedLocation:
    """Resolve `query` to a point in the US.

    Tries coordinates, then the gazetteer ("City, ST"), then Nominatim. Raises ValidationError
    for unknown/non-US locations, UpstreamServiceError if Nominatim is down.
    """
    parsed = parse_location(query)

    if parsed.foreign:
        raise ValidationError(
            {field_name: [_("Location must be within the USA.")]},
            code=PlacesErrorCode.OUTSIDE_USA,
        )
    if parsed.coordinates:
        nearest = get_place_index().nearest(parsed.coordinates)
        if nearest is None or nearest.distance_miles > MAX_DISTANCE_FROM_US_PLACE_MILES:
            raise ValidationError(
                {field_name: [_("Location must be within the USA.")]},
                code=PlacesErrorCode.OUTSIDE_USA,
            )
        name = f"Near {nearest.name}, {nearest.state}"
        return ResolvedLocation(query, name, parsed.coordinates, "coordinates")

    if parsed.city and parsed.state:
        place = get_place(parsed.city, parsed.state)
        if place:
            name = f"{place.name}, {place.state}"
            return ResolvedLocation(query, name, LatLng(place.lat, place.lng), "gazetteer")

    if not settings.GEOCODING_ONLINE_FALLBACK:
        raise ValidationError(
            {field_name: [_("Location not found. Use 'City, ST' or 'lat,lng'.")]},
            code=PlacesErrorCode.NOT_FOUND,
        )
    return _geocode_online(query, field_name, counter)


def _geocode_online(
    query: str, field_name: str, counter: ApiCallCounter | None
) -> ResolvedLocation:
    """Geocode free text with Nominatim, caching hits and misses."""
    cache_key = f"geocode:nominatim:{normalize_place_name(query)}"
    cached = cache.get(cache_key)
    if cached is None:
        try:
            if counter is not None:
                counter.add("nominatim")
            result = NominatimGeocoder().search(query)
        except ExternalAPIException as e:
            logger.warning("Geocoding failed for %r: %s", query, e)
            raise UpstreamServiceError(_("Geocoding service is unavailable.")) from e
        cached = (result.display_name, result.lat, result.lng) if result else ()
        cache.set(cache_key, cached, settings.ROUTE_CACHE_TIMEOUT)

    if not cached:
        raise ValidationError(
            {field_name: [_("Location not found in the USA.")]},
            code=PlacesErrorCode.NOT_FOUND,
        )
    name, lat, lng = cached
    return ResolvedLocation(query, name, LatLng(lat, lng), "nominatim")
