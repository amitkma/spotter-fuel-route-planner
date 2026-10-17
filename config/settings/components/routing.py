"""Routing, geocoding and vehicle settings."""

# Spotter imports
from config.env import env

# Routing
# Dotted path to a `RoutingProvider` implementation.
ROUTING_PROVIDER = env.str(
    "ROUTING_PROVIDER", default="integrations.routing.osrm.client.OSRMRoutingProvider"
)
# Public OSRM demo server (no key). Use a self-hosted one in prod.
OSRM_BASE_URL = env.str("OSRM_BASE_URL", default="https://router.project-osrm.org")
ROUTING_TIMEOUT_SECONDS = env.float("ROUTING_TIMEOUT_SECONDS", default=15.0)

# Geocoding
# "City, ST" and coordinates are resolved offline from the gazetteer. Nominatim is only used
# for other free text.
GEOCODING_ONLINE_FALLBACK = env.bool("GEOCODING_ONLINE_FALLBACK", default=True)
NOMINATIM_BASE_URL = env.str("NOMINATIM_BASE_URL", default="https://nominatim.openstreetmap.org")
NOMINATIM_USER_AGENT = env.str(
    "NOMINATIM_USER_AGENT", default="spotter-fuel-route-planner/1.0 (assessment)"
)
GEOCODING_TIMEOUT_SECONDS = env.float("GEOCODING_TIMEOUT_SECONDS", default=10.0)

# Vehicle / fuel planning
VEHICLE_RANGE_MILES = env.float("VEHICLE_RANGE_MILES", default=500.0)
VEHICLE_MPG = env.float("VEHICLE_MPG", default=10.0)
# How far off the route a station can be. Generous on purpose since station coords are just
# city centroids.
STATION_CORRIDOR_MILES = env.float("STATION_CORRIDOR_MILES", default=10.0)
# USD per stop, only used inside the optimiser (not in the reported cost). Without it the
# cheapest plan stops every few miles to save a few cents. 0 = strictly cheapest.
FUEL_STOP_PENALTY_USD = env.float("FUEL_STOP_PENALTY_USD", default=5.0)
# Trip starts empty but with this much reserve, so the first stop doesn't have to be the
# nearest station. Billed at the first stop's price.
START_RESERVE_MILES = env.float("START_RESERVE_MILES", default=25.0)
