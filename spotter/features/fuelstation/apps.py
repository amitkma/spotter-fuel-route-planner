"""App config for the fuelstation feature."""

# Django imports
from django.apps import AppConfig


class FuelStationConfig(AppConfig):
    """FuelStation feature app config."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "spotter.features.fuelstation"
    label = "fuelstation"
