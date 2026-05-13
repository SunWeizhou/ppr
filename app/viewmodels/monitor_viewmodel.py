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
from app.data._constants import QUEUE_STATUS_VALUES


class MonitorViewModel:
    """Assembles template context for the Monitor page."""

    PLACEHOLDER_VALUES = {
        "stable identity",
        "test paper title",
        "browser smoke paper",
        "hit test",
        "hits list",
        "query a",
        "query b",
        "sub a",
        "sub b",
        "first paper",
        "json fields paper",
        "fixture-paper",
        "p1",
        "p2",
        "a",
        "b",
        "[]",
    }

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

    @classmethod
    def _looks_like_fixture_value(cls, value) -> bool:
        if value is None:
            return False
        text = str(value).strip().lower()
        if not text:
            return False
        if text in cls.PLACEHOLDER_VALUES:
            return True
        return any(token in text for token in (
            "test paper title",
            "stable identity",
            "browser smoke paper",
            "fixture",
        ))

    @classmethod
    def _looks_like_fixture_subscription(cls, sub: dict) -> bool:
        return any(
            cls._looks_like_fixture_value(sub.get(key))
            for key in ("name", "query_text")
        )

    @classmethod
    def _looks_like_fixture_hit(cls, hit: dict) -> bool:
        return any(
            cls._looks_like_fixture_value(hit.get(key))
            for key in ("paper_id", "title", "matched_reason", "author_text")
        )

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
        """Resolve paper metadata from all available local sources.

        Resolution order (canonicalises *paper_id* at the start):
          1. SQLite paper_metadata table
          2. paper_cache.json on disk (handles versioned-key aliases)
          3. Recent recommendation runs
          4. History markdown digest files
          5. Graceful fallback

        The method aligns with ``PaperViewModel._find_paper_data`` so that
        Watch hit enrichment uses the same resolution chain as Paper Detail.
        """
        from app.data._constants import canonical_paper_id as _canonical_paper_id

        canonical_id = _canonical_paper_id(paper_id)
        result: dict = {}

        # -- 1. paper_metadata table (already canonicalises internally) ------
        get_metadata = getattr(self._store, "get_paper_metadata", None)
        if callable(get_metadata):
            try:
                row = get_metadata(canonical_id) or {}
                if row.get("title"):
                    result = dict(row)
            except Exception:
                pass

        # -- 2. paper_cache.json ----------------------------------------------
        if not result.get("title"):
            try:
                cache = self._safe_load_json(
                    self._resolve_path("CACHE_FILE")
                )
                if isinstance(cache, dict):
                    entry: dict | None = None
                    # 2a. Direct key lookup
                    raw = cache.get(canonical_id)
                    if isinstance(raw, dict) and raw.get("title"):
                        entry = raw
                    # 2b. Scan for versioned-key aliases
                    if not entry:
                        for k, v in cache.items():
                            if (
                                isinstance(v, dict)
                                and v.get("title")
                                and _canonical_paper_id(k) == canonical_id
                            ):
                                entry = v
                                break
                    if entry:
                        # Merge with existing result — result keys win
                        result = {**entry, **result}
            except Exception:
                pass

        # -- 3. Recommendation runs -------------------------------------------
        if not result.get("title"):
            try:
                rec = self._find_paper_in_recommendations(canonical_id)
                if rec and rec.get("title"):
                    result.setdefault("title", rec["title"])
                    authors = rec.get("authors") or rec.get("authors_json")
                    if authors:
                        result.setdefault("authors", authors)
                    if rec.get("abstract"):
                        result.setdefault("abstract", rec.get("abstract"))
                    link = rec.get("source_url") or rec.get("link")
                    if link:
                        result.setdefault("link", link)
                    if rec.get("published_at") or rec.get("date"):
                        result.setdefault("date", rec.get("published_at") or rec.get("date"))
                    cats = rec.get("categories")
                    if cats:
                        result.setdefault("categories", cats)
            except Exception:
                pass

        # -- 4. History markdown digest files ---------------------------------
        if not result.get("title"):
            try:
                from pathlib import Path
                from app_paths import HISTORY_DIR
                import os
                from app.viewmodels.inbox_viewmodel import InboxViewModel

                if os.path.exists(str(HISTORY_DIR)):
                    for fname in sorted(
                        os.listdir(str(HISTORY_DIR)), reverse=True
                    ):
                        if not fname.startswith("digest_") or not fname.endswith(".md"):
                            continue
                        filepath = os.path.join(str(HISTORY_DIR), fname)
                        papers, _ = InboxViewModel.parse_digest(
                            filepath, use_cache=False
                        )
                        for p in papers:
                            if _canonical_paper_id(p.get("id") or "") == canonical_id:
                                if p.get("title"):
                                    result.setdefault("title", p["title"])
                                    result.setdefault("authors", p.get("authors"))
                                    result.setdefault("abstract", p.get("abstract") or p.get("summary"))
                                    result.setdefault("link", p.get("link") or p.get("source_url"))
                                    result.setdefault("categories", p.get("categories"))
                                    break
                        if result.get("title"):
                            break
            except Exception:
                pass

        return result

    def _find_paper_in_recommendations(self, paper_id: str) -> dict | None:
        """Search recent recommendation runs for paper metadata."""
        from app.data._constants import canonical_paper_id as _canonical_paper_id
        canonical = _canonical_paper_id(paper_id)
        try:
            recent_runs = self._store.list_recommendation_runs(limit=10)
            for run in recent_runs:
                items = self._store.get_recommendation_items(run["run_id"])
                for item in items:
                    stored_id = _canonical_paper_id(item.get("paper_id") or item.get("id") or "")
                    if stored_id == canonical:
                        return item
        except Exception:
            pass
        return None

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

    @staticmethod
    def _source_health_for(item: dict) -> dict:
        if not item.get("enabled", True):
            return {
                "state": "paused",
                "label": "Paused",
                "message": "This watch is not checking for new hits.",
            }
        if item.get("last_checked_at"):
            return {
                "state": "healthy",
                "label": "Healthy",
                "message": "Last check completed.",
            }
        return {
            "state": "ready",
            "label": "Ready",
            "message": "This watch has not checked yet.",
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
        raw = item.get("last_checked_at")
        if raw is None or str(raw).strip().lower() in ("none", ""):
            item["last_checked_at"] = ""
        else:
            item["last_checked_at"] = str(raw)
        item["research_question"] = self._research_question_for(
            item.get("research_question_id")
        )
        item["workspace_stats"] = self._workspace_stats_for(
            item.get("research_question_id")
        )
        recent_hits = []
        for hit in hits_by_subscription.get(item["id"], [])[:8]:
            card = self._hit_card(hit, item)
            if not self._looks_like_fixture_hit(card):
                recent_hits.append(card)
            if len(recent_hits) >= 5:
                break
        item["recent_hits"] = recent_hits
        item["source_health"] = self._source_health_for(item)
        item["available_hit_actions"] = [
            "Preview",
            "Send to Reading",
            "Ignore",
            "Create collection",
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

        page_context = self._build_page_context("subscriptions")

        # ── unified subscription enrichment ──
        unified_subs = self._store.list_subscriptions()
        hits_by_subscription = self._subscription_hits_by_subscription()
        decorated_subs = [
            self._decorate_subscription(sub, hits_by_subscription)
            for sub in unified_subs
            if not self._looks_like_fixture_subscription(sub)
        ]

        # ── scholars from unified subscriptions ──
        author_subs = [s for s in decorated_subs if s.get("type") == "author"]
        my_scholars = [
            self._subscription_to_scholar(s)
            for s in author_subs
        ]

        # ── venues split into journals and conferences ──
        venue_subs = [s for s in decorated_subs if s.get("type") == "venue"]
        journal_subs = [s for s in venue_subs if s.get("venue_type") == "journal" or s.get("venue_type") == "venue"]
        conference_subs = [s for s in venue_subs if s.get("venue_type") == "conference"]
        journal_cards = [
            self._subscription_to_venue(s)
            for s in venue_subs
        ]

        # ── fields from unified subscriptions ──
        field_subs = [s for s in decorated_subs if s.get("type") == "field"]

        # ── recent hits ──
        recent_hits = []
        if tab == "recent-hits":
            recent_hits = self._build_recent_hits(decorated_subs)

        # ── headline metrics ──
        headline_metrics = [
            {"label": "Followed Scholars", "value": len(my_scholars)},
            {"label": "Tracked Journals", "value": len(journal_subs)},
            {"label": "Tracked Conferences", "value": len(conference_subs)},
            {
                "label": "Collections",
                "value": len(page_context["all_collections"]),
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
            "title": "Subscriptions - Paper Agent",
            "tab": tab,
            "headline_metrics": headline_metrics,
            "my_scholars": my_scholars,
            "journal_cards": journal_cards,
            "recent_hits": recent_hits,
            "unified_subs": decorated_subs,
            "query_subs": query_subs,
            "author_subs": author_subs,
            "journal_subs": journal_subs,
            "conference_subs": conference_subs,
            "field_subs": field_subs,
            "unified_query_count": unified_query_count,
            "unified_author_count": unified_author_count,
            "unified_venue_count": unified_venue_count,
            "total_subscription_hits": total_hits,
            **page_context,
        }
