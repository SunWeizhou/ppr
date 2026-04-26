"""Inbox page viewmodel — home, date view, and generating states."""

from __future__ import annotations

import json
import os
import re
import threading
from datetime import datetime
from typing import Optional

from app_paths import CACHE_DIR, HISTORY_DIR, PROJECT_ROOT
from app.services.feedback_service import FeedbackService
from app.services.paper_utils import (
    extract_primary_author,
    format_author_text,
    generate_relevance_html,
    normalize_queue_status,
    status_class,
)
from app.viewmodels.shared import assemble_page_context
from state_store import QUEUE_STATUS_VALUES
from utils import CATEGORY_NAMES, count_keyword


# ---------------------------------------------------------------------------
# Per-process digest cache (avoids re-parsing the same file repeatedly)
# ---------------------------------------------------------------------------
_history_cache: dict = {}  # {date: (papers, keywords, timestamp)}
_HISTORY_CACHE_TTL = 300  # 5 seconds — kept short so fresh data appears quickly


class InboxViewModel:
    """Build template contexts for the inbox / home research page."""

    def __init__(self, state_store):
        self._store = state_store
        self._feedback_service: Optional[FeedbackService] = None
        self._generation_status = {
            "running": False,
            "started_at": None,
            "error": None,
            "run_id": None,
        }

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
        prev_date: Optional[str],
        next_date: Optional[str],
        feedback: dict,
        selected_filter: str = "all",
    ) -> dict:
        """Build the full template context for ``home_research.html``.

        Corresponds to the combined logic of ``_render_home_research()`` and
        ``_decorate_home_papers()`` in web_server.py.
        """
        keywords_config = self._load_keywords_config()
        today_matched_keywords = self._extract_today_keywords(papers, keywords_config)
        is_today = date == datetime.now().strftime("%Y-%m-%d")

        page_ctx = self._build_page_context(active_tab="inbox")
        decorated = self._decorate_home_papers(papers, feedback)

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
            "title": f"arXiv Daily Digest - {date}",
            "date": date,
            "is_today": is_today,
            "hero_keywords": today_matched_keywords or keywords[:8],
            "daily_themes": keywords[:10],
            "matched_keyword_count": len(today_matched_keywords),
            "papers": decorated,
            "selected_filter": selected_filter,
            "date_cards": self._build_date_cards(dates, date),
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
        context["title"] = "Generating Recommendations - arXiv Recommender"
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
        """Return sorted list of history dates (newest first)."""
        if not os.path.exists(HISTORY_DIR):
            return []
        dates = []
        for f in os.listdir(HISTORY_DIR):
            if f.startswith("digest_") and f.endswith(".md"):
                dates.append(f.replace("digest_", "").replace(".md", ""))
        return sorted(dates, reverse=True)

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

        papers, keywords = InboxViewModel._parse_markdown_digest(filepath)

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

    def start_background_generation(self) -> Optional[str]:
        """Start a background pipeline run; returns the job *run_id*.

        No-op if a generation is already running.
        """
        if self._generation_status["running"]:
            return self._generation_status.get("run_id")

        job = self._store.create_job(
            "daily_recommendation",
            trigger_source="auto_homepage",
            payload={"force_refresh": False, "mode": "background_generation"},
            status="queued",
        )

        self._generation_status = {
            "running": True,
            "started_at": datetime.now().isoformat(),
            "error": None,
            "run_id": job["run_id"],
        }

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
        counts = {status: 0 for status in QUEUE_STATUS_VALUES}
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

    def _build_date_cards(self, dates: list[str], current_date: str) -> list[dict]:
        cards = []
        for raw_date in dates[:14]:
            try:
                dt = datetime.strptime(raw_date, "%Y-%m-%d")
                cards.append({
                    "date": raw_date,
                    "day": dt.strftime("%d"),
                    "month": dt.strftime("%b").upper(),
                    "weekday": dt.strftime("%a"),
                    "active": raw_date == current_date,
                })
            except ValueError:
                cards.append({
                    "date": raw_date,
                    "day": raw_date[-2:],
                    "month": raw_date[5:7],
                    "weekday": "",
                    "active": raw_date == current_date,
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
        try:
            profile["saved_searches"] = self._store.list_saved_searches()
        except Exception:
            pass
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
                item["recommendation_reason"] = {}
                item["reason_summary"] = ""

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

    @staticmethod
    def _parse_markdown_digest(filepath: str):
        """Parse a markdown digest to extract papers and keywords."""
        papers = []
        keywords = []

        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        themes_match = re.search(r"\*\*Research Themes:\*\* (.+)", content)
        if themes_match:
            keywords = [k.strip() for k in themes_match.group(1).split(",")]

        date_match = re.search(r"digest_(\d{4}-\d{2}-\d{2})", filepath)
        date_str = date_match.group(1) if date_match else None

        if date_str:
            metadata_path = os.path.join(PROJECT_ROOT, "cache", "daily_metadata.json")
            if os.path.exists(metadata_path):
                try:
                    with open(metadata_path, "r", encoding="utf-8") as f:
                        metadata = json.load(f)
                        if metadata.get("date") == date_str and metadata.get("keywords"):
                            keywords = [k["word"] for k in metadata["keywords"]]
                except Exception:
                    pass

        # Try to load breakdown info from recommendation run files
        breakdown_map = {}
        if date_str:
            run_paths = [
                os.path.join(PROJECT_ROOT, "cache", "recommendation_runs", f"{date_str}.json"),
                os.path.join(PROJECT_ROOT, "cache", "daily_recommendation.json"),
            ]
            for rec_path in run_paths:
                if not os.path.exists(rec_path):
                    continue
                try:
                    with open(rec_path, "r", encoding="utf-8") as f:
                        rec_data = json.load(f)
                    if isinstance(rec_data, dict):
                        articles = rec_data.get("articles") or rec_data.get("papers") or []
                        for art in articles:
                            paper_id = art.get("id") or art.get("arxiv_id", "")
                            if paper_id:
                                bd = art.get("breakdown") or art.get("score_details") or {}
                                if bd:
                                    breakdown_map[paper_id] = bd
                        meta_kw = rec_data.get("keywords") or rec_data.get("themes") or []
                        if meta_kw:
                            keywords = (
                                meta_kw
                                if isinstance(meta_kw[0], str)
                                else [kw.get("word", str(kw)) for kw in meta_kw]
                            )
                        break
                except Exception:
                    pass

        # Parse individual paper sections
        sections = re.split(r"\n## \d+\. ", content)
        for section in sections[1:]:
            lines = section.strip().split("\n")
            if not lines:
                continue

            title = lines[0].strip()
            paper = {
                "title": title,
                "authors": [],
                "id": "",
                "link": "",
                "summary": "",
                "abstract": "",
                "relevance": "",
                "score": 0.0,
                "categories": [],
                "relevance_reason": "",
            }

            for line in lines[1:]:
                if line.startswith("**Authors:**"):
                    paper["authors"] = [
                        a.strip() for a in line.replace("**Authors:**", "").strip().split(",")
                    ]
                elif line.startswith("**arXiv:**"):
                    arxiv_part = line.replace("**arXiv:**", "").strip()
                    id_match = re.search(r"\[([^\]]+)\]", arxiv_part)
                    link_match = re.search(r"\(([^)]+)\)", arxiv_part)
                    if id_match:
                        paper["id"] = id_match.group(1)
                    if link_match:
                        paper["link"] = link_match.group(1)
                elif line.startswith("**Summary:**"):
                    paper["summary"] = line.replace("**Summary:**", "").strip()
                elif line.startswith("**Relevance:**"):
                    paper["relevance"] = line.replace("**Relevance:**", "").strip()
                    paper["relevance_reason"] = paper["relevance"]
                elif line.startswith("**Score:**"):
                    try:
                        paper["score"] = float(
                            line.replace("**Score:**", "").strip().split()[0]
                        )
                    except (ValueError, IndexError):
                        pass
                elif line.startswith("**Categories:**"):
                    raw = line.replace("**Categories:**", "").strip()
                    paper["categories"] = [c.strip() for c in raw.split(",") if c.strip()]

            if paper.get("id"):
                pid = paper["id"]
                if pid in breakdown_map:
                    paper["score_details"] = breakdown_map[pid]

            papers.append(paper)

        return papers, keywords

    # ==================================================================
    # Internal — background pipeline
    # ==================================================================

    def _run_pipeline_background(self, run_id=None, force_refresh=False):
        try:
            import sys

            sys.path.insert(0, str(PROJECT_ROOT))
            from arxiv_recommender_v5 import run_pipeline

            if run_id:
                self._store.update_job(run_id, "running")
            papers = run_pipeline(force_refresh=force_refresh)
            self._generation_status["running"] = False
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
            self._generation_status["error"] = None
        except Exception as e:
            self._generation_status["running"] = False
            self._generation_status["error"] = str(e)
            if run_id:
                self._store.update_job(run_id, "failed", error_text=str(e))

    # ==================================================================
    # Internal — recommendation health
    # ==================================================================

    def _build_recommendation_health(self, cached_papers=None) -> dict:
        try:
            from config_manager import get_config

            config = get_config()
            core_count = len(config.core_keywords)
            secondary_count = len(config.get_keywords_by_category("secondary"))
            theory_count = len(config.theory_keywords)
            zotero_path = os.path.expanduser(config._zotero.database_path or "")
            zotero_exists = bool(zotero_path and os.path.exists(zotero_path))
            scores = [float(p.get("score", 0) or 0) for p in (cached_papers or [])]
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
                "zotero": {"enabled": False, "configured_path": "", "path_exists": False},
            }
