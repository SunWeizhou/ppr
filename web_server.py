"""arXiv Paper Recommender — web server entry point.

Thin Flask application shell. Page rendering, business logic, and API
handling live in app/viewmodels/, app/services/, and app/routes/.
"""

from __future__ import annotations

import os
import subprocess  # noqa: F401 — test compat (mocked via web_server.subprocess)
import time

from flask import Flask, request
from flask_cors import CORS

from app_paths import CACHE_DIR, PROJECT_ROOT, STATE_DB_PATH, ensure_runtime_dirs
from logger_config import get_logger
from state_store import get_state_store

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------

app = Flask(__name__)
CORS(app)


@app.before_request
def _log_request():
    request._start_time = time.time()


@app.after_request
def _log_response(response):
    duration = time.time() - getattr(request, "_start_time", time.time())
    logger.info("%s %s %s (%.3fs)", request.method, request.path, response.status_code, duration)
    return response


# ---------------------------------------------------------------------------
# Module-level state (mutable — tests patch these)
# ---------------------------------------------------------------------------

STATE_STORE = get_state_store()
STATE_DB_FILE = str(STATE_DB_PATH)
FEEDBACK_FILE = str(CACHE_DIR / "user_feedback.json")
FAVORITES_FILE = str(CACHE_DIR / "favorite_papers.json")
CACHE_FILE = str(CACHE_DIR / "paper_cache.json")

SNAPSHOT_FILES = {
    "user_profile": PROJECT_ROOT / "user_profile.json",
    "user_config": PROJECT_ROOT / "user_config.json",
    "keywords_config": PROJECT_ROOT / "keywords_config.json",
    "user_feedback": CACHE_DIR / "user_feedback.json",
    "favorite_papers": CACHE_DIR / "favorite_papers.json",
    "paper_cache": CACHE_DIR / "paper_cache.json",
    "journal_update_log": CACHE_DIR / "journal_update_log.json",
}

# ---------------------------------------------------------------------------
# Blueprint registration (module-level -- required for test clients)
# ---------------------------------------------------------------------------


from app.routes import register_blueprints  # noqa: E402
from app.viewmodels.shared import NAV_ITEM_CONFIG  # noqa: E402 — test compat re-export

register_blueprints(app)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    ensure_runtime_dirs()

    if os.getenv("USE_DEV_SERVER"):
        logger.info("Starting Flask dev server on http://localhost:5555")
        app.run(host="localhost", port=5555, debug=True)
    else:
        from waitress import serve

        logger.info("Starting waitress on http://localhost:5555")
        serve(app, host="localhost", port=5555)


if __name__ == "__main__":
    main()
