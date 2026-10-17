"""ASGI config for the Spotter project."""

# Standard library imports
import os

# Django imports
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_asgi_application()
