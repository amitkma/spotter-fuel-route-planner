"""Models for fuel stations."""

# Django imports
from django.db import models

# Spotter imports
from spotter.core.models import BaseModel, sane_str


class FuelStation(BaseModel):
    """A truck stop with its retail diesel price (from the OPIS price list)."""

    class GeocodeSource(models.TextChoices):
        """How the station's coordinates were obtained."""

        GAZETTEER = "gazetteer", "Census gazetteer (city centroid)"
        NOMINATIM = "nominatim", "Nominatim (city centroid)"

    opis_id = models.PositiveIntegerField(unique=True, help_text="OPIS Truckstop ID")
    name = models.CharField(max_length=128)
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=128)
    state = models.CharField(max_length=2)
    rack_id = models.PositiveIntegerField(null=True, blank=True)
    retail_price = models.DecimalField(max_digits=12, decimal_places=8, help_text="USD per gallon")
    lat = models.FloatField(null=True, blank=True)
    lng = models.FloatField(null=True, blank=True)
    geocode_source = models.CharField(
        max_length=10, choices=GeocodeSource.choices, blank=True, default=""
    )

    class Meta:
        """Metadata for FuelStation."""

        indexes = [models.Index(fields=["state", "city"])]

    __str__ = sane_str("opis_id", "name", "city", "state", "retail_price")
