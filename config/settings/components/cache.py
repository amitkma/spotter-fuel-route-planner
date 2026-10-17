"""Cache settings.

Redis if `REDIS_URL` is set, locmem otherwise. Mostly used to cache routes.
"""

# Spotter imports
from config.env import env

REDIS_URL = env.str("REDIS_URL", default="")

if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "spotter",
            "OPTIONS": {"MAX_ENTRIES": 2000},
        }
    }

# How long routes and geocoding results are kept (seconds).
ROUTE_CACHE_TIMEOUT = env.int("ROUTE_CACHE_TIMEOUT", default=60 * 60 * 24)
