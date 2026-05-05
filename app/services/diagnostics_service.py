"""Shared diagnostics helpers — consolidated from inbox_viewmodel and api/helpers."""

from __future__ import annotations

import logging
import os
from typing import Any


def build_recommendation_health(
    cached_papers: list[dict[str, Any]] | None = None,
    *,
    state_store: Any = None,
    logger: logging.Logger | None = None,
) -> dict[str, Any]:
    """Build recommendation health diagnostics dict.

    Args:
        cached_papers: Optional list of paper dicts (for score analysis).
        state_store: Reserved for future use (not currently consumed).
        logger: If provided, errors are logged at WARNING with exc_info=True.
                If None (the default), errors are silently swallowed and a
                zero-dict is returned — matching the viewmodel convention.
    """
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
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        low_signal_count = sum(1 for score in scores if score <= 0.7)

        recent_run_count = 0
        embedding_cache_count = 0
        feedback_model_auc = None
        if state_store is not None:
            try:
                recent_run_count = len(state_store.list_recommendation_dates(limit=7))
            except Exception:
                pass
            try:
                embeddings = state_store.get_all_embeddings_for_model(
                    config._settings.embedding_model
                )
                embedding_cache_count = len(embeddings) if embeddings else 0
            except Exception:
                pass
            try:
                fb = state_store.get_latest_feedback_model()
                if fb:
                    feedback_model_auc = fb.get("auc")
            except Exception:
                pass

        return {
            "core_keyword_count": core_count,
            "secondary_keyword_count": secondary_count,
            "theory_keyword_count": theory_count,
            "has_positive_profile": (core_count + secondary_count) > 0,
            "max_score": max_score,
            "avg_score": avg_score,
            "low_signal_count": low_signal_count,
            "recent_run_count": recent_run_count,
            "embedding_cache_count": embedding_cache_count,
            "feedback_model_auc": feedback_model_auc,
            "zotero": {
                "enabled": bool(config._zotero.enabled),
                "configured_path": config._zotero.database_path,
                "path_exists": zotero_exists,
                "auto_detect": bool(config._zotero.auto_detect),
            },
        }
    except Exception:
        if logger is not None:
            logger.warning("Could not build recommendation health", exc_info=True)
        return {
            "core_keyword_count": 0,
            "secondary_keyword_count": 0,
            "theory_keyword_count": 0,
            "has_positive_profile": False,
            "max_score": 0.0,
            "avg_score": 0.0,
            "low_signal_count": 0,
            "recent_run_count": 0,
            "embedding_cache_count": 0,
            "feedback_model_auc": None,
            "zotero": {"enabled": False, "configured_path": "", "path_exists": False},
        }
