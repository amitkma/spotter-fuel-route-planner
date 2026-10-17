"""Admin for fuel stations."""

# Django imports
from django.contrib import admin

# Spotter imports
from spotter.features.fuelstation.models import FuelStation


@admin.register(FuelStation)
class FuelStationAdmin(admin.ModelAdmin):
    """Admin for FuelStation."""

    list_display = ("opis_id", "name", "city", "state", "retail_price", "lat", "lng")
    list_filter = ("state", "geocode_source")
    search_fields = ("name", "city", "address", "opis_id")
