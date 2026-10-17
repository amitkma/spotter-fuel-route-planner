"""App config for Spotter."""

# Django imports
from django.apps import AppConfig


class SpotterConfig(AppConfig):
    """Spotter app config."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "spotter"
