"""Interface every routing provider must implement."""

# Standard library imports
from abc import ABC, abstractmethod
from dataclasses import dataclass

# Spotter imports
from spotter.core.types import LatLng


@dataclass(frozen=True, slots=True)
class Route:
    """A driving route. `coordinates` is the full geometry as (lat, lng), in order."""

    coordinates: list[tuple[float, float]]
    distance_meters: float
    duration_seconds: float


class RouteNotFoundError(Exception):
    """No drivable route between the two points."""


class RoutingProvider(ABC):
    """Base class for routing providers."""

    #: used in cache keys and in `meta.external_api_calls`
    name: str

    @abstractmethod
    def get_route(self, start: LatLng, finish: LatLng) -> Route:
        """Return the route from `start` to `finish`. Should be a single upstream call.

        Raise RouteNotFoundError if there's no route, ExternalAPIException if the provider fails.
        """
