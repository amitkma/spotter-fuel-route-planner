# Django imports
from django.conf import settings
from django.utils.module_loading import import_string

# Spotter imports
from integrations.routing.interface import RoutingProvider


def get_routing_provider() -> RoutingProvider:
    """Return an instance of the configured routing provider."""
    provider: RoutingProvider = import_string(settings.ROUTING_PROVIDER)()
    return provider
