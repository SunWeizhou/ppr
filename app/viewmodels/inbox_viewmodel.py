"""Inbox page viewmodel — home, date view, and generating states."""

from __future__ import annotations

import contextlib
import json
import os
import re
import threading
from datetime import datetime, timedelta
from typing import Optional

from app.services.feedback_service import FeedbackService
from app.services.paper_utils import (
    extract_primary_author,
    format_author_text,
    generate_relevance_html,
    normalize_queue_status,
    status_class,
)
from app.viewmodels.shared import assemble_page_context
from app_paths import CACHE_DIR, HISTORY_DIR, PROJECT_ROOT
from app.data._constants import QUEUE_STATUS_VALUES
from utils import CATEGORY_NAMES, count_keyword, parse_markdown_digest

# ---------------------------------------------------------------------------
# Per-process digest cache (avoids re-parsing the same file repeatedly)
# ---------------------------------------------------------------------------
_history_cache: dict = {}  # {date: (papers, keywords, timestamp)}
_HISTORY_CACHE_TTL = 300  # 5 minutes — kept short so fresh data appears quickly


class InboxViewModel:
    """Build template contexts for the inbox / home research page."""

    def __init__(self, state_store):
        self._store = state_store
        self._feedback_service: FeedbackService | None = None

    # ==================================================================
    # Public API — template contexts
    # ==================================================================

    def load_feedback(self) -> dict:
        """Return canonical user feedback (likes + dislikes)."""
        return self._get_feedback_service().load_feedback()

    def to_template_context(
        self,
        date: str,
        papers: list,
        keywords: list,
        dates: list,
        prev_date: str | None,
        next_date: str | None,
        feedback: dict,
    ) -> dict:
        """Build the full template context for ``today.html``.

        Corresponds to the combined logic of ``_render_home_research()`` and
        ``_decorate_home_papers()`` in web_server.py.

        Option C: only untriaged papers shown by default; filters removed.
        """
        keywords_config = self._load_keywords_config()
        today_matched_keywords = self._extract_today_keywords(papers, keywords_config)
        is_today = date == datetime.now().strftime("%Y-%m-%d")

        page_ctx = self._build_page_context(active_tab="inbox")
        decorated = self._decorate_home_papers(papers, feedback)

        # Option C: filter to untriaged papers only
        untriaged_papers = [
            p for p in decorated
            if not p.get("is_liked") and not p.get("is_disliked") and not p.get("queue_status")
        ]

        headline_metrics = [
            {"label": "Today's Papers", "value": len(decorated)},
            {"label": "Liked", "value": page_ctx["liked_count"]},
            {"label": "Queue Total", "value": sum(page_ctx["queue_counts"].values())},
            {
                "label": "Top Score",
                "value": f"{max((p.get('score', 0) for p in decorated), default=0):.1f}",
            },
        ]

        context = {
            "title": "Today - Paper Agent",
            "date": date,
            "today": datetime.now().strftime("%Y-%m-%d"),
            "is_today": is_today,
            "hero_keywords": today_matched_keywords or keywords[:8],
            "daily_themes": keywords[:10],
            "matched_keyword_count": len(today_matched_keywords),
            "papers": decorated,
            "untriaged_papers": untriaged_papers,
            "date_cards": self._build_date_cards(date, set(dates)),
            "prev_date": prev_date,
            "next_date": next_date,
            "headline_metrics": headline_metrics,
        }
        context.update(page_ctx)
        return context

    def to_generating_context(self) -> dict:
        """Build page context for ``generating.html``."""
        context = assemble_page_context(self._store, active_tab="inbox")
        context["queue_counts"] = self._queue_counts()
        context["queue_status_values"] = QUEUE_STATUS_VALUES
        context["title"] = "Generating Recommendations - Paper Agent"
        return context

    def to_no_data_html(self, date: str) -> str:
        """Return inline HTML for a date that has no recommendation data."""
        safe_date = str(date).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return (
            '<html><body style="font-family:sans-serif;padding:40px;background:#1a1a2e;color:#fff;">'
            f"<h1>{safe_date} - No Data</h1>"
            '<p><a href="/" style="color:#00d4ff">Back to Today</a></p>'
            "</body></html>"
        )

    # ==================================================================
    # Public API — data helpers
    # ==================================================================

    @staticmethod
    def get_available_dates() -> list[str]:
        """Return sorted list of available dates (newest first).

        Prefers SQLite recommendation runs, falls back to history digests.
        """
        from state_store import get_state_store
        try:
            store = get_state_store()
            sqlite_dates = store.list_recommendation_dates(limit=60, trigger_source="auto_homepage")
            if sqlite_dates:
                return sqlite_dates
        except Exception:
            pass

        # Fallback: scan history digest files
        if not os.path.exists(HISTORY_DIR):
            return []
        dates = []
        for f in os.listdir(HISTORY_DIR):
            if f.startswith("digest_") and f.endswith(".md"):
                dates.append(f.replace("digest_", "").replace(".md", ""))
        return sorted(dates, reverse=True)

    def load_papers_from_sqlite(self, date: str) -> tuple:
        """Load recommendation papers and themes from SQLite for a given date.

        Returns ``(papers, themes)`` where *papers* is a list of paper dicts
        (with ``paper_id`` normalised to ``id``) and *themes* is a list of
        keyword strings, or ``(None, None)`` if the date has no SQLite run.
        """
        try:
            run = self._store.get_recommendation_run_by_date(date, trigger_source="auto_homepage")
            if run:
                items = self._store.get_recommendation_items(run["run_id"])
                if items:
                    # Normalise: make ``id`` the arxiv paper ID (mirrors markdown path)
                    for item in items:
                        item["id"] = item["paper_id"]
                        del item["paper_id"]

                    # Enrich each paper with data from the papers table when available
                    try:
                        list_papers = getattr(self._store, 'list_papers_by_ids', None)
                        if callable(list_papers):
                            paper_ids = [item["id"] for item in items if item.get("id")]
                            if paper_ids:
                                enriched_map = {p["paper_id"]: p for p in list_papers(paper_ids)}
                                for item in items:
                                    ep = enriched_map.get(item.get("id"))
                                    if ep:
                                        for key in ('pdf_url', 'source_url', 'source',
                                                    'published_at', 'updated_at', 'abstract'):
                                            if ep.get(key) and (key not in item or not item.get(key)):
                                                item[key] = ep[key]
                                        # Fallback: if source_url exists but link is empty, set link from source_url
                                        if ep.get('source_url') and not item.get('link'):
                                            item['link'] = ep['source_url']
                    except Exception:
                        pass

                    # Load themes from the run record
                    try:
                        themes = json.loads(run.get("themes_json", "[]"))
                    except (TypeError, json.JSONDecodeError):
                        themes = []
                    return items, themes
        except Exception:
            pass
        return None, None

    @staticmethod
    def parse_digest(filepath: str, use_cache: bool = True):
        """Parse a markdown digest file, returning ``(papers, keywords)``."""
        global _history_cache
        import time

        date_match = re.search(r"digest_(\d{4}-\d{2}-\d{2})", filepath)
        cache_key = date_match.group(1) if date_match else filepath
        current_time = time.time()

        if use_cache and cache_key in _history_cache:
            cached_papers, cached_keywords, cached_time = _history_cache[cache_key]
            try:
                file_mtime = os.path.getmtime(filepath)
                if cached_time >= file_mtime and (current_time - cached_time) < _HISTORY_CACHE_TTL:
                    return cached_papers, cached_keywords
            except OSError:
                pass

        papers, keywords = parse_markdown_digest(filepath)

        if use_cache and papers:
            _history_cache[cache_key] = (papers, keywords, current_time)

        return papers, keywords

    @staticmethod
    def build_date_nav(date: str, dates: list[str]):
        """Return ``(prev_date, next_date)`` for the given date in the list."""
        prev_date = next_date = None
        if date in dates:
            idx = dates.index(date)
            if idx + 1 < len(dates):
                prev_date = dates[idx + 1]
            if idx > 0:
                next_date = dates[idx - 1]
        return prev_date, next_date

    def start_background_generation(self) -> str | None:
        """Start a background pipeline run; returns the job *run_id*.

        No-op if a generation is already running (checked via StateStore).
        """
        if self._store.has_running_job("daily_recommendation"):
            job = self._store.get_latest_job("daily_recommendation")
            return job["run_id"] if job else None

        job = self._store.create_job(
            "daily_recommendation",
            trigger_source="auto_homepage",
            payload={"force_refresh": False, "mode": "background_generation"},
            status="queued",
        )

        thread = threading.Thread(
            target=self._run_pipeline_background,
            args=(job["run_id"], False),
            daemon=True,
        )
        thread.start()
        return job["run_id"]

    # ==================================================================
    # Internal — page context / counts
    # ==================================================================

    def _get_feedback_service(self) -> FeedbackService:
        if self._feedback_service is None:
            self._feedback_service = FeedbackService(
                self._store,
                feedback_file=str(CACHE_DIR / "user_feedback.json"),
                favorites_file=str(CACHE_DIR / "favorite_papers.json"),
                cache_file=str(CACHE_DIR / "paper_cache.json"),
                history_dir=str(HISTORY_DIR),
            )
        return self._feedback_service

    def _queue_counts(self) -> dict:
        counts = dict.fromkeys(QUEUE_STATUS_VALUES, 0)
        for item in self._store.list_queue_items():
            status = item.get("status")
            if status in counts:
                counts[status] += 1
        return counts

    def _queue_map(self) -> dict:
        return {
            item.get("paper_id"): normalize_queue_status(item.get("status"))
            for item in self._store.list_queue_items()
        }

    def _build_page_context(self, active_tab: str) -> dict:
        feedback = self.load_feedback()
        base = assemble_page_context(self._store, active_tab=active_tab, feedback=feedback)
        base["queue_counts"] = self._queue_counts()
        base["queue_status_values"] = QUEUE_STATUS_VALUES
        base["recommendation_health"] = self._build_recommendation_health()
        return base

    # ==================================================================
    # Internal — date cards / keywords
    # ==================================================================

    def _build_date_cards(self, current_date: str, available_dates: set[str]) -> list[dict]:
        today_str = datetime.now().strftime("%Y-%m-%d")
        cards = []
        try:
            current_dt = datetime.strptime(current_date, "%Y-%m-%d")
        except ValueError:
            return cards
        for offset in range(-5, 6):
            dt = current_dt + timedelta(days=offset)
            raw_date = dt.strftime("%Y-%m-%d")
            cards.append({
                "date": raw_date,
                "day": dt.strftime("%d"),
                "month": dt.strftime("%b").upper(),
                "weekday": dt.strftime("%a"),
                "active": raw_date == current_date,
                "is_today": raw_date == today_str,
                "has_data": raw_date in available_dates,
            })
        return cards

    def _load_keywords_config(self) -> dict:
        try:
            from config_manager import get_config

            cm = get_config()
            return {
                "core_topics": cm.core_keywords,
                "secondary_topics": cm.get_keywords_by_category("secondary"),
                "theory_keywords": cm._config.get("theory_keywords", []),
                "demote_topics": cm.demote_keywords,
                "dislike_topics": list(cm.dislike_keywords.keys()),
            }
        except Exception:
            return {
                "core_topics": {},
                "secondary_topics": {},
                "theory_keywords": [],
                "demote_topics": {},
                "dislike_topics": [],
            }

    def _extract_today_keywords(self, papers: list, keywords_config: dict) -> list[str]:
        matched = []
        core_topics = keywords_config.get("core_topics", {})
        secondary_topics = keywords_config.get("secondary_topics", {})
        theory_keywords = keywords_config.get("theory_keywords", [])

        all_keywords = list(core_topics.keys()) + list(secondary_topics.keys()) + theory_keywords

        for paper in papers[:20]:
            text = (
                paper.get("title", "")
                + " "
                + paper.get("summary", "")
                + " "
                + paper.get("abstract", "")
            )
            for kw in all_keywords:
                if count_keyword(text, kw) > 0 and kw not in matched:
                    matched.append(kw)

        return matched[:10]

    # ==================================================================
    # Internal — paper decoration
    # ==================================================================

    def _load_user_profile_for_reason(self) -> dict:
        """Load a minimal user-profile dict for the recommendation reason builder."""
        profile: dict = {"core_keywords": {}, "secondary_keywords": {}, "saved_searches": []}
        try:
            from config_manager import get_config

            config = get_config()
            profile["core_keywords"] = config.core_keywords
            profile["secondary_keywords"] = config.get_keywords_by_category("secondary")
        except Exception:
            pass
        with contextlib.suppress(Exception):
            profile["saved_searches"] = self._store.list_saved_searches()
        return profile

    def _decorate_home_papers(self, papers: list, feedback: dict) -> list:
        queue_map = self._queue_map()
        decorated = []

        rec_profile = self._load_user_profile_for_reason()
        rec_context = {
            "feedback": feedback,
            "saved_searches": rec_profile.get("saved_searches", []),
        }

        for idx, paper in enumerate(papers, start=1):
            item = dict(paper)
            item["rank"] = idx
            item["is_liked"] = item.get("id") in feedback.get("liked", [])
            item["is_disliked"] = item.get("id") in feedback.get("disliked", [])
            item["queue_status"] = queue_map.get(item.get("id"))
            item["queue_status_class"] = status_class(item["queue_status"])

            try:
                from app.services.scoring_service import build_recommendation_reason

                rec_reason = build_recommendation_reason(
                    item, user_profile=rec_profile, run_context=rec_context
                )
                item["recommendation_reason"] = rec_reason
                item["reason_summary"] = rec_reason.get("reason_summary", "")
            except Exception:
                rec_reason = {}
                item["recommendation_reason"] = {}
                item["reason_summary"] = ""
                item["source_chips"] = []

            # Build the structured 5-group recommendation reason blocks
            zotero_sim = rec_reason.get("zotero_similarity", 0) if isinstance(rec_reason, dict) else 0
            sim_count = 1 if (isinstance(zotero_sim, (int, float)) and zotero_sim > 0) else 0
            item["recommendation_reason_blocks"] = [
                {
                    "label": "Matched Topics",
                    "items": rec_reason.get("matched_topics", []) if isinstance(rec_reason, dict) else [],
                    "natural_text": "",
                },
                {
                    "label": "Matched Subscriptions",
                    "items": rec_reason.get("matched_subscriptions", []) if isinstance(rec_reason, dict) else [],
                    "natural_text": "",
                },
                {
                    "label": "Zotero Similarity",
                    "items": [],
                    "natural_text": "Semantically similar to papers in your Zotero library" if sim_count else "",
                },
                {
                    "label": "Feedback Signals",
                    "items": rec_reason.get("feedback_signals", []) if isinstance(rec_reason, dict) else [],
                    "natural_text": "",
                },
                {
                    "label": "Source",
                    "items": rec_reason.get("source_tags", []) if isinstance(rec_reason, dict) else [],
                    "natural_text": "",
                },
            ]

            # Build source chips from subscription matches
            sub_names = rec_reason.get("matched_subscriptions", []) if isinstance(rec_reason, dict) else []
            source_chips = []
            if sub_names:
                source_chips.append({"label": sub_names[0], "type": "subscription"})
            item["source_chips"] = source_chips

            item["relevance_html"] = generate_relevance_html(item)
            item["author_text"] = format_author_text(item.get("authors"), limit=4)
            item["first_author"] = extract_primary_author(item.get("authors"))
            item["category_labels"] = [
                CATEGORY_NAMES.get(cat, cat) for cat in item.get("categories", [])[:4]
            ]
            item["summary_short"] = (item.get("summary") or item.get("abstract") or "")[:220]
            decorated.append(item)

        # Add "why above" / "why hidden" explanations
        for idx, item in enumerate(decorated):
            details = item.get("score_details") or {}
            score = item.get("score", 0) or 0
            prev_score = decorated[idx - 1].get("score", 0) if idx > 0 else None
            primary_signal = max(
                (
                    ("Theme Match", details.get("relevance", 0)),
                    ("Author / Institution", details.get("author", 0)),
                    ("Technical Depth", details.get("depth", 0)),
                    ("Zotero Semantic", details.get("semantic", 0)),
                ),
                key=lambda pair: pair[1],
            )[0]
            if idx == 0:
                item["why_above"] = "It has the highest composite score, so it ranks first."
            else:
                gap = max((prev_score or 0) - score, 0)
                item["why_above"] = (
                    f"It stays near the top because {primary_signal} is strong; "
                    f"the score gap to the paper above is ~{gap:.1f}."
                )
            item["why_hidden"] = (
                "Papers with only weak keyword hits or lacking semantic/author "
                "signals are pushed lower in the list."
            )
        return decorated

    # ==================================================================
    # Internal — digest parsing
    # ==================================================================

    # ==================================================================
    # Internal — background pipeline
    # ==================================================================

    def _run_pipeline_background(self, run_id=None, force_refresh=False):
        try:
            from app.services.daily_pipeline import run_pipeline

            if run_id:
                self._store.update_job(run_id, "running")
            papers = run_pipeline(force_refresh=force_refresh)
            if run_id:
                self._store.update_job(
                    run_id,
                    "succeeded",
                    result={
                        "paper_count": len(papers) if papers else 0,
                        "mode": "background_generation",
                        "force_refresh": force_refresh,
                    },
                )
        except Exception as e:
            if run_id:
                self._store.update_job(run_id, "failed", error_text=str(e)[:2000])
        except BaseException:
            if run_id:
                self._store.update_job(run_id, "failed", error_text="Unexpected shutdown")
            raise

    # ==================================================================
    # Internal — recommendation health
    # ==================================================================

    def _build_recommendation_health(self, cached_papers=None) -> dict:
        from app.services.diagnostics_service import build_recommendation_health

        return build_recommendation_health(cached_papers, state_store=self._store)
