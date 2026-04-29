"""Shared utilities for API route modules.

Provides _current_state_store() (with P2-C app config injection),
helper factory functions, error handlers, and module-level constants.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime

from flask import jsonify

from app.services.ai_analysis_service import AIAnalysisService
from app.services.ai_providers import build_ai_provider_from_env
from app.services.errors import AppError
from app.services.queue_service import QueueService
from app.viewmodels.shared import serialize_collection, serialize_job, serialize_saved_search  # noqa: F401
from app_paths import CACHE_DIR, HISTORY_DIR, PROJECT_ROOT
from state_store import QUEUE_STATUS_VALUES, _canonical_paper_id, get_state_store  # noqa: F401
from utils import atomic_write_json, safe_load_json  # noqa: F401

from . import bp

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level state — internal fallback only
# The test-patchable STATE_STORE / AI_ANALYSIS_PROVIDER live in the package
# namespace (__init__.py). Helpers read them dynamically from the package so
# that ``api_routes.X = ...`` test patches are always visible.
# ---------------------------------------------------------------------------

_own_state_store = get_state_store()

# File paths used by services
FEEDBACK_FILE = str(CACHE_DIR / "user_feedback.json")
FAVORITES_FILE = str(CACHE_DIR / "favorite_papers.json")
CACHE_FILE = str(CACHE_DIR / "paper_cache.json")
# TODO: migrate ScholarService to use subscriptions(type='author')
SCHOLARS_DATA_FILE = str(CACHE_DIR / "scholars.json")


def _package_attr(name: str):
    """Return *name* from the api package, or ``None``."""
    pkg = sys.modules.get(__package__)
    if pkg is not None:
        return getattr(pkg, name, None)
    return None


# ---------------------------------------------------------------------------
# State store resolution — test patches first, app config for production fallback
# ---------------------------------------------------------------------------


def _current_state_store():
    """Return the current StateStore.

    Resolution order:
      1. ``api_routes.STATE_STORE`` — package-level name; test patches reassign this.
      2. ``web_server.STATE_STORE`` — module-level global (backward-compat).
      3. Flask ``current_app.config["STATE_STORE"]`` — P2-C, preferred in production.
      4. The local ``_own_state_store`` fallback.

    Test patches on ``web_server.STATE_STORE`` or ``api_routes.STATE_STORE``
    always win because they are checked before the (immutable) app config,
    preserving backward compat without changing test code.
    """
    # 1. Package-level STATE_STORE (test patches via api_routes.STATE_STORE = ...)
    pkg_store = _package_attr("STATE_STORE")
    if pkg_store is not None:
        return pkg_store

    # 2. web_server module-level (older test patches)
    try:
        import web_server

        return web_server.STATE_STORE
    except Exception:
        pass

    # 3. Flask app config (P2-C — production; checked last so test patches win)
    try:
        from flask import current_app

        store = current_app.config.get("STATE_STORE")
        if store is not None:
            return store
    except (RuntimeError, ImportError):
        pass

    # 4. Local fallback
    return _own_state_store


# ---------------------------------------------------------------------------
# Service factory helpers
# ---------------------------------------------------------------------------


def _ai_analysis_service():
    # Read AI_ANALYSIS_PROVIDER from the package namespace so test patches
    # via ``api_routes.AI_ANALYSIS_PROVIDER = ...`` are visible at call time.
    provider = _package_attr("AI_ANALYSIS_PROVIDER")
    return AIAnalysisService(
        _current_state_store(),
        provider=provider or build_ai_provider_from_env(),
    )


def _queue_service():
    return QueueService(_current_state_store())


def _resolve_path(attr: str, fallback: str) -> str:
    """Resolve a file path, preferring web_server's version for test compatibility."""
    try:
        import web_server

        return getattr(web_server, attr)
    except Exception:
        return fallback


def _settings_service():
    from app.services.settings_service import SettingsService

    return SettingsService()


def _feedback_service():
    from app.services.feedback_service import FeedbackService
    from app.services.scholar_service import ScholarService

    svc = _settings_service()
    return FeedbackService(
        _current_state_store(),
        feedback_file=_resolve_path("FEEDBACK_FILE", FEEDBACK_FILE),
        favorites_file=_resolve_path("FAVORITES_FILE", FAVORITES_FILE),
        cache_file=_resolve_path("CACHE_FILE", CACHE_FILE),
        history_dir=_resolve_path("HISTORY_DIR", str(HISTORY_DIR)),
        scholar_service=ScholarService(_resolve_path("SCHOLARS_DATA_FILE", SCHOLARS_DATA_FILE)),
        keywords_loader=svc.load_keywords_config,
        keywords_saver=svc.save_keywords_config,
    )


def _scholar_service():
    from app.services.scholar_service import ScholarService

    return ScholarService(SCHOLARS_DATA_FILE)


# ---------------------------------------------------------------------------
# Snapshot helpers
# ---------------------------------------------------------------------------


def _get_snapshot_files():
    """Return the snapshot file mapping, respecting web_server patches for tests."""
    try:
        import web_server

        return web_server.SNAPSHOT_FILES
    except Exception:
        from app_paths import SNAPSHOT_FILES

        return SNAPSHOT_FILES


def _build_state_snapshot_inline():
    """Build a full state snapshot for export."""
    files = {}
    for key, path in _get_snapshot_files().items():
        if path.exists():
            files[key] = safe_load_json(str(path), {})
    return {
        "schema_version": "local-product-state-v1",
        "exported_at": datetime.now().isoformat(),
        "files": files,
        "state_store": _current_state_store().export_state(),
    }


def _build_recommendation_health(cached_papers=None):
    """Build recommendation health diagnostics (delegates to shared helper)."""
    from app.services.diagnostics_service import build_recommendation_health

    return build_recommendation_health(cached_papers, logger=logger)


def _load_history_paper_index():
    """Build {paper_id: paper_dict} index from history digest files."""
    from utils import load_history_paper_index

    return load_history_paper_index(HISTORY_DIR)


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


@bp.errorhandler(AppError)
def handle_app_error(error):
    return jsonify({"success": False, "error": str(error)}), error.status_code
