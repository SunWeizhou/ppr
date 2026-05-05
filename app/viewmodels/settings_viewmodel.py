"""Settings page viewmodel.

Migrated from web_server.py — settings_page, _render_settings_research.
"""

from __future__ import annotations

import os

from app.services.feedback_service import FeedbackService
from app.viewmodels.shared import assemble_page_context
from state_store import QUEUE_STATUS_VALUES


class SettingsViewModel:
    """Assembles template context for the Settings page."""

    def __init__(self, state_store):
        self._store = state_store
        self._feedback_service: FeedbackService | None = None

    # ── lazy feedback-service access ──────────────────────────────────────

    def _feedback(self) -> FeedbackService:
        if self._feedback_service is None:
            from app_paths import CACHE_DIR, HISTORY_DIR

            self._feedback_service = FeedbackService(
                self._store,
                feedback_file=str(CACHE_DIR / "user_feedback.json"),
                favorites_file=str(CACHE_DIR / "favorite_papers.json"),
                cache_file=str(CACHE_DIR / "paper_cache.json"),
                history_dir=str(HISTORY_DIR),
            )
        return self._feedback_service

    # ── queue helpers ─────────────────────────────────────────────────────

    def _queue_counts(self) -> dict[str, int]:
        counts: dict[str, int] = dict.fromkeys(QUEUE_STATUS_VALUES, 0)
        for item in self._store.list_queue_items():
            status = item.get("status")
            if status in counts:
                counts[status] += 1
        return counts

    # ── recommendation health ─────────────────────────────────────────────

    @staticmethod
    def _build_recommendation_health(cached_papers=None):
        try:
            from config_manager import get_config

            config = get_config()
            core_count = len(config.core_keywords)
            secondary_count = len(config.get_keywords_by_category("secondary"))
            zotero_path = os.path.expanduser(config._zotero.database_path or "")
            zotero_exists = bool(zotero_path and os.path.exists(zotero_path))
            scores = [
                float(paper.get("score", 0) or 0)
                for paper in (cached_papers or [])
            ]
            max_score = max(scores, default=0.0)
            low_signal_count = sum(1 for s in scores if s <= 0.7)
            return {
                "core_keyword_count": core_count,
                "secondary_keyword_count": secondary_count,
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
            return {
                "core_keyword_count": 0,
                "secondary_keyword_count": 0,
                "has_positive_profile": False,
                "zotero": {
                    "enabled": False,
                    "configured_path": "",
                    "path_exists": False,
                },
            }

    def _build_page_context(self, active_tab: str) -> dict:
        """Build the shared page context (replaces web_server._build_page_context)."""
        feedback = self._feedback().load_feedback()
        base = assemble_page_context(
            self._store, active_tab=active_tab, feedback=feedback
        )
        base["queue_counts"] = self._queue_counts()
        base["queue_status_values"] = QUEUE_STATUS_VALUES
        base["recommendation_health"] = self._build_recommendation_health()
        return base

    # ── public entry-point ────────────────────────────────────────────────

    def to_template_context(self, tab: str = "profile") -> dict:
        """Assemble the full Settings page context.
        Replaces web_server.settings_page + _render_settings_research."""
        # Backward compat: old "system" tab renamed to "diagnostics"
        if tab == "system":
            tab = "diagnostics"
        try:
            from config_manager import get_config

            config = get_config()
            core_keywords = [
                {"keyword": k, "weight": float(v)}
                for k, v in config.core_keywords.items()
            ]
            papers_per_day = config._settings.papers_per_day
            sources = {
                "arxiv_enabled": config._sources.arxiv_enabled,
                "journal_enabled": config._sources.journal_enabled,
                "scholar_enabled": config._sources.scholar_enabled,
                "lookback_days": config._sources.lookback_days,
            }
            zotero = {
                "enabled": config._zotero.enabled,
                "auto_detect": config._zotero.auto_detect,
                "database_path": config._zotero.database_path,
            }
            ai_config = config.get_ai_config()
        except Exception:
            core_keywords = []
            papers_per_day = 20
            sources = {
                "arxiv_enabled": True,
                "journal_enabled": True,
                "scholar_enabled": False,
                "lookback_days": 14,
            }
            zotero = {"enabled": True, "auto_detect": True, "database_path": ""}
            ai_config = {
                "provider": "none",
                "api_key": "",
                "base_url": "https://api.deepseek.com",
                "model": "deepseek-chat",
                "enabled": False,
            }

        page_context = self._build_page_context("settings")

        return {
            "title": "Settings - arXiv Recommender",
            "tab": tab,
            "core_keywords": core_keywords,
            "papers_per_day": papers_per_day,
            "sources": sources,
            "zotero": zotero,
            "ai_config": ai_config,
            **page_context,
        }
