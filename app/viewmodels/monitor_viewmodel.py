"""Monitor page viewmodel.

Migrated from web_server.py — monitor_page, _render_track_research, _build_recent_hits.
"""
from __future__ import annotations

import json
import os
from urllib.parse import urlencode

from app.services.feedback_service import FeedbackService
from app.services.paper_utils import format_author_text, split_query_terms
from app.services.workspace_service import WorkspaceService
from app.viewmodels.shared import assemble_page_context
from state_store import QUEUE_STATUS_VALUES


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
        from app_paths import CACHE_DIR

        mapping = {
            "CACHE_FILE": str(CACHE_DIR / "paper_cache.json"),
        }
        return mapping[key]

    # ── small utils ──────────────────────────────────────────────────────

    @staticmethod
    def _safe_load_json(filepath: str, default=None):
        if default is None:
            default = {}
        try:
            with open(filepath, encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, Exception):
            return default

    def _queue_counts(self) -> dict[str, int]:
        counts: dict[str, int] = dict.fromkeys(QUEUE_STATUS_VALUES, 0)
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

    # ── subscription-to-scholar conversion ──────────────────────────────────

    @classmethod
    def _subscription_to_scholar(cls, sub: dict) -> dict:
        payload = sub.get("payload_json") or {}
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except (TypeError, json.JSONDecodeError):
                payload = {}
        links = []
        if payload.get("google_scholar"):
            links.append({"label": "Google Scholar", "href": payload["google_scholar"], "tone": "btn-subtle"})
        if payload.get("website"):
            links.append({"label": "Website", "href": payload["website"], "tone": "btn-subtle"})
        if payload.get("arxiv"):
            links.append({"label": "arXiv", "href": payload["arxiv"], "tone": "btn-ghost"})
        return {
            "name": sub.get("name", ""),
            "id": sub.get("id"),
            "description": payload.get("description", ""),
            "affiliation": payload.get("affiliation", ""),
            "focus": payload.get("focus", ""),
            "links": links,
            "query_text": sub.get("query_text", ""),
        }

    @classmethod
    def _subscription_to_venue(cls, sub: dict) -> dict:
        payload = sub.get("payload_json") or {}
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except (TypeError, json.JSONDecodeError):
                payload = {}
        return {
            "key": sub.get("query_text", ""),
            "name": sub.get("name", ""),
            "should_check": True,
            "update_reason": "subscribed",
            "last_update": payload.get("last_check", "never"),
            "latest_hit_count": sub.get("latest_hit_count", 0) or 0,
        }

    # ── workspace and metadata decoration ──────────────────────────────────

    def _workspace_stats_for(self, research_question_id) -> dict:
        if not research_question_id:
            return {}
        try:
            return WorkspaceService(self._store).workspace_stats(
                int(research_question_id)
            )
        except Exception:
            return {}

    def _research_question_for(self, research_question_id):
        if not research_question_id:
            return None
        try:
            return self._store.get_research_question(int(research_question_id))
        except Exception:
            return None

    def _paper_metadata_for_hit(self, paper_id: str) -> dict:
        metadata = {}
        get_metadata = getattr(self._store, "get_paper_metadata", None)
        if callable(get_metadata):
            try:
                metadata = get_metadata(paper_id) or {}
            except Exception:
                metadata = {}

        paper_cache = self._safe_load_json(self._resolve_path("CACHE_FILE"))
        if isinstance(paper_cache, dict):
            cached = paper_cache.get(paper_id, {}) or {}
            metadata = {**cached, **metadata}

        get_paper = getattr(self._store, "get_paper", None)
        if callable(get_paper):
            try:
                paper_row = get_paper(paper_id)
            except Exception:
                paper_row = None
            if paper_row:
                if paper_row.get("title"):
                    metadata.setdefault("title", paper_row["title"])
                authors_val = (
                    paper_row.get("authors_json") or paper_row.get("authors")
                )
                if authors_val:
                    metadata.setdefault("authors", authors_val)
                if paper_row.get("abstract"):
                    metadata.setdefault("abstract", paper_row["abstract"])
                if paper_row.get("source_url"):
                    metadata.setdefault("link", paper_row["source_url"])
                if paper_row.get("published_at"):
                    metadata.setdefault("date", paper_row["published_at"])
        return metadata

    @staticmethod
    def _detail_url(paper_id: str, research_question_id=None) -> str:
        if not research_question_id:
            return f"/papers/{paper_id}"
        return f"/papers/{paper_id}?{urlencode({'research_question_id': research_question_id})}"

    def _hit_card(self, hit: dict, subscription: dict | None = None) -> dict:
        paper_id = hit.get("paper_id", "")
        metadata = self._paper_metadata_for_hit(paper_id)
        research_question_id = (
            subscription or {}
        ).get("research_question_id")
        authors = metadata.get("authors", "")
        return {
            "id": hit.get("id"),
            "paper_id": paper_id,
            "title": metadata.get("title") or paper_id,
            "authors": authors,
            "author_text": format_author_text(authors) if authors else "",
            "summary": metadata.get("abstract") or metadata.get("summary", ""),
            "summary_short": (
                metadata.get("abstract") or metadata.get("summary", "")
            )[:200],
            "link": metadata.get("link", f"https://arxiv.org/abs/{paper_id}"),
            "score": metadata.get("score", 0),
            "categories": metadata.get("categories", []),
            "matched_reason": hit.get("matched_reason", ""),
            "hit_status": hit.get("status", "new"),
            "hit_date": hit.get("hit_date", ""),
            "detail_url": self._detail_url(paper_id, research_question_id),
        }

    def _decorate_subscription(
        self,
        sub: dict,
        hits_by_subscription: dict[int, list[dict]],
    ) -> dict:
        item = dict(sub)
        payload = item.get("payload_json") or {}
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except (TypeError, json.JSONDecodeError):
                payload = {}
        item["_raw"] = dict(sub)
        item["payload"] = payload
        item["description"] = payload.get("description", "") or payload.get("focus", "")
        item["affiliation"] = payload.get("affiliation", "")
        item["focus"] = payload.get("focus", "")
        item["venue_type"] = payload.get("venue_type", item.get("type", ""))
        item["homepage_url"] = payload.get("homepage_url", "")
        item["last_checked_at"] = item.get("last_checked_at") or ""
        item["research_question"] = self._research_question_for(
            item.get("research_question_id")
        )
        item["workspace_stats"] = self._workspace_stats_for(
            item.get("research_question_id")
        )
        item["recent_hits"] = [
            self._hit_card(hit, item)
            for hit in hits_by_subscription.get(item["id"], [])[:5]
        ]
        return item

    # ── recent hits (no-network) ───────────────────────────────────────────

    def _subscription_hits_by_subscription(self, limit: int = 100) -> dict[int, list[dict]]:
        grouped: dict[int, list[dict]] = {}
        try:
            for hit in self._store.list_subscription_hits(limit=limit):
                sub_id = hit.get("subscription_id")
                if sub_id is None:
                    continue
                grouped.setdefault(sub_id, []).append(hit)
        except Exception:
            return {}
        return grouped

    def _build_recent_hits(self, subscriptions: list[dict]) -> list[dict]:
        hits = []
        seen: set[str] = set()
        for sub in subscriptions:
            for hit in sub.get("recent_hits", []):
                paper_id = hit.get("paper_id")
                if not paper_id or paper_id in seen:
                    continue
                seen.add(paper_id)
                entry = dict(hit)
                entry["source_type"] = sub.get("type", "hit")
                entry["source_name"] = sub.get("name", "")
                hits.append(entry)
                if len(hits) >= 30:
                    return hits
        return hits

    # ── public entry-point ────────────────────────────────────────────────

    def to_template_context(self, tab: str = "recent-hits") -> dict:
        """Assemble the full Monitor page context.
        Replaces web_server.monitor_page and merges _render_track_research."""

        page_context = self._build_page_context("monitor")

        # ── unified subscription enrichment ──
        unified_subs = self._store.list_subscriptions()
        hits_by_subscription = self._subscription_hits_by_subscription()
        decorated_subs = [
            self._decorate_subscription(sub, hits_by_subscription)
            for sub in unified_subs
        ]

        # ── scholars from unified subscriptions ──
        author_subs = [s for s in decorated_subs if s.get("type") == "author"]
        my_scholars = [
            self._subscription_to_scholar(s)
            for s in author_subs
        ]

        # ── venues from unified subscriptions ──
        venue_subs = [s for s in decorated_subs if s.get("type") == "venue"]
        journal_cards = [
            self._subscription_to_venue(s)
            for s in venue_subs
        ]

        # ── recent hits ──
        recent_hits = []
        if tab == "recent-hits":
            recent_hits = self._build_recent_hits(decorated_subs)

        # ── headline metrics ──
        headline_metrics = [
            {"label": "Followed Scholars", "value": len(my_scholars)},
            {"label": "Tracked Venues", "value": len(venue_subs)},
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
        unified_query_count = sum(
            1 for s in decorated_subs if s.get("type") == "query"
        )
        unified_author_count = sum(
            1 for s in decorated_subs if s.get("type") == "author"
        )
        unified_venue_count = sum(
            1 for s in decorated_subs if s.get("type") == "venue"
        )
        total_hits = sum(
            s.get("latest_hit_count", 0) or 0 for s in decorated_subs
        )

        # Filtered lists for template section rendering
        query_subs = [s for s in decorated_subs if s.get("type") == "query"]

        return {
            "title": "Monitor - Agent Literature Research Assistant",
            "tab": tab,
            "headline_metrics": headline_metrics,
            "my_scholars": my_scholars,
            "journal_cards": journal_cards,
            "recent_hits": recent_hits,
            "unified_subs": decorated_subs,
            "query_subs": query_subs,
            "author_subs": author_subs,
            "venue_subs": venue_subs,
            "unified_query_count": unified_query_count,
            "unified_author_count": unified_author_count,
            "unified_venue_count": unified_venue_count,
            "total_subscription_hits": total_hits,
            **page_context,
        }
