"""WSGI config for the Spotter project."""

# Standard library imports
import os

# Django imports
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_wsgi_application()
