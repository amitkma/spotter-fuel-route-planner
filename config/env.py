"""We expose this variable to access env vars in other modules."""

# Standard library imports
import sys

# Other third-party library imports
import environ

env = environ.Env(TEST=(bool, "test" in sys.argv or sys.argv[0].endswith("pytest")))
