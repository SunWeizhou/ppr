"""Shared utilities for API route modules.

Provides _current_state_store() (with P2-C app config injection),
helper factory functions, error handlers, and module-level constants.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime

from flask import jsonify

from app.services.ai_analysis_service import AIAnalysisService
from app.services.ai_providers import build_ai_provider_from_env
from app.services.errors import AppError
from app.services.queue_service import QueueService
from app.viewmodels.shared import serialize_collection, serialize_saved_search, serialize_job  # noqa: F401
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
MY_SCHOLARS_FILE = str(PROJECT_ROOT / "my_scholars.json")


def _package_attr(name: str):
    """Return *name* from the api package, or ``None``."""
    pkg = sys.modules.get(__package__)
    if pkg is not None:
        return getattr(pkg, name, None)
    return None


# ---------------------------------------------------------------------------
# State store resolution — P2-C: Flask app config preferred over module globals
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
        scholar_service=ScholarService(_resolve_path("MY_SCHOLARS_FILE", MY_SCHOLARS_FILE)),
        keywords_loader=svc.load_keywords_config,
        keywords_saver=svc.save_keywords_config,
    )


def _scholar_service():
    from app.services.scholar_service import ScholarService

    return ScholarService(MY_SCHOLARS_FILE)


# ---------------------------------------------------------------------------
# Snapshot helpers
# ---------------------------------------------------------------------------

SNAPSHOT_FILES = {
    "user_profile": PROJECT_ROOT / "user_profile.json",
    "user_config": PROJECT_ROOT / "user_config.json",
    "keywords_config": PROJECT_ROOT / "keywords_config.json",
    "user_feedback": CACHE_DIR / "user_feedback.json",
    "favorite_papers": CACHE_DIR / "favorite_papers.json",
    "paper_cache": CACHE_DIR / "paper_cache.json",
    "journal_update_log": CACHE_DIR / "journal_update_log.json",
}


def _get_snapshot_files():
    """Return the snapshot file mapping, respecting web_server patches for tests."""
    try:
        import web_server

        return web_server.SNAPSHOT_FILES
    except Exception:
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
    """Build recommendation health diagnostics."""
    try:
        from config_manager import get_config

        config = get_config()
        core_count = len(config.core_keywords)
        secondary_count = len(config.get_keywords_by_category("secondary"))
        theory_count = len(config.theory_keywords)
        zotero_path = os.path.expanduser(config._zotero.database_path or "")
        zotero_exists = bool(zotero_path and os.path.exists(zotero_path))
        scores = [float(paper.get("score", 0) or 0) for paper in (cached_papers or [])]
        max_score = max(scores, default=0.0)
        low_signal_count = sum(1 for score in scores if score <= 0.7)
        return {
            "core_keyword_count": core_count,
            "secondary_keyword_count": secondary_count,
            "theory_keyword_count": theory_count,
            "has_positive_profile": (core_count + secondary_count) > 0,
            "max_score": max_score,
            "low_signal_count": low_signal_count,
            "zotero": {
                "enabled": bool(config._zotero.enabled),
                "configured_path": config._zotero.database_path,
                "path_exists": zotero_exists,
                "auto_detect": bool(config._zotero.auto_detect),
            },
        }
    except Exception:
        logger.warning("Could not build recommendation health", exc_info=True)
        return {
            "core_keyword_count": 0,
            "secondary_keyword_count": 0,
            "theory_keyword_count": 0,
            "has_positive_profile": False,
            "zotero": {"enabled": False, "configured_path": "", "path_exists": False},
        }


def _load_history_paper_index():
    """Lightweight inline version of _load_history_paper_index for related-paper lookups."""
    all_papers = {}
    hist_dir = str(HISTORY_DIR)
    if not os.path.exists(hist_dir):
        return all_papers
    for fname in sorted(os.listdir(hist_dir)):
        if not (fname.startswith("digest_") and fname.endswith(".md")):
            continue
        filepath = os.path.join(hist_dir, fname)
        try:
            from utils import parse_markdown_digest_cached

            papers, _ = parse_markdown_digest_cached(filepath)
        except Exception:
            continue
        for paper in papers:
            paper_id = paper.get("id")
            if not paper_id or paper_id in all_papers:
                continue
            item = dict(paper)
            item["date"] = fname.replace("digest_", "").replace(".md", "")
            all_papers[paper_id] = item
    return all_papers


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


@bp.errorhandler(AppError)
def handle_app_error(error):
    return jsonify({"success": False, "error": str(error)}), error.status_code
