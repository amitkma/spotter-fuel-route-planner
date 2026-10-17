"""Nominatim (OpenStreetMap) geocoder, only used as a fallback for free-text input.

Usage policy: real User-Agent, max 1 req/s.
https://operations.osmfoundation.org/policies/nominatim/
"""

# Standard library imports
import logging
from dataclasses import dataclass

# Django imports
from django.conf import settings

# Other third-party library imports
import requests

# Spotter imports
from spotter.core.exceptions import ExternalAPIException

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class NominatimResult:
    """A single geocoding match."""

    display_name: str
    lat: float
    lng: float


class NominatimGeocoder:
    """Client for Nominatim `/search`, US only."""

    def __init__(self, base_url: str | None = None, timeout: float | None = None) -> None:
        self.base_url = (base_url or settings.NOMINATIM_BASE_URL).rstrip("/")
        self.timeout = timeout or settings.GEOCODING_TIMEOUT_SECONDS
        self.session = requests.Session()
        self.session.headers["User-Agent"] = settings.NOMINATIM_USER_AGENT

    def search(self, query: str) -> NominatimResult | None:
        """Geocode `query` in the US, or None if there's no match."""
        params: dict[str, str | int] = {
            "q": query,
            "format": "jsonv2",
            "limit": 1,
            "countrycodes": "us",
        }
        try:
            response = self.session.get(
                f"{self.base_url}/search", params=params, timeout=self.timeout
            )
            response.raise_for_status()
            results = response.json()
        except (requests.RequestException, ValueError) as e:
            raise ExternalAPIException(True, f"Nominatim request failed: {e}") from e

        if not results:
            return None
        best = results[0]
        return NominatimResult(
            display_name=best.get("display_name", query),
            lat=float(best["lat"]),
            lng=float(best["lon"]),
        )
