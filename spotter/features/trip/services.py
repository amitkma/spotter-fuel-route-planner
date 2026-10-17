"""Trip planning."""

# Standard library imports
import logging
import time
from dataclasses import dataclass, field

# Django imports
from django.conf import settings
from django.core.cache import cache
from django.utils.translation import gettext_lazy as _

# Other third-party library imports
import numpy as np
from rest_framework.exceptions import ValidationError

# Spotter imports
from integrations.routing import get_routing_provider
from integrations.routing.interface import Route, RouteNotFoundError
from spotter.core.exceptions import ExternalAPIException, UnprocessableError, UpstreamServiceError
from spotter.core.geo import (
    METERS_PER_MILE,
    cumulative_miles,
    resample_polyline,
    simplify_polyline,
)
from spotter.core.types import LatLng
from spotter.features.fuelstation.selectors import RouteStation, get_station_index
from spotter.features.places.services import ApiCallCounter, ResolvedLocation, resolve_location
from spotter.features.trip.error_codes import TripErrorCode
from spotter.features.trip.optimizer import Candidate, NoFeasiblePlanError, plan_fuel_stops

logger = logging.getLogger(__name__)

# resample the route to this spacing before matching stations
ROUTE_SAMPLE_STEP_MILES = 0.25
# RDP tolerance for the returned geometry, roughly 50 m
RESPONSE_GEOMETRY_TOLERANCE_DEG = 0.0005
# closer than this = same place
MIN_TRIP_MILES = 0.5

ASSUMPTIONS = [
    "Vehicle range is {range:.0f} miles on a full tank and it does {mpg:g} miles per gallon.",
    "The trip starts with an empty tank. The vehicle leaves on a {reserve:g} mile reserve to "
    "reach a good nearby station, and that reserve is billed at the first stop's price, so the "
    "total covers every mile driven.",
    "Stops minimise total fuel cost, with ${penalty:g} counted per stop while optimising so "
    "the plan skips stops that would save only cents (stop_penalty=0 gives the absolute "
    "cheapest plan). The vehicle arrives with an empty tank.",
    "Stations are located at their city's centroid and count as on-route within "
    "{corridor:g} miles of the road. Detours to reach a station are not added to the distance.",
]


@dataclass(frozen=True, slots=True)
class PlannedStop:
    """A fuel stop in the plan."""

    sequence: int
    station: RouteStation
    gallons: float
    cost: float
    fuel_on_arrival_miles: float


@dataclass
class TripPlan:
    """Everything the API returns for a trip."""

    start: ResolvedLocation
    finish: ResolvedLocation
    distance_miles: float
    duration_seconds: float
    geometry: list[tuple[float, float]]  # simplified (lat, lng)
    stops: list[PlannedStop]
    total_gallons: float
    total_cost: float
    range_miles: float
    mpg: float
    corridor_miles: float
    stop_penalty: float
    stations_on_route: int
    route_cache_hit: bool
    external_api_calls: dict[str, int] = field(default_factory=dict)
    took_ms: float = 0.0

    @property
    def assumptions(self) -> list[str]:
        """Assumptions, returned with every plan."""
        values = {
            "range": self.range_miles,
            "mpg": self.mpg,
            "corridor": self.corridor_miles,
            "penalty": self.stop_penalty,
            "reserve": settings.START_RESERVE_MILES,
        }
        return [a.format(**values) for a in ASSUMPTIONS]


def get_route(start: LatLng, finish: LatLng, counter: ApiCallCounter) -> tuple[Route, bool]:
    """Return (route, from_cache). Cache miss = one call to the routing provider."""
    provider = get_routing_provider()
    a, b = start.rounded(), finish.rounded()
    cache_key = f"route:{provider.name}:{a.lat},{a.lng};{b.lat},{b.lng}"
    if (route := cache.get(cache_key)) is not None:
        return route, True

    counter.add(provider.name)
    try:
        route = provider.get_route(start, finish)
    except RouteNotFoundError as e:
        raise UnprocessableError(
            _("No drivable route found between these locations."), code=TripErrorCode.NO_ROUTE
        ) from e
    except ExternalAPIException as e:
        logger.warning("Routing failed: %s", e)
        raise UpstreamServiceError(_("Routing service is unavailable. Please retry.")) from e
    cache.set(cache_key, route, settings.ROUTE_CACHE_TIMEOUT)
    return route, False


def _cheapest_per_mile(stations: list[RouteStation]) -> list[RouteStation]:
    """Drop stations at the same route mile as a cheaper one."""
    best: dict[float, RouteStation] = {}
    for station in stations:
        key = round(station.mile, 2)
        if key not in best or station.station.price < best[key].station.price:
            best[key] = station
    return sorted(best.values(), key=lambda s: s.mile)


def plan_trip(start_query: str, finish_query: str, stop_penalty: float | None = None) -> TripPlan:
    """Plan a trip between two US locations.

    400 for bad locations, 422 for no route / no fuel in range, 502 if a provider is down.
    """
    started = time.perf_counter()
    counter = ApiCallCounter()
    start = resolve_location(start_query, "start", counter)
    finish = resolve_location(finish_query, "finish", counter)

    route, cache_hit = get_route(start.point, finish.point, counter)
    distance_miles = route.distance_meters / METERS_PER_MILE
    if distance_miles < MIN_TRIP_MILES:
        raise ValidationError(
            {"finish": [_("Start and finish are the same place.")]}, code=TripErrorCode.SAME_PLACE
        )

    points = np.asarray(route.coordinates, dtype=float)
    miles = cumulative_miles(points)
    if miles[-1] > 0:
        # scale to the provider's distance so mile markers add up
        miles *= distance_miles / miles[-1]
    dense_points, dense_miles = resample_polyline(points, miles, ROUTE_SAMPLE_STEP_MILES)

    range_miles = settings.VEHICLE_RANGE_MILES
    mpg = settings.VEHICLE_MPG
    corridor = settings.STATION_CORRIDOR_MILES
    if stop_penalty is None:
        stop_penalty = settings.FUEL_STOP_PENALTY_USD
    on_route = get_station_index().along_route(dense_points, dense_miles, corridor)
    candidates = [Candidate(s.mile, s.station.price, s) for s in _cheapest_per_mile(on_route)]

    # Start with a small reserve so the first stop isn't forced to be the nearest station.
    # It gets billed further down.
    first_leg = candidates[0].mile if candidates else 0.0
    reserve = min(max(first_leg, settings.START_RESERVE_MILES), range_miles, distance_miles)
    try:
        plan = plan_fuel_stops(
            candidates,
            distance_miles,
            range_miles,
            mpg,
            start_fuel_miles=reserve,
            stop_penalty=stop_penalty,
        )
    except NoFeasiblePlanError as e:
        raise UnprocessableError(
            _(
                "No fuel station within the vehicle's range between mile {start:.0f} and "
                "mile {end:.0f} of the route."
            ).format(start=e.gap_start_mile, end=e.gap_end_mile),
            code=TripErrorCode.NO_FUEL_IN_RANGE,
        ) from e

    if not candidates:
        raise UnprocessableError(
            _("No fuel station found along this route."), code=TripErrorCode.NO_FUEL_IN_RANGE
        )
    stops = [
        PlannedStop(n, s.candidate.ref, s.gallons, s.cost, s.fuel_on_arrival_miles)
        for n, s in enumerate(plan.stops, start=1)
    ]
    # Charge the reserve at the first stop's price so total gallons = distance / mpg.
    reserve_gallons = reserve / mpg
    if stops:
        first = stops[0]
        gallons = first.gallons + reserve_gallons
        stops[0] = PlannedStop(
            1, first.station, gallons, gallons * first.station.station.price,
            first.fuel_on_arrival_miles,
        )  # fmt: skip
    else:  # short trip, the reserve covers it
        nearest = candidates[0].ref
        stops = [
            PlannedStop(1, nearest, reserve_gallons, reserve_gallons * nearest.station.price, 0)
        ]

    geometry = simplify_polyline(points, RESPONSE_GEOMETRY_TOLERANCE_DEG)
    return TripPlan(
        start=start,
        finish=finish,
        distance_miles=distance_miles,
        duration_seconds=route.duration_seconds,
        geometry=[(float(lat), float(lng)) for lat, lng in geometry],
        stops=stops,
        total_gallons=sum(s.gallons for s in stops),
        total_cost=sum(s.cost for s in stops),
        range_miles=range_miles,
        mpg=mpg,
        corridor_miles=corridor,
        stop_penalty=stop_penalty,
        stations_on_route=len(on_route),
        route_cache_hit=cache_hit,
        external_api_calls=counter.calls,
        took_ms=(time.perf_counter() - started) * 1000,
    )
