"""Monitor page viewmodel.

Migrated from web_server.py — monitor_page, _render_track_research, _build_recent_hits.
"""

from __future__ import annotations

import json
import os

from state_store import QUEUE_STATUS_VALUES

from app.services.feedback_service import FeedbackService
from app.services.paper_utils import format_author_text, split_query_terms
from app.viewmodels.shared import assemble_page_context


class MonitorViewModel:
    """Assembles template context for the Monitor page."""

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

    # ── path helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _resolve_path(key: str) -> str:
        from app_paths import CACHE_DIR, PROJECT_ROOT

        mapping = {
            "CACHE_FILE": str(CACHE_DIR / "paper_cache.json"),
            "MY_SCHOLARS_FILE": str(PROJECT_ROOT / "my_scholars.json"),
        }
        return mapping[key]

    # ── small utils ──────────────────────────────────────────────────────

    @staticmethod
    def _safe_load_json(filepath: str, default=None):
        if default is None:
            default = {}
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, Exception):
            return default

    def _queue_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {status: 0 for status in QUEUE_STATUS_VALUES}
        for item in self._store.list_queue_items():
            status = item.get("status")
            if status in counts:
                counts[status] += 1
        return counts

    @staticmethod
    def _build_recommendation_health(cached_papers=None):
        try:
            from config_manager import get_config

            config = get_config()
            core_count = len(config.core_keywords)
            secondary_count = len(config.get_keywords_by_category("secondary"))
            theory_count = len(config.theory_keywords)
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
            return {
                "core_keyword_count": 0,
                "secondary_keyword_count": 0,
                "theory_keyword_count": 0,
                "has_positive_profile": False,
                "zotero": {
                    "enabled": False,
                    "configured_path": "",
                    "path_exists": False,
                },
            }

    def _build_page_context(self, active_tab: str) -> dict:
        feedback = self._feedback().load_feedback()
        base = assemble_page_context(
            self._store, active_tab=active_tab, feedback=feedback
        )
        base["queue_counts"] = self._queue_counts()
        base["queue_status_values"] = QUEUE_STATUS_VALUES
        base["recommendation_health"] = self._build_recommendation_health()
        return base

    # ── scholar helpers ───────────────────────────────────────────────────

    @staticmethod
    def _scholar_links(scholar: dict) -> list[dict]:
        links = []
        if scholar.get("google_scholar"):
            links.append({
                "label": "Google Scholar",
                "href": scholar["google_scholar"],
                "tone": "btn-brand",
            })
        if scholar.get("website"):
            links.append({
                "label": "个人主页",
                "href": scholar["website"],
                "tone": "btn-subtle",
            })
        if scholar.get("arxiv"):
            links.append({
                "label": "arXiv",
                "href": scholar["arxiv"],
                "tone": "btn-ghost",
            })
        return links

    @classmethod
    def _serialize_scholar(cls, scholar: dict) -> dict:
        item = dict(scholar)
        item["links"] = cls._scholar_links(scholar)
        return item

    def _load_my_scholars(self) -> dict:
        return self._safe_load_json(
            self._resolve_path("MY_SCHOLARS_FILE"), {"scholars": []}
        )

    # ── recent hits ───────────────────────────────────────────────────────

    def _build_recent_hits(self, scholars, journals, saved_searches) -> list[dict]:
        """Aggregate recent papers from unified subscription_hits and paper cache.
        Replaces web_server._build_recent_hits."""
        hits = []
        paper_cache = self._safe_load_json(self._resolve_path("CACHE_FILE"))

        # Read recent hits from the subscription_hits table (unified model)
        try:
            all_hits = self._store.list_subscription_hits(limit=50)
            hit_paper_ids: set[str] = set()
            for hit in all_hits:
                paper_id = hit.get("paper_id", "")
                if not paper_id or paper_id in hit_paper_ids:
                    continue
                hit_paper_ids.add(paper_id)

                # Get subscription info for source_type
                sub_id = hit.get("subscription_id")
                sub = self._store.get_subscription(sub_id) if sub_id else None
                source_type = sub.get("type", "hit") if sub else "hit"
                source_name = sub.get("name", "") if sub else ""

                # Look up paper details from paper cache
                paper_data = (
                    paper_cache.get(paper_id, {})
                    if isinstance(paper_cache, dict)
                    else {}
                )
                paper_entry = {
                    "id": paper_id,
                    "title": paper_data.get("title", paper_id),
                    "authors": paper_data.get("authors", ""),
                    "author_text": (
                        format_author_text(paper_data.get("authors", ""), paper_id)
                        if paper_data.get("authors")
                        else ""
                    ),
                    "summary": paper_data.get("abstract", "")
                    or paper_data.get("summary", ""),
                    "summary_short": (
                        paper_data.get("abstract", "")
                        or paper_data.get("summary", "")
                    )[:200],
                    "link": paper_data.get(
                        "link", f"https://arxiv.org/abs/{paper_id}"
                    ),
                    "score": paper_data.get("score", 0),
                    "source_type": source_type,
                    "source_name": source_name,
                    "hit_status": hit.get("status", "new"),
                    "hit_date": hit.get("hit_date", ""),
                }
                if "date" in paper_data:
                    paper_entry["date"] = paper_data["date"]
                hits.append(paper_entry)

                if len(hits) >= 30:
                    break
        except Exception:
            pass

        # Fallback: if no hits exist yet, try live search for saved_searches
        if not hits:
            try:
                from arxiv_recommender_v5 import search_by_keywords

                for search in saved_searches[:3]:
                    query_text = search.get("query_text", "")
                    if not query_text:
                        continue
                    try:
                        papers = search_by_keywords(
                            split_query_terms(query_text),
                            max_results=3,
                            days_back=30,
                        )
                        for paper in papers:
                            paper["source_type"] = "query"
                            hits.append(paper)
                    except Exception:
                        pass
            except ImportError:
                pass

        return hits

    # ── public entry-point ────────────────────────────────────────────────

    def to_template_context(self, tab: str = "authors") -> dict:
        """Assemble the full Monitor page context.
        Replaces web_server.monitor_page and merges _render_track_research."""
        from journal_tracker import (
            JournalTracker,
            LEGACY_USER_CONFIG_PATH,
            USER_PROFILE_PATH,
            load_update_log,
            should_check_for_updates,
        )

        page_context = self._build_page_context("monitor")

        # ── scholars ──
        my_scholars_data = self._load_my_scholars()
        my_scholars = [
            self._serialize_scholar(s)
            for s in my_scholars_data.get("scholars", [])
        ]

        # ── journal tracker ──
        preferred_config = (
            USER_PROFILE_PATH
            if USER_PROFILE_PATH.exists()
            else LEGACY_USER_CONFIG_PATH
        )
        tracker = JournalTracker(
            str(preferred_config) if preferred_config.exists() else None
        )
        update_log = load_update_log()
        journal_cards = []
        for journal in tracker.get_all_journals():
            should_check, update_reason = should_check_for_updates(journal["key"])
            journal_cards.append({
                **journal,
                "should_check": should_check,
                "update_reason": update_reason,
                "last_update": update_log.get(journal["key"], {}).get(
                    "last_check", "从未"
                ),
            })

        # ── recent hits ──
        recent_hits = []
        if tab == "recent-hits":
            recent_hits = self._build_recent_hits(
                my_scholars, journal_cards, page_context["all_saved_searches"]
            )

        # ── headline metrics ──
        headline_metrics = [
            {"label": "Followed Scholars", "value": len(my_scholars)},
            {"label": "Tracked Journals", "value": len(journal_cards)},
            {
                "label": "Collections",
                "value": len(page_context["all_collections"]),
            },
            {
                "label": "Saved Searches",
                "value": len(page_context["all_saved_searches"]),
            },
        ]

        # ── unified subscription counts ──
        unified_subs = self._store.list_subscriptions()
        unified_query_count = sum(
            1 for s in unified_subs if s.get("type") == "query"
        )
        unified_author_count = sum(
            1 for s in unified_subs if s.get("type") == "author"
        )
        unified_venue_count = sum(
            1 for s in unified_subs if s.get("type") == "venue"
        )
        total_hits = sum(
            s.get("latest_hit_count", 0) or 0 for s in unified_subs
        )

        return {
            "title": "Monitor - arXiv Recommender",
            "tab": tab,
            "headline_metrics": headline_metrics,
            "my_scholars": my_scholars,
            "journal_cards": journal_cards,
            "recent_hits": recent_hits,
            "unified_subs": unified_subs,
            "unified_query_count": unified_query_count,
            "unified_author_count": unified_author_count,
            "unified_venue_count": unified_venue_count,
            "total_subscription_hits": total_hits,
            **page_context,
        }
