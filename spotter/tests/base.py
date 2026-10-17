"""Base test cases for the project."""

# Django imports
from django.core.cache import cache
from django.test import TestCase

# Other third-party library imports
from rest_framework.test import APITestCase

# Spotter imports
from spotter.features.fuelstation.models import FuelStation
from spotter.features.fuelstation.selectors import reset_station_index
from spotter.features.places.models import Place
from spotter.features.places.selectors import reset_place_index
from spotter.features.places.utils import normalize_place_name


class TestSetupMixin:
    """Clears process-wide caches so each test sees only its own data."""

    def setUp(self):
        super().setUp()
        cache.clear()
        reset_place_index()
        reset_station_index()

    def tearDown(self):
        reset_place_index()
        reset_station_index()
        super().tearDown()

    @staticmethod
    def create_place(name: str, state: str, lat: float, lng: float) -> Place:
        return Place.objects.create(
            name=name, state=state, normalized_name=normalize_place_name(name), lat=lat, lng=lng
        )

    @staticmethod
    def create_station(opis_id: int, price: float, lat: float, lng: float, **kwargs) -> FuelStation:
        defaults = {
            "name": f"STATION #{opis_id}",
            "address": "I-00, EXIT 1",
            "city": "Somewhere",
            "state": "TX",
        }
        return FuelStation.objects.create(
            opis_id=opis_id, retail_price=price, lat=lat, lng=lng, **(defaults | kwargs)
        )


class BaseTest(TestSetupMixin, TestCase):
    """Base test case for Django test suite."""


class APIBaseTest(TestSetupMixin, APITestCase):
    """Base test case for API tests."""
