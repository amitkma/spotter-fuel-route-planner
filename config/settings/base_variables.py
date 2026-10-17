"""Variables that are used by the base settings and its components."""

# Standard library imports
from pathlib import Path

# Spotter imports
from config.env import env

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Read the .env file (if any) before anything else reads the environment.
env.read_env(BASE_DIR / ".env")

DJANGO_ENV = env.str("DJANGO_ENV", default="development")
DEBUG = env.bool("DEBUG", default=DJANGO_ENV == "development")
SECRET_KEY = env.str("DJANGO_SECRET_KEY", default="django-insecure-only-for-local-development")

DATA_DIR = BASE_DIR / "data"
