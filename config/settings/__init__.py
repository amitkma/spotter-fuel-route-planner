# Spotter imports
from config.env import env

# Spotter local imports
from .base import *

if not env("TEST"):
    if DJANGO_ENV == "development":
        # Spotter local imports
        from .development import *

        try:
            # Spotter local imports
            from .local import *
        except ImportError:
            # No local settings was found, skipping.
            pass

    else:
        # Spotter local imports
        from .production import *

else:
    # Spotter local imports
    from .test import *
