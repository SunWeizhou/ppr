"""Agent Literature Research Assistant — web server entry point.

Thin Flask application shell. Page rendering, business logic, and API
handling live in app/viewmodels/, app/services/, and app/routes/.
"""

from __future__ import annotations

import os
import subprocess  # noqa: F401 — test compat (mocked via web_server.subprocess)

from app.factory import create_app
from app_paths import CACHE_DIR, PROJECT_ROOT, SNAPSHOT_FILES, STATE_DB_PATH, ensure_runtime_dirs
from logger_config import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------

app = create_app()
STATE_STORE = app.config["STATE_STORE"]  # backward compat for test patches

# Module-level state (backward compat — used by some tests and config references)
STATE_DB_FILE = str(STATE_DB_PATH)
FEEDBACK_FILE = str(CACHE_DIR / "user_feedback.json")
FAVORITES_FILE = str(CACHE_DIR / "favorite_papers.json")
CACHE_FILE = str(CACHE_DIR / "paper_cache.json")

# SNAPSHOT_FILES imported from app_paths (consolidated, single source of truth)

# Re-export for test compat
from app.viewmodels.shared import NAV_ITEM_CONFIG  # noqa: E402 — test compat re-export

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _configured_port() -> int:
    """Return the local server port, defaulting to the product port."""
    raw = os.getenv("PORT") or os.getenv("FLASK_RUN_PORT") or "5555"
    try:
        return int(raw)
    except ValueError:
        return 5555


def main():
    ensure_runtime_dirs()

    # Recover stale jobs on startup so no job blocks future runs
    try:
        recovered = STATE_STORE.recover_stale_jobs(stale_after_minutes=120)
        if recovered:
            logger.info("Recovered %d stale job(s) on startup", recovered)
    except Exception:
        logger.debug("Job recovery on startup skipped (DB not ready)")

    port = _configured_port()
    if os.getenv("USE_DEV_SERVER"):
        logger.info("Starting Flask dev server on http://localhost:%s", port)
        app.run(host="localhost", port=port, debug=True)
    else:
        from waitress import serve

        logger.info("Starting waitress on http://localhost:%s", port)
        serve(app, host="localhost", port=port)


if __name__ == "__main__":
    main()
