"""Logging settings."""

# Spotter imports
from config.env import env

LOG_LEVEL = env.str("LOG_LEVEL", default="INFO")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "spotter": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        "integrations": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
    },
}
