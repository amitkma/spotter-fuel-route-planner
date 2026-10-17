"""Tests for the OSRM routing provider."""

# Standard library imports
from unittest import TestCase
from unittest.mock import MagicMock, patch

# Other third-party library imports
import requests

# Spotter imports
from integrations.routing.interface import RouteNotFoundError
from integrations.routing.osrm.client import OSRMRoutingProvider
from spotter.core.exceptions import ExternalAPIException
from spotter.core.types import LatLng

START, FINISH = LatLng(41.88, -87.63), LatLng(29.76, -95.37)


def fake_response(status_code: int, payload: dict) -> MagicMock:
    response = MagicMock(status_code=status_code)
    response.json.return_value = payload
    return response


class OSRMRoutingProviderTest(TestCase):
    def setUp(self):
        self.provider = OSRMRoutingProvider(base_url="https://osrm.test", timeout=1)

    def test_parses_route_and_swaps_coordinates(self):
        payload = {
            "code": "Ok",
            "routes": [
                {
                    "distance": 1748381.0,
                    "duration": 71500.4,
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[-87.63, 41.88], [-95.37, 29.76]],
                    },
                }
            ],
        }
        with patch.object(
            self.provider.session, "get", return_value=fake_response(200, payload)
        ) as get:
            route = self.provider.get_route(START, FINISH)

        self.assertEqual(get.call_count, 1)
        url = get.call_args.args[0]
        self.assertEqual(
            url, "https://osrm.test/route/v1/driving/-87.630000,41.880000;-95.370000,29.760000"
        )
        self.assertEqual(get.call_args.kwargs["params"]["overview"], "full")
        self.assertEqual(route.coordinates, [(41.88, -87.63), (29.76, -95.37)])
        self.assertEqual(route.distance_meters, 1748381.0)

    def test_no_route(self):
        response = fake_response(400, {"code": "NoRoute", "message": "Impossible route"})
        with patch.object(self.provider.session, "get", return_value=response):
            with self.assertRaises(RouteNotFoundError):
                self.provider.get_route(START, FINISH)

    def test_server_error_is_retryable(self):
        with patch.object(self.provider.session, "get", return_value=fake_response(503, {})):
            with self.assertRaises(ExternalAPIException) as ctx:
                self.provider.get_route(START, FINISH)
        self.assertTrue(ctx.exception.is_retryable)

    def test_network_error(self):
        with patch.object(
            self.provider.session, "get", side_effect=requests.ConnectionError("down")
        ):
            with self.assertRaises(ExternalAPIException):
                self.provider.get_route(START, FINISH)
