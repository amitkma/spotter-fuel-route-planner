"""OSRM routing provider.

Defaults to the public demo server (router.project-osrm.org, no key needed). Set
`OSRM_BASE_URL` to use your own instance.
https://project-osrm.org/docs/v5.24.0/api/#route-service
"""

# Standard library imports
import logging

# Django imports
from django.conf import settings

# Other third-party library imports
import requests

# Spotter imports
from integrations.routing.interface import Route, RouteNotFoundError, RoutingProvider
from spotter.core.exceptions import ExternalAPIException
from spotter.core.types import LatLng

logger = logging.getLogger(__name__)

# OSRM codes for "no route" (bad input), not server errors
NO_ROUTE_CODES = {"NoRoute", "NoSegment"}


class OSRMRoutingProvider(RoutingProvider):
    """Routing provider backed by an OSRM server."""

    name = "osrm"

    def __init__(self, base_url: str | None = None, timeout: float | None = None) -> None:
        self.base_url = (base_url or settings.OSRM_BASE_URL).rstrip("/")
        self.timeout = timeout or settings.ROUTING_TIMEOUT_SECONDS
        self.session = requests.Session()
        self.session.headers["User-Agent"] = settings.NOMINATIM_USER_AGENT

    def get_route(self, start: LatLng, finish: LatLng) -> Route:
        """Fetch the route with full geometry (one request)."""
        url = (
            f"{self.base_url}/route/v1/driving/"
            f"{start.lng:.6f},{start.lat:.6f};{finish.lng:.6f},{finish.lat:.6f}"
        )
        params = {"overview": "full", "geometries": "geojson", "steps": "false"}
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
        except requests.RequestException as e:
            raise ExternalAPIException(True, f"OSRM request failed: {e}") from e

        try:
            payload = response.json()
        except ValueError:
            payload = {}

        code = payload.get("code")
        if code in NO_ROUTE_CODES or (response.status_code == 400 and code):
            raise RouteNotFoundError(payload.get("message") or code)
        if response.status_code != 200 or code != "Ok" or not payload.get("routes"):
            logger.warning("OSRM error status=%s code=%s", response.status_code, code)
            raise ExternalAPIException(
                response.status_code >= 500 or response.status_code == 429,
                f"OSRM returned {response.status_code}: {code}",
            )

        route = payload["routes"][0]
        coordinates = [(lat, lng) for lng, lat in route["geometry"]["coordinates"]]
        return Route(
            coordinates=coordinates,
            distance_meters=float(route["distance"]),
            duration_seconds=float(route["duration"]),
        )
