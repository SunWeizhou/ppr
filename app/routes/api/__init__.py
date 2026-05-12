"""API route modules — split from monolithic api.py."""
from flask import Blueprint

bp = Blueprint("api", __name__)

# Test-patchable module-level names (set before importing helpers).
#   - STATE_STORE: tests patch this for mocking the state store
#   - AI_ANALYSIS_PROVIDER: tests patch this for mocking the AI provider
# Helpers.py will look up these from the package namespace at call time
# so test reassignments via api_routes.X = ... are always visible.
STATE_STORE = None
AI_ANALYSIS_PROVIDER = None

# Import helpers first (no routes, just shared utilities)
from . import helpers  # noqa: F401

# Import all route modules to register their routes
from . import ai  # noqa: F401
from . import queue  # noqa: F401
from . import feedback  # noqa: F401
from . import state  # noqa: F401
from . import collections  # noqa: F401
from . import saved_searches  # noqa: F401
from . import subscriptions  # noqa: F401
from . import keywords  # noqa: F401
from . import inbox  # noqa: F401
from . import evaluation  # noqa: F401
from . import paper  # noqa: F401
from . import workspaces  # noqa: F401
from . import agent  # noqa: F401
from . import recommendations  # noqa: F401
from . import entities  # noqa: F401


# Re-export selected route functions for test backward compat
# (tests and inspector reference api_routes.manage_queue etc.)
from .queue import manage_queue, manage_queue_bulk  # noqa: F401
