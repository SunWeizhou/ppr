"""Flask application factory with dependency injection.

Centralizes Flask app setup (CORS, hooks, middleware, blueprints) and
accepts optional ``state_store`` / ``ai_provider`` for test injection.
"""

from __future__ import annotations

import hashlib
import os
import time
from urllib.parse import urlparse

from flask import Flask, jsonify, request
from flask_cors import CORS

from app.services.ai_providers import build_ai_provider_from_env
from app.routes import register_blueprints
from app_paths import PROJECT_ROOT
from logger_config import get_logger
from state_store import get_state_store

logger = get_logger(__name__)


def _configured_port() -> int:
    """Return the local server port, defaulting to the product port."""
    raw = os.getenv("PORT") or os.getenv("FLASK_RUN_PORT") or "5555"
    try:
        return int(raw)
    except ValueError:
        return 5555


def create_app(state_store=None, ai_provider=None):
    """Create and configure a Flask application instance.

    Parameters
    ----------
    state_store : optional
        State store instance. Defaults to ``get_state_store()``.
    ai_provider : optional
        AI analysis provider. Defaults to ``build_ai_provider_from_env()``.

    Returns
    -------
    Flask
        Fully configured app with all blueprints, hooks, and middleware.
    """
    app = Flask(__name__, root_path=str(PROJECT_ROOT))

    # ── Config ──────────────────────────────────────────────────────────────
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 31536000

    # ── Dependency injection ────────────────────────────────────────────────
    app.config["STATE_STORE"] = get_state_store() if state_store is None else state_store
    app.config["AI_ANALYSIS_PROVIDER"] = (
        build_ai_provider_from_env() if ai_provider is None else ai_provider
    )

    # ── CORS ────────────────────────────────────────────────────────────────
    port = _configured_port()
    CORS(
        app,
        origins=[
            "http://localhost:5555",
            "http://127.0.0.1:5555",
            f"http://localhost:{port}",
            f"http://127.0.0.1:{port}",
        ],
    )

    # ── Static version hash (cache-bust) ────────────────────────────────────

    _static_version: str | None = None

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

    def _get_static_version() -> str:
        nonlocal _static_version
        if _static_version is None:
            _static_version = _compute_static_hash()
        return _static_version

    # ── Hooks ───────────────────────────────────────────────────────────────

    @app.after_request
    def _cache_static_assets(response):
        if request.path.startswith("/static/"):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response

    @app.context_processor
    def _inject_static_version():
        return {"static_version": _get_static_version()}

    @app.before_request
    def _log_and_guard_request():
        request._start_time = time.time()

        # Local CSRF guard: for state-changing methods, verify the request
        # originates from the local app (malicious pages cannot set a localhost Origin)
        if request.method in ("POST", "PUT", "DELETE", "PATCH"):
            origin = request.headers.get("Origin") or ""
            referer = request.headers.get("Referer") or ""
            allowed = frozenset({("localhost", 5555), ("127.0.0.1", 5555),
                                 ("localhost", port), ("127.0.0.1", port)})

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

    # ── Blueprints ─────────────────────────────────────────────────────────
    register_blueprints(app)

    return app
