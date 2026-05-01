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
# Import all route modules to register their routes
from . import (
    ai,  # noqa: F401
    collections,  # noqa: F401
    evaluation,  # noqa: F401
    feedback,  # noqa: F401
    helpers,  # noqa: F401
    inbox,  # noqa: F401
    keywords,  # noqa: F401
    paper,  # noqa: F401
    queue,  # noqa: F401
    saved_searches,  # noqa: F401
    state,  # noqa: F401
    subscriptions,  # noqa: F401
)

# Re-export selected route functions for test backward compat
# (tests and inspector reference api_routes.manage_queue etc.)
from .queue import manage_queue, manage_queue_bulk  # noqa: F401
