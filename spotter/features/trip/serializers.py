"""Serializers for trip planning."""

# Standard library imports
from typing import Any

# Other third-party library imports
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

# Spotter imports
from spotter.features.trip.services import TripPlan


class RoundedFloatField(serializers.FloatField):
    """Float rounded to a fixed number of decimals on output."""

    def __init__(self, decimals: int = 2, **kwargs: Any) -> None:
        self.decimals = decimals
        kwargs.setdefault("read_only", True)
        super().__init__(**kwargs)

    def to_representation(self, value: Any) -> Any:
        """Round the value."""
        return round(float(value), self.decimals)


class TripPlanRequestSerializer(serializers.Serializer):
    """Trip planning input."""

    start = serializers.CharField(
        max_length=200,
        help_text="Start location in the USA: 'City, ST' (e.g. 'Chicago, IL') or 'lat,lng'. "
        "Other free-text addresses are geocoded online.",
    )
    finish = serializers.CharField(
        max_length=200, help_text="Finish location in the USA, same formats as `start`."
    )
    stop_penalty = serializers.FloatField(
        required=False,
        min_value=0,
        max_value=100,
        help_text="USD the optimiser charges per stop to avoid tiny top-ups (default 5). "
        "0 gives the absolute cheapest plan, whatever the number of stops.",
    )


class LocationSerializer(serializers.Serializer):
    """A resolved start/finish location."""

    query = serializers.CharField()
    name = serializers.CharField()
    lat = RoundedFloatField(6, source="point.lat")
    lng = RoundedFloatField(6, source="point.lng")
    resolved_by = serializers.CharField(
        source="source", help_text="How it was geocoded: coordinates | gazetteer | nominatim"
    )


class FuelStopSerializer(serializers.Serializer):
    """One fuel stop."""

    sequence = serializers.IntegerField()
    opis_id = serializers.IntegerField(source="station.station.opis_id")
    name = serializers.CharField(source="station.station.name")
    address = serializers.CharField(source="station.station.address")
    city = serializers.CharField(source="station.station.city")
    state = serializers.CharField(source="station.station.state")
    lat = RoundedFloatField(6, source="station.station.lat")
    lng = RoundedFloatField(6, source="station.station.lng")
    price_per_gallon = RoundedFloatField(3, source="station.station.price")
    route_mile = RoundedFloatField(1, source="station.mile", help_text="Miles from the start.")
    off_route_miles = RoundedFloatField(
        1, source="station.off_route_miles", help_text="Straight-line distance from the route."
    )
    gallons = RoundedFloatField(2)
    cost = RoundedFloatField(2, help_text="USD")


class RouteSummarySerializer(serializers.Serializer):
    """Route summary."""

    distance_miles = RoundedFloatField(1)
    duration_hours = serializers.SerializerMethodField()

    def get_duration_hours(self, plan: TripPlan) -> float:
        """Driving time without stops."""
        return round(plan.duration_seconds / 3600, 2)


class FuelSummarySerializer(serializers.Serializer):
    """Fuel plan summary."""

    vehicle_range_miles = RoundedFloatField(0, source="range_miles")
    miles_per_gallon = RoundedFloatField(1, source="mpg")
    total_gallons = RoundedFloatField(2)
    total_cost = RoundedFloatField(2, help_text="USD spent on fuel for the whole trip.")
    average_price_per_gallon = serializers.SerializerMethodField()
    stations_on_route = serializers.IntegerField()
    stop_penalty = RoundedFloatField(2, help_text="Per-stop penalty used while optimising.")
    stops = FuelStopSerializer(many=True)

    def get_average_price_per_gallon(self, plan: TripPlan) -> float | None:
        """Effective price paid per gallon."""
        return round(plan.total_cost / plan.total_gallons, 3) if plan.total_gallons else None


class MetaSerializer(serializers.Serializer):
    """Request metadata."""

    external_api_calls = serializers.DictField(child=serializers.IntegerField())
    route_cache_hit = serializers.BooleanField()
    took_ms = RoundedFloatField(1)


class TripPlanSerializer(serializers.Serializer):
    """Trip plan output. Pass the map page URL as `map_url` in the context."""

    start = LocationSerializer()
    finish = LocationSerializer()
    route = RouteSummarySerializer(source="*")
    fuel = FuelSummarySerializer(source="*")
    map = serializers.SerializerMethodField()
    assumptions = serializers.ListField(child=serializers.CharField())
    meta = MetaSerializer(source="*")

    @extend_schema_field(
        {
            "type": "object",
            "properties": {
                "url": {"type": "string", "format": "uri"},
                "geojson": {"type": "object", "description": "GeoJSON FeatureCollection"},
            },
        }
    )
    def get_map(self, plan: TripPlan) -> dict[str, Any]:
        """Map page link and a GeoJSON FeatureCollection (route line + start/finish/stops)."""
        return {"url": self.context.get("map_url"), "geojson": build_geojson(plan)}


def build_geojson(plan: TripPlan) -> dict[str, Any]:
    """Build a GeoJSON FeatureCollection (works as-is in geojson.io, Leaflet, Mapbox...)."""

    def point(lat: float, lng: float, props: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [round(lng, 6), round(lat, 6)]},
            "properties": props,
        }

    features: list[dict[str, Any]] = [
        {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": [[round(lng, 5), round(lat, 5)] for lat, lng in plan.geometry],
            },
            "properties": {
                "kind": "route",
                "distance_miles": round(plan.distance_miles, 1),
                "stroke": "#2563eb",
                "stroke-width": 4,
            },
        },
        point(
            plan.start.point.lat,
            plan.start.point.lng,
            {"kind": "start", "name": plan.start.name, "marker-color": "#16a34a"},
        ),
        point(
            plan.finish.point.lat,
            plan.finish.point.lng,
            {"kind": "finish", "name": plan.finish.name, "marker-color": "#dc2626"},
        ),
    ]
    for stop in plan.stops:
        station = stop.station.station
        features.append(
            point(
                station.lat,
                station.lng,
                {
                    "kind": "fuel_stop",
                    "sequence": stop.sequence,
                    "name": station.name,
                    "address": f"{station.address}, {station.city}, {station.state}",
                    "price_per_gallon": round(station.price, 3),
                    "gallons": round(stop.gallons, 2),
                    "cost": round(stop.cost, 2),
                    "route_mile": round(stop.station.mile, 1),
                    "marker-color": "#f59e0b",
                    "marker-symbol": str(stop.sequence),
                },
            )
        )
    return {"type": "FeatureCollection", "features": features}
