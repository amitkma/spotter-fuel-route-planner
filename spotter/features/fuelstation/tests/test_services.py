"""Tests for importing fuel stations."""

# Standard library imports
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

# Other third-party library imports
import numpy as np

# Spotter imports
from integrations.geocoding.nominatim.client import NominatimResult
from spotter.features.fuelstation.models import FuelStation
from spotter.features.fuelstation.selectors import StationIndex, StationInfo
from spotter.features.fuelstation.services import import_fuel_stations
from spotter.features.places.models import Place
from spotter.tests.base import BaseTest

CSV = """OPIS Truckstop ID,Truckstop Name,Address,City,State,Rack ID,Retail Price
20,PILOT TRAVEL CENTER #1243,"I-8, EXIT 119 & SR-85",Gila Bend,AZ,930,3.899
20,PILOT #1243,"I-8, EXIT 119 & SR-85",Gila Bend,AZ,930,3.799
21,FLYING J,"I-10, EXIT 1",St. Louis,MO,1,3.5
22,HUSKY,"HWY 1",Calgary,AB,1,1.5
23,TINY STOP,"SR-1",Hamlet,TX,1,3.2
24,BROKEN,"SR-1",Gila Bend,AZ,1,n/a
"""


class ImportFuelStationsTest(BaseTest):
    def setUp(self):
        super().setUp()
        self.create_place("Gila Bend", "AZ", 32.94, -112.71)
        self.create_place("Saint Louis", "MO", 38.63, -90.24)
        self.tmp = Path(tempfile.mkdtemp())
        self.csv = self.tmp / "prices.csv"
        self.csv.write_text(CSV)
        self.cache = self.tmp / "geocoded.json"

    def test_offline_import(self):
        report = import_fuel_stations(self.csv, self.cache, online_geocoding=False)

        self.assertEqual(report.rows, 6)
        self.assertEqual(report.skipped_non_us, 1)
        self.assertEqual(report.skipped_invalid, 1)
        self.assertEqual(report.duplicates, 1)
        self.assertEqual(report.stations, 3)
        self.assertEqual(report.not_geocoded, 1)  # Hamlet, TX is not a known place

        pilot = FuelStation.objects.get(opis_id=20)
        self.assertEqual(pilot.name, "PILOT #1243")  # the cheaper duplicate wins
        self.assertEqual(float(pilot.retail_price), 3.799)
        self.assertEqual((pilot.lat, pilot.lng), (32.94, -112.71))
        self.assertIsNotNone(FuelStation.objects.get(opis_id=21).lat)  # "St." == "Saint"
        self.assertFalse(self.cache.exists())

    def test_online_geocoding_is_cached_to_file(self):
        result = NominatimResult("Hamlet, Texas", 31.0, -99.0)
        with (
            patch("integrations.geocoding.nominatim.client.NominatimGeocoder.search",
                  return_value=result) as search,
            patch("spotter.features.fuelstation.services.time.sleep"),
        ):  # fmt: skip
            report = import_fuel_stations(self.csv, self.cache, online_geocoding=True)
            import_fuel_stations(self.csv, self.cache, online_geocoding=True)

        self.assertEqual(search.call_count, 1)
        self.assertEqual(report.geocoded_online, 1)
        self.assertEqual(json.loads(self.cache.read_text()), {"Hamlet|TX": [31.0, -99.0]})
        hamlet = FuelStation.objects.get(opis_id=23)
        self.assertEqual(hamlet.geocode_source, FuelStation.GeocodeSource.NOMINATIM)
        self.assertTrue(Place.objects.filter(name="Hamlet", kind=Place.Kind.OVERRIDE).exists())


class StationIndexTest(BaseTest):
    def test_along_route_filters_by_corridor_and_orders_by_mile(self):
        def info(i, lat, lng):
            return StationInfo(i, i, f"S{i}", "", "", "TX", 3.0, lat, lng)

        index = StationIndex([info(1, 31.0, -97.05), info(2, 30.5, -97.0), info(3, 31.0, -95.0)])
        points = np.column_stack((np.linspace(30, 32, 201), np.full(201, -97.0)))
        miles = np.linspace(0, 138.2, 201)

        hits = index.along_route(points, miles, corridor_miles=10)

        self.assertEqual([h.station.id for h in hits], [2, 1])
        self.assertAlmostEqual(hits[0].mile, 34.55, delta=1)
        self.assertAlmostEqual(hits[1].off_route_miles, 2.96, delta=0.1)
