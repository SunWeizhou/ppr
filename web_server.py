"""StatDesk — web server entry point.

Thin Flask application shell. Page rendering, business logic, and API
handling live in app/viewmodels/, app/services/, and app/routes/.
"""

from __future__ import annotations

import hashlib
import os
import subprocess  # noqa: F401 — test compat (mocked via web_server.subprocess)
import time
from urllib.parse import urlparse

from flask import Flask, jsonify, request
from flask_cors import CORS

from app_paths import CACHE_DIR, PROJECT_ROOT, SNAPSHOT_FILES, STATE_DB_PATH, ensure_runtime_dirs
from logger_config import get_logger
from state_store import get_state_store

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------

app = Flask(__name__)
if os.getenv("USE_DEV_SERVER"):
    CORS(app)
else:
    CORS(app, origins=["http://localhost:5555", "http://127.0.0.1:5555"])

# Static assets: 1-year immutable cache (cache-bust via content hash)
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 31536000


def _compute_static_hash() -> str:
    """MD5 of all static .js/.css content → auto cache-bust on any change."""
    static_dir = os.path.join(PROJECT_ROOT, "static")
    hasher = hashlib.md5()
    for root, _dirs, files in os.walk(static_dir):
        for f in sorted(files):
            if f.endswith((".js", ".css")):
                path = os.path.join(root, f)
                try:
                    with open(path, "rb") as fh:
                        hasher.update(fh.read())
                except OSError:
                    pass  # skip unreadable files
    return hasher.hexdigest()[:8]


_STATIC_VERSION = _compute_static_hash()


@app.after_request
def _cache_static_assets(response):
    if request.path.startswith("/static/"):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return response


@app.context_processor
def _inject_static_version():
    return {"static_version": _STATIC_VERSION}


@app.before_request
def _log_and_guard_request():
    request._start_time = time.time()

    # Local CSRF guard: for state-changing methods, verify the request
    # originates from the local app (malicious pages cannot set a localhost Origin)
    if request.method in ("POST", "PUT", "DELETE", "PATCH"):
        origin = request.headers.get("Origin") or ""
        referer = request.headers.get("Referer") or ""
        allowed = frozenset({("localhost", 5555), ("127.0.0.1", 5555)})

        def _host_port_ok(url: str) -> bool:
            if not url:
                return True  # no header = not cross-origin, allow
            try:
                p = urlparse(url)
                return (p.hostname, p.port or 80) in allowed
            except Exception:
                return False

        if not _host_port_ok(origin) or not _host_port_ok(referer):
            logger.warning("Blocked cross-origin %s %s (Origin: %s, Referer: %s)",
                           request.method, request.path, origin, referer)
            return jsonify({"success": False, "error": "Cross-origin requests not allowed"}), 403


@app.after_request
def _log_response(response):
    duration = time.time() - getattr(request, "_start_time", time.time())
    logger.info("%s %s %s (%.3fs)", request.method, request.path, response.status_code, duration)
    return response


# ---------------------------------------------------------------------------
# Module-level state (mutable — tests patch these)
# ---------------------------------------------------------------------------

STATE_STORE = get_state_store()
app.config["STATE_STORE"] = STATE_STORE  # P2-C: inject into Flask app config
STATE_DB_FILE = str(STATE_DB_PATH)
FEEDBACK_FILE = str(CACHE_DIR / "user_feedback.json")
FAVORITES_FILE = str(CACHE_DIR / "favorite_papers.json")
CACHE_FILE = str(CACHE_DIR / "paper_cache.json")

# SNAPSHOT_FILES imported from app_paths (consolidated, single source of truth)

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

    # Recover stale jobs on startup so no job blocks future runs
    try:
        recovered = STATE_STORE.recover_stale_jobs(stale_after_minutes=120)
        if recovered:
            logger.info("Recovered %d stale job(s) on startup", recovered)
    except Exception:
        logger.debug("Job recovery on startup skipped (DB not ready)")

    if os.getenv("USE_DEV_SERVER"):
        logger.info("Starting Flask dev server on http://localhost:5555")
        app.run(host="localhost", port=5555, debug=True)
    else:
        from waitress import serve

        logger.info("Starting waitress on http://localhost:5555")
        serve(app, host="localhost", port=5555)


if __name__ == "__main__":
    main()
