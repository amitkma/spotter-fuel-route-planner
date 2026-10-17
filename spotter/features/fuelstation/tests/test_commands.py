"""Tests for the data import management commands."""

# Standard library imports
import gzip
import tempfile
from io import StringIO
from pathlib import Path

# Django imports
from django.core.management import CommandError, call_command

# Spotter imports
from spotter.features.fuelstation.models import FuelStation
from spotter.features.places.models import Place
from spotter.tests.base import BaseTest


class ImportCommandsTest(BaseTest):
    def setUp(self):
        super().setUp()
        self.tmp = Path(tempfile.mkdtemp())
        self.places = self.tmp / "places.csv.gz"
        with gzip.open(self.places, "wt") as fh:
            fh.write("name,state,lat,lng,kind\nGila Bend,AZ,32.94,-112.71,place\n")
        self.prices = self.tmp / "prices.csv"
        self.prices.write_text(
            "OPIS Truckstop ID,Truckstop Name,Address,City,State,Rack ID,Retail Price\n"
            '20,PILOT #1243,"I-8, EXIT 119",Gila Bend,AZ,930,3.899\n'
        )

    def test_stations_require_places(self):
        with self.assertRaises(CommandError):
            call_command("import_fuel_stations", file=self.prices, offline=True, stdout=StringIO())

    def test_import_places_then_stations(self):
        out = StringIO()
        call_command("import_places", file=self.places, stdout=out)
        call_command("import_places", file=self.places, stdout=out)  # idempotent
        call_command(
            "import_fuel_stations",
            file=self.prices,
            geocode_cache=self.tmp / "cache.json",
            offline=True,
            stdout=out,
        )
        self.assertEqual(Place.objects.count(), 1)
        self.assertEqual(FuelStation.objects.get().lat, 32.94)
        self.assertIn("Imported 1 fuel stations.", out.getvalue())
