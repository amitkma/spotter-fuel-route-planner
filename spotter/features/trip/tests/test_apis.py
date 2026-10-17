"""API tests for the trip planner."""

# Standard library imports
from unittest.mock import patch

# Django imports
from django.test import override_settings
from django.urls import reverse

# Other third-party library imports
from rest_framework import status

# Spotter imports
from integrations.routing.interface import Route, RouteNotFoundError, RoutingProvider
from spotter.core.exceptions import ExternalAPIException
from spotter.tests.base import APIBaseTest

FAKE_PROVIDER = "spotter.features.trip.tests.test_apis.FakeRoutingProvider"

# A straight north-south "highway" along lng -97, from lat 30 to lat 44 (~967 miles).
ROUTE = Route(
    coordinates=[(30.0 + i * 0.5, -97.0) for i in range(29)],
    distance_meters=967 * 1609.344,
    duration_seconds=15 * 3600,
)


class FakeRoutingProvider(RoutingProvider):
    name = "fake"
    calls = 0
    route: Route | Exception = ROUTE

    def get_route(self, start, finish):
        type(self).calls += 1
        if isinstance(self.route, Exception):
            raise self.route
        return self.route


@override_settings(ROUTING_PROVIDER=FAKE_PROVIDER)
class TripPlanAPITest(APIBaseTest):
    def setUp(self):
        super().setUp()
        FakeRoutingProvider.calls = 0
        FakeRoutingProvider.route = ROUTE
        self.url = reverse("trip-plan")
        self.create_place("Southville", "TX", 30.0, -97.0)
        self.create_place("Northville", "NE", 44.0, -97.0)
        # Stations next to the highway (lat ~ 69 miles per degree).
        self.create_station(1, 3.90, 30.01, -97.0, name="START STOP")  # mile ~0.7
        self.create_station(2, 3.10, 33.00, -97.02, name="CHEAP STOP")  # mile ~207
        self.create_station(3, 4.50, 36.50, -97.0, name="PRICEY STOP")  # mile ~449
        self.create_station(4, 3.30, 38.00, -97.0, name="GOOD STOP")  # mile ~553
        self.create_station(5, 2.00, 37.00, -90.0)  # cheap but 380 miles off the route

    def test_plan_returns_route_stops_cost_and_map(self):
        response = self.client.get(
            self.url, {"start": "Southville, TX", "finish": "Northville, NE"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        data = response.json()

        self.assertEqual(data["start"]["name"], "Southville, TX")
        self.assertEqual(data["start"]["resolved_by"], "gazetteer")
        self.assertAlmostEqual(data["route"]["distance_miles"], 967, delta=1)
        names = [s["name"] for s in data["fuel"]["stops"]]
        self.assertEqual(names, ["START STOP", "CHEAP STOP", "GOOD STOP"])
        self.assertNotIn("PRICEY STOP", names)
        self.assertAlmostEqual(data["fuel"]["total_gallons"], 96.7, delta=0.1)
        expected = sum(s["gallons"] * s["price_per_gallon"] for s in data["fuel"]["stops"])
        self.assertAlmostEqual(data["fuel"]["total_cost"], expected, delta=0.05)

        kinds = [f["properties"]["kind"] for f in data["map"]["geojson"]["features"]]
        self.assertEqual(kinds, ["route", "start", "finish", "fuel_stop", "fuel_stop", "fuel_stop"])
        self.assertIn("/trips/map/?start=Southville", data["map"]["url"])
        self.assertEqual(data["meta"]["external_api_calls"], {"fake": 1})

    def test_route_is_cached_between_requests(self):
        params = {"start": "Southville, TX", "finish": "Northville, NE"}
        self.client.get(self.url, params)
        response = self.client.post(self.url, params, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.json()["meta"]["route_cache_hit"])
        self.assertEqual(response.json()["meta"]["external_api_calls"], {})
        self.assertEqual(FakeRoutingProvider.calls, 1)

    def test_map_page_reuses_cached_route(self):
        params = {"start": "Southville, TX", "finish": "Northville, NE"}
        self.client.get(self.url, params)
        response = self.client.get(reverse("trip-map"), params)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(response, "CHEAP STOP")
        self.assertContains(response, 'id="route-geojson"')
        self.assertEqual(FakeRoutingProvider.calls, 1)

    def test_coordinates_are_accepted(self):
        response = self.client.get(self.url, {"start": "30.0,-97.0", "finish": "44,-97"})
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertEqual(response.json()["start"]["resolved_by"], "coordinates")
        self.assertEqual(response.json()["start"]["name"], "Near Southville, TX")

    def test_missing_params(self):
        response = self.client.get(self.url, {"start": "Southville, TX"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()["errors"][0]["attr"], "finish")

    def test_unknown_location(self):
        response = self.client.get(self.url, {"start": "Atlantis, TX", "finish": "Northville, NE"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()["errors"][0]["code"], "location_not_found")
        self.assertEqual(FakeRoutingProvider.calls, 0)

    @override_settings(GEOCODING_ONLINE_FALLBACK=True)
    def test_location_outside_usa(self):
        for start in ("51.5072,-0.1276", "Toronto, ON"):
            with (
                self.subTest(start=start),
                patch("integrations.geocoding.nominatim.client.NominatimGeocoder.search") as search,
            ):
                response = self.client.get(self.url, {"start": start, "finish": "Northville, NE"})
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertEqual(response.json()["errors"][0]["code"], "location_outside_usa")
                search.assert_not_called()

    def test_no_fuel_within_range(self):
        FakeRoutingProvider.route = Route(
            coordinates=[(30.0 + i * 0.5, -100.0) for i in range(29)],
            distance_meters=967 * 1609.344,
            duration_seconds=1,
        )
        response = self.client.get(
            self.url, {"start": "Southville, TX", "finish": "Northville, NE"}
        )
        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(response.json()["errors"][0]["code"], "no_fuel_in_range")

    def test_no_route(self):
        FakeRoutingProvider.route = RouteNotFoundError("NoRoute")
        response = self.client.get(
            self.url, {"start": "Southville, TX", "finish": "Northville, NE"}
        )
        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(response.json()["errors"][0]["code"], "no_route")

    def test_routing_provider_down(self):
        FakeRoutingProvider.route = ExternalAPIException(True, "boom")
        # 5xx responses fire `got_request_exception`, which the test client re-raises.
        self.client.raise_request_exception = False
        response = self.client.get(
            self.url, {"start": "Southville, TX", "finish": "Northville, NE"}
        )
        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)

    @override_settings(GEOCODING_ONLINE_FALLBACK=True)
    def test_free_text_falls_back_to_nominatim_once(self):
        # Spotter imports
        from integrations.geocoding.nominatim.client import NominatimResult

        result = NominatimResult("Southville Main St", 30.0, -97.0)
        with patch(
            "integrations.geocoding.nominatim.client.NominatimGeocoder.search", return_value=result
        ) as search:
            params = {"start": "1 Main Street Southville", "finish": "Northville, NE"}
            first = self.client.get(self.url, params).json()
            second = self.client.get(self.url, params).json()
        self.assertEqual(search.call_count, 1)
        self.assertEqual(first["meta"]["external_api_calls"], {"nominatim": 1, "fake": 1})
        self.assertEqual(second["meta"]["external_api_calls"], {})

    def test_status_and_unknown_api(self):
        self.assertEqual(self.client.get("/api/status/").json()["fuel_stations"], 5)
        self.assertEqual(self.client.get("/api/nope/").status_code, status.HTTP_404_NOT_FOUND)

    def test_schema_renders(self):
        self.assertEqual(self.client.get(reverse("schema")).status_code, status.HTTP_200_OK)

    def test_stop_penalty_param(self):
        params = {"start": "Southville, TX", "finish": "Northville, NE", "stop_penalty": 0}
        response = self.client.get(self.url, params)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["fuel"]["stop_penalty"], 0)
        self.assertIn("stop_penalty=0", response.json()["map"]["url"])

        response = self.client.get(self.url, params | {"stop_penalty": -1})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()["errors"][0]["attr"], "stop_penalty")

    def test_trip_shorter_than_reserve_is_still_billed(self):
        FakeRoutingProvider.route = Route(
            coordinates=[(30.0, -97.0), (30.2, -97.0)],
            distance_meters=20 * 1609.344,
            duration_seconds=1,
        )
        response = self.client.get(
            self.url, {"start": "Southville, TX", "finish": "Northville, NE"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        fuel = response.json()["fuel"]
        self.assertEqual(len(fuel["stops"]), 1)
        self.assertAlmostEqual(fuel["total_gallons"], 2.0)
        self.assertAlmostEqual(fuel["total_cost"], 2.0 * 3.90, places=2)
