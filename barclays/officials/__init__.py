"""The officials registry. Importing this package registers every built-in official."""
from .base import REGISTRY, Ctx  # noqa: F401
from . import exec_tests, static_py, text_fidelity  # noqa: F401  (registration side effects)

# What each built-in official is cleared to handle. Built-ins run locally and send nothing anywhere, so they are
# cleared for every label. An adapter that calls a remote service must declare a narrower set here.
CLEARANCE = {name: ["synthetic", "public", "internal", "restricted"] for name in REGISTRY}
