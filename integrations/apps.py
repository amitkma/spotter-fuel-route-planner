"""App config for third-party integrations."""

# Django imports
from django.apps import AppConfig


class IntegrationsConfig(AppConfig):
    """Integrations app config."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "integrations"
