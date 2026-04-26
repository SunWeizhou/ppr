"""Library page viewmodel.

Migrated from web_server.py — _render_library_research, _resolve_queue_papers,
_resolve_feedback_papers, _decorate_library_papers, _decorate_feedback_papers,
_build_stats_payload, _render_stats_research, _render_favorites_research.
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timedelta

from state_store import QUEUE_STATUS_VALUES, _canonical_paper_id

from app.services.feedback_service import FeedbackService
from app.services.paper_utils import (
    extract_primary_author,
    format_author_text,
    generate_relevance_html,
    normalize_queue_status,
    status_class,
)
from app.viewmodels.shared import (
    assemble_page_context,
    serialize_collection,
)


# ── static category labels (mirrored from web_server.py) ──────────────────

CATEGORY_NAMES = {
    "stat.ML": "Stat ML",
    "stat.TH": "Stat Theory",
    "stat.ME": "Methodology",
    "stat.CO": "Computation",
    "cs.LG": "ML",
    "cs.AI": "AI",
    "cs.CL": "NLP",
    "cs.CV": "Vision",
    "cs.NE": "Neural",
    "cs.IT": "Info Theory",
    "math.ST": "Math Stats",
    "math.PR": "Probability",
    "math.OC": "Optimization",
    "econ.EM": "Econometrics",
}

# Cache TTL for parsed markdown digests (seconds)
_HISTORY_CACHE_TTL = 300


class LibraryViewModel:
    """Assembles template context for the Library page and its sub-views
    (collections, saved papers, history, favorites, stats)."""

    def __init__(self, state_store):
        self._store = state_store
        self._feedback_service: FeedbackService | None = None
        # per-instance digest parse cache
        self._digest_cache: dict[str, tuple[list, list, float]] = {}

    # ── lazy feedback-service access ──────────────────────────────────────

    def _feedback(self) -> FeedbackService:
        if self._feedback_service is None:
            self._feedback_service = FeedbackService(
                self._store,
                feedback_file=self._resolve_path("FEEDBACK_FILE"),
                favorites_file=self._resolve_path("FAVORITES_FILE"),
                cache_file=self._resolve_path("CACHE_FILE"),
                history_dir=self._resolve_path("HISTORY_DIR"),
            )
        return self._feedback_service

    # ── path helpers (delegated to app_paths) ─────────────────────────────

    @staticmethod
    def _resolve_path(key: str) -> str:
        """Resolve well-known filesystem paths from *app_paths*."""
        from app_paths import CACHE_DIR, HISTORY_DIR, PROJECT_ROOT

        mapping = {
            "CACHE_FILE": str(CACHE_DIR / "paper_cache.json"),
            "HISTORY_DIR": str(HISTORY_DIR),
            "FEEDBACK_FILE": str(CACHE_DIR / "user_feedback.json"),
            "FAVORITES_FILE": str(CACHE_DIR / "favorite_papers.json"),
            "KEYWORDS_CONFIG_FILE": str(PROJECT_ROOT / "keywords_config.json"),
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

    def _queue_map(self) -> dict[str, str]:
        return {
            item.get("paper_id"): normalize_queue_status(item.get("status"))
            for item in self._store.list_queue_items()
        }

    def _queue_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {status: 0 for status in QUEUE_STATUS_VALUES}
        for item in self._store.list_queue_items():
            status = item.get("status")
            if status in counts:
                counts[status] += 1
        return counts

    def _available_dates(self) -> list[str]:
        history_dir = self._resolve_path("HISTORY_DIR")
        if not os.path.exists(history_dir):
            return []
        dates = []
        for f in os.listdir(history_dir):
            if f.startswith("digest_") and f.endswith(".md"):
                dates.append(f.replace("digest_", "").replace(".md", ""))
        return sorted(dates, reverse=True)

    def _parse_markdown_digest_cached(self, filepath: str) -> tuple[list, list]:
        """Parse a digest .md file, returning (papers, keywords).  Results are
        cached per-instance with a TTL to avoid redundant I/O."""
        date_match = re.search(r"digest_(\d{4}-\d{2}-\d{2})", filepath)
        cache_key = date_match.group(1) if date_match else filepath
        now = time.time()

        if cache_key in self._digest_cache:
            cached_papers, cached_keywords, cached_time = self._digest_cache[cache_key]
            try:
                file_mtime = os.path.getmtime(filepath)
            except OSError:
                file_mtime = 0
            if cached_time >= file_mtime and (now - cached_time) < _HISTORY_CACHE_TTL:
                return cached_papers, cached_keywords

        papers, keywords = self._parse_markdown_digest(filepath)
        self._digest_cache[cache_key] = (papers, keywords, now)
        return papers, keywords

    @staticmethod
    def _parse_markdown_digest(filepath: str) -> tuple[list, list]:
        """Minimal markdown digest parser — extracts papers and keywords."""
        papers: list = []
        keywords: list = []

        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        themes_match = re.search(r"\*\*Research Themes:\*\*\s*(.+)", content)
        if themes_match:
            keywords = [k.strip() for k in themes_match.group(1).split(",")]

        # Simple paper extraction: split by paper entries
        entries = re.split(r"\n##\s+(?:\d+\.\s+)?", content)
        for entry in entries[1:]:  # skip header
            paper = {}
            # title — first non-empty line
            lines = [l.strip() for l in entry.split("\n") if l.strip()]
            if not lines:
                continue
            paper["title"] = lines[0].lstrip("#").strip()

            # arxiv id
            id_match = re.search(
                r"arxiv\.org/abs/([\w\.\-]+)", entry, re.IGNORECASE
            )
            if not id_match:
                id_match = re.search(r"arXiv:([\w\.\-]+)", entry)
            paper["id"] = id_match.group(1) if id_match else ""

            # authors
            auth_match = re.search(r"\*\*Authors?:\*\*\s*(.+)", entry)
            if auth_match:
                paper["authors"] = auth_match.group(1).strip()

            # score
            score_match = re.search(r"\*\*Score:\*\*\s*([\d\.]+)", entry)
            if score_match:
                paper["score"] = float(score_match.group(1))

            # relevance / reason
            reason_match = re.search(r"\*\*(?:Recommendation|Relevance):\*\*\s*(.+)", entry)
            if reason_match:
                paper["relevance_reason"] = reason_match.group(1).strip()
                paper["relevance"] = reason_match.group(1).strip()

            # categories
            cat_match = re.search(r"\*\*Categories:\*\*\s*(.+)", entry)
            if cat_match:
                paper["categories"] = [
                    c.strip() for c in cat_match.group(1).split(",")
                ]

            # summary / abstract (short paragraph after metadata)
            abstract_match = re.search(r"\*\*(?:Summary|Abstract):\*\*\s*(.+)", entry)
            if abstract_match:
                paper["summary"] = abstract_match.group(1).strip()
                paper["abstract"] = abstract_match.group(1).strip()

            papers.append(paper)

        return papers, keywords

    def _load_history_paper_index(self) -> dict[str, dict]:
        """Build an in-memory index of paper_id → paper across all history dates."""
        index: dict[str, dict] = {}
        for date in self._available_dates():
            filepath = os.path.join(
                self._resolve_path("HISTORY_DIR"), f"digest_{date}.md"
            )
            try:
                papers, _ = self._parse_markdown_digest_cached(filepath)
            except OSError:
                continue
            for paper in papers:
                paper_id = paper.get("id")
                if paper_id and paper_id not in index:
                    item = dict(paper)
                    item["date"] = date
                    index[paper_id] = item
        return index

    def _resolve_paper_record(
        self,
        paper_id,
        *,
        history_index=None,
        favorites=None,
        paper_cache=None,
    ) -> dict:
        if favorites is None:
            favorites = self._feedback().load_favorites()
        if paper_cache is None:
            paper_cache = self._safe_load_json(self._resolve_path("CACHE_FILE"))
        if history_index is None:
            history_index = self._load_history_paper_index()

        if paper_id in favorites:
            fav = favorites[paper_id]
            return {
                "id": paper_id,
                "title": fav.get("title", f"论文 {paper_id}"),
                "link": fav.get("link", f"https://arxiv.org/abs/{paper_id}"),
                "authors": fav.get("authors", ""),
                "summary": fav.get(
                    "summary",
                    fav.get("abstract", "")[:300] if fav.get("abstract") else "",
                ),
                "abstract": fav.get("abstract", fav.get("summary", "")),
                "relevance": fav.get("relevance", "来自你的长期收藏"),
                "score": fav.get("score", 0),
                "date": (
                    fav.get("date_published") or fav.get("date_added") or ""
                )[:10],
                "categories": fav.get("categories", []),
                "source": "favorites",
            }

        if paper_id in history_index:
            item = dict(history_index[paper_id])
            item.setdefault("source", "history")
            item.setdefault("summary", item.get("abstract", ""))
            item.setdefault("abstract", item.get("summary", ""))
            item.setdefault(
                "relevance",
                item.get("relevance_reason", item.get("relevance", "")),
            )
            return item

        if paper_id in paper_cache:
            cached = paper_cache[paper_id]
            return {
                "id": paper_id,
                "title": cached.get("title", f"论文 {paper_id}"),
                "link": f"https://arxiv.org/abs/{paper_id}",
                "authors": cached.get("authors", "作者信息不可用"),
                "summary": cached.get("abstract", "摘要不可用"),
                "abstract": cached.get("abstract", ""),
                "relevance": cached.get("relevance", "来自缓存"),
                "score": cached.get("score", 0),
                "date": cached.get("date", ""),
                "categories": cached.get("categories", []),
                "source": "paper_cache",
            }

        return {
            "id": paper_id,
            "title": f"论文 {paper_id}",
            "link": f"https://arxiv.org/abs/{paper_id}",
            "authors": "详情不可用",
            "summary": "此论文信息暂时不在历史记录或缓存中，可按需补全。",
            "abstract": "",
            "relevance": "点击查看 arXiv 页面",
            "score": 0,
            "date": "",
            "categories": [],
            "source": "placeholder",
        }

    # ── decoration ────────────────────────────────────────────────────────

    def _decorate_papers(self, papers, feedback, *, queue_overrides=None):
        """Decorate a list of papers with queue status, author formatting etc.
        (Migrated from _decorate_library_papers.)"""
        queue_map = self._queue_map()
        if queue_overrides:
            queue_map.update(queue_overrides)

        decorated = []
        for idx, paper in enumerate(papers, start=1):
            item = dict(paper)
            item["rank"] = idx
            item["author_text"] = format_author_text(item.get("authors"))
            item["first_author"] = extract_primary_author(item.get("authors"))
            item["queue_status"] = queue_map.get(item.get("id"))
            item["queue_status_class"] = status_class(item["queue_status"])
            item["relevance_html"] = generate_relevance_html(item)
            item["is_incomplete"] = not item.get("score")
            item["is_liked"] = item.get("id") in feedback.get("liked", [])
            item["is_disliked"] = item.get("id") in feedback.get("disliked", [])
            item["category_labels"] = [
                CATEGORY_NAMES.get(category, category)
                for category in item.get("categories", [])[:4]
            ]
            item["summary_short"] = (
                item.get("summary") or item.get("abstract") or ""
            )[:220]
            decorated.append(item)
        return decorated

    def _decorate_feedback_papers(self, papers, feedback):
        """Decorate papers for the favorites / disliked view."""
        queue_map = self._queue_map()
        decorated = []
        for idx, paper in enumerate(papers, start=1):
            item = dict(paper)
            item["rank"] = idx
            item["author_text"] = format_author_text(item.get("authors"))
            item["queue_status"] = queue_map.get(item.get("id"))
            item["queue_status_class"] = status_class(item["queue_status"])
            item["relevance_html"] = generate_relevance_html(item)
            item["is_incomplete"] = not item.get("score")
            item["is_liked"] = item.get("id") in feedback.get("liked", [])
            item["is_disliked"] = item.get("id") in feedback.get("disliked", [])
            decorated.append(item)
        return decorated

    # ── queue / feedback resolution ───────────────────────────────────────

    def _resolve_queue_papers(self, status=None):
        feedback = self._feedback().load_feedback()
        history_index = self._load_history_paper_index()
        favorites = self._feedback().load_favorites()
        paper_cache = self._safe_load_json(self._resolve_path("CACHE_FILE"))

        resolved = []
        for item in self._store.list_queue_items(status=status):
            queue_status = normalize_queue_status(item.get("status"))
            paper = self._resolve_paper_record(
                item.get("paper_id"),
                history_index=history_index,
                favorites=favorites,
                paper_cache=paper_cache,
            )
            paper["queue_status"] = queue_status
            paper["queue_status_class"] = status_class(queue_status)
            paper["queue_note"] = item.get("note", "")
            paper["queue_tags"] = item.get("tags_json", [])
            paper["queue_source"] = item.get("source", "")
            paper["updated_at"] = item.get("updated_at", "")
            resolved.append(paper)

        return self._decorate_papers(
            resolved,
            feedback,
            queue_overrides={paper["id"]: paper["queue_status"] for paper in resolved},
        )

    def _resolve_feedback_papers(self, feedback_type):
        feedback = self._feedback().load_feedback()
        paper_ids = feedback.get(feedback_type, [])
        favorites = self._feedback().load_favorites()
        paper_cache = self._safe_load_json(self._resolve_path("CACHE_FILE"))
        all_papers = self._load_history_paper_index()

        filtered_papers = []
        found_count = 0

        for paper_id in paper_ids:
            if feedback_type == "liked" and paper_id in favorites:
                fav = favorites[paper_id]
                filtered_papers.append({
                    "id": paper_id,
                    "title": fav.get("title", f"论文 {paper_id}"),
                    "link": fav.get("link", f"https://arxiv.org/abs/{paper_id}"),
                    "authors": fav.get("authors", ""),
                    "summary": fav.get(
                        "summary",
                        fav.get("abstract", "")[:300] if fav.get("abstract") else "",
                    ),
                    "relevance": fav.get("relevance", "来自你的长期收藏"),
                    "score": fav.get("score", 0),
                    "date": (
                        fav.get("date_published") or fav.get("date_added") or ""
                    )[:10],
                })
                found_count += 1
            elif paper_id in all_papers:
                filtered_papers.append(all_papers[paper_id])
                found_count += 1
            elif paper_id in paper_cache:
                cached = paper_cache[paper_id]
                filtered_papers.append({
                    "id": paper_id,
                    "title": cached.get("title", f"论文 {paper_id}"),
                    "link": f"https://arxiv.org/abs/{paper_id}",
                    "authors": cached.get("authors", "作者信息不可用"),
                    "summary": cached.get("abstract", "摘要不可用"),
                    "relevance": cached.get("relevance", "来自缓存"),
                    "score": cached.get("score", 0),
                    "date": cached.get("date", ""),
                })
                found_count += 1
            else:
                filtered_papers.append({
                    "id": paper_id,
                    "title": f"论文 {paper_id}",
                    "link": f"https://arxiv.org/abs/{paper_id}",
                    "authors": "详情不可用",
                    "summary": "此论文信息暂时不在历史记录或缓存中，可按需补全。",
                    "relevance": "点击查看 arXiv 页面",
                    "score": 0,
                    "date": "",
                })

        if feedback_type == "liked":
            def _sort_date(paper):
                paper_id = paper.get("id", "")
                fav = favorites.get(paper_id, {})
                date_str = fav.get("date_added", "")
                if not date_str:
                    return datetime.min
                try:
                    return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                except Exception:
                    return datetime.min

            filtered_papers.sort(key=_sort_date, reverse=True)

        return filtered_papers, found_count, len(paper_ids), feedback

    # ── stats payload ─────────────────────────────────────────────────────

    def _build_stats_payload(self):
        feedback = self._feedback().load_feedback()
        favorites = self._feedback().load_favorites()
        liked_ids = feedback.get("liked", [])
        disliked_ids = feedback.get("disliked", [])
        favorite_ids = list(favorites.keys())
        dates = self._available_dates()

        def _parse_paper_date(paper_id):
            try:
                year_month = paper_id.split("v")[0][:4]
                year = 2000 + int(year_month[:2])
                month = int(year_month[2:4])
                return datetime(year, month, 1)
            except Exception:
                return None

        today = datetime.now()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        weekly_liked = sum(
            1 for pid in liked_ids
            if _parse_paper_date(pid) and _parse_paper_date(pid) >= week_ago
        )
        monthly_liked = sum(
            1 for pid in liked_ids
            if _parse_paper_date(pid) and _parse_paper_date(pid) >= month_ago
        )

        # Keyword extraction from liked papers
        keyword_counts: dict[str, int] = {}
        for paper_id in liked_ids:
            text = ""
            if paper_id in favorites:
                text = (
                    favorites[paper_id].get("title", "")
                    + " "
                    + favorites[paper_id].get("abstract", "")
                ).lower()
            else:
                for date in dates[:7]:
                    filepath = os.path.join(
                        self._resolve_path("HISTORY_DIR"), f"digest_{date}.md"
                    )
                    if not os.path.exists(filepath):
                        continue
                    try:
                        papers, _ = self._parse_markdown_digest_cached(filepath)
                    except Exception:
                        continue
                    for paper in papers:
                        if paper.get("id") == paper_id:
                            text = (
                                paper.get("title", "")
                                + " "
                                + paper.get("summary", "")
                            ).lower()
                            break
                    if text:
                        break

            keywords = re.findall(r"\b[a-z]+(?:\s+[a-z]+)?\b", text)
            for kw in keywords:
                if len(kw) > 4:
                    keyword_counts[kw] = keyword_counts.get(kw, 0) + 1

        top_keywords = [
            {"keyword": k, "count": c}
            for k, c in sorted(
                keyword_counts.items(), key=lambda item: -item[1]
            )[:15]
        ]

        total_seen = 0
        cache_file = self._resolve_path("CACHE_FILE")
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    total_seen = len(json.load(f))
            except Exception:
                total_seen = 0

        avg_daily_likes = len(liked_ids) / max(len(dates), 1)
        total_feedback = len(liked_ids) + len(disliked_ids)
        like_rate = (
            len(liked_ids) * 100 // max(total_feedback, 1)
        )

        return {
            "liked_count": len(liked_ids),
            "disliked_count": len(disliked_ids),
            "favorite_count": len(favorite_ids),
            "weekly_liked": weekly_liked,
            "monthly_liked": monthly_liked,
            "active_days": len(dates),
            "avg_daily_likes": avg_daily_likes,
            "total_seen": total_seen,
            "total_feedback": total_feedback,
            "like_rate": like_rate,
            "top_keywords": top_keywords,
        }

    # ── recommendation health (mirrored from web_server._build_recommendation_health) ─

    def _build_recommendation_health(self, cached_papers=None):
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

    # ── page-context assembly ─────────────────────────────────────────────

    def _build_page_context(self, active_tab: str) -> dict:
        """Build the shared page context (replaces web_server._build_page_context)."""
        feedback = self._feedback().load_feedback()
        base = assemble_page_context(self._store, active_tab=active_tab, feedback=feedback)
        base["queue_counts"] = self._queue_counts()
        base["queue_status_values"] = QUEUE_STATUS_VALUES
        base["recommendation_health"] = self._build_recommendation_health()
        return base

    # ── public entry-points ───────────────────────────────────────────────

    def to_template_context(
        self,
        tab: str = "collections",
        collection_id: int | None = None,
        selected_date: str = "",
    ) -> dict:
        """Render the main Library page (collections / saved / history tabs).
        Replaces web_server._render_library_research."""
        page_context = self._build_page_context("library")
        feedback = self._feedback().load_feedback()
        collections_all = page_context["all_collections"]

        # ── Collections tab ──
        selected_collection = None
        if collection_id:
            col = self._store.get_collection(collection_id)
            selected_collection = serialize_collection(col) if col else None
        elif tab == "collections" and collections_all:
            selected_collection = collections_all[0]

        selected_collection_papers = []
        if selected_collection:
            history_index = self._load_history_paper_index()
            favorites = self._feedback().load_favorites()
            paper_cache = self._safe_load_json(self._resolve_path("CACHE_FILE"))
            resolved = []
            for item in self._store.list_collection_papers(selected_collection["id"]):
                paper = self._resolve_paper_record(
                    item.get("paper_id"),
                    history_index=history_index,
                    favorites=favorites,
                    paper_cache=paper_cache,
                )
                paper["collection_note"] = item.get("note", "")
                paper["added_at"] = item.get("added_at", "")
                resolved.append(paper)
            selected_collection_papers = self._decorate_papers(resolved, feedback)

        # ── Saved Papers tab ──
        saved_papers = self._resolve_queue_papers(status="Saved")

        # ── History tab ──
        history_dates = self._available_dates()
        history_papers = []
        if selected_date:
            filepath = os.path.join(
                self._resolve_path("HISTORY_DIR"), f"digest_{selected_date}.md"
            )
            if os.path.exists(filepath):
                papers, _ = self._parse_markdown_digest_cached(filepath)
                for paper in papers:
                    paper["date"] = selected_date
                history_papers = self._decorate_papers(papers, feedback)

        context = {
            "title": "Library - arXiv Recommender",
            "tab": tab,
            "selected_collection": selected_collection,
            "selected_collection_papers": selected_collection_papers,
            "saved_papers": saved_papers,
            "saved_papers_count": len(saved_papers),
            "history_dates": history_dates,
            "selected_date": selected_date,
            "history_papers": history_papers,
        }
        context.update(page_context)
        return context

    def to_favorites_context(self, feedback_type: str) -> dict:
        """Render the Favorites / Disliked view.
        Replaces web_server._render_favorites_research."""
        papers, found_count, total_count, feedback = self._resolve_feedback_papers(
            feedback_type
        )
        decorated_papers = self._decorate_feedback_papers(papers, feedback)
        page_context = self._build_page_context("library")

        queued_count = sum(1 for p in decorated_papers if p.get("queue_status"))
        incomplete_count = sum(1 for p in decorated_papers if p.get("is_incomplete"))
        missing_count = max(total_count - found_count, 0)

        hero_title = (
            "喜欢的论文" if feedback_type == "liked" else "已忽略论文"
        )
        hero_subtitle = (
            "这不是一个静态收藏夹，而是你长期研究资产的一部分。把真正值得回看的论文送进队列，再逐步沉淀成 collection。"
            if feedback_type == "liked"
            else "忽略列表用来收紧推荐边界，避免首页反复被同类噪音占据。它更像一组持久的负反馈，而不是临时的“看过了”。"
        )
        asset_note = (
            "喜欢页优先展示你未来还会反复回看的论文；缺失元数据的条目可以按需补全。"
            if feedback_type == "liked"
            else "忽略页用于观察系统正在学会规避哪些主题，必要时也可以重新标记为相关。"
        )

        headline_metrics = [
            {"label": "条目总数", "value": total_count},
            {"label": "已补全", "value": found_count},
            {"label": "已在队列", "value": queued_count},
            {"label": "待补全", "value": incomplete_count},
        ]

        context = {
            "title": f"{hero_title} - arXiv Recommender",
            "hero_kicker": (
                "Research Assets" if feedback_type == "liked" else "Feedback Memory"
            ),
            "hero_title": hero_title,
            "hero_subtitle": hero_subtitle,
            "asset_note": asset_note,
            "feedback_type": feedback_type,
            "papers": decorated_papers,
            "headline_metrics": headline_metrics,
            "total_count": total_count,
            "found_count": found_count,
            "missing_count": missing_count,
        }
        context.update(page_context)
        return context

    def to_stats_context(self) -> dict:
        """Render the Reading Stats page.
        Replaces web_server._render_stats_research."""
        page_context = self._build_page_context("insights")
        # Remove liked_count from page_context as stats has its own
        page_context = {k: v for k, v in page_context.items() if k != "liked_count"}
        stats_payload = self._build_stats_payload()

        headline_metrics = [
            {"label": "总浏览量", "value": stats_payload["total_seen"]},
            {"label": "喜欢", "value": stats_payload["liked_count"]},
            {"label": "忽略", "value": stats_payload["disliked_count"]},
            {"label": "喜欢率", "value": f"{stats_payload['like_rate']}%"},
        ]
        rhythm_cards = [
            {
                "label": "本周喜欢",
                "value": stats_payload["weekly_liked"],
                "copy": "最近一周真正进入正反馈的论文数量。",
            },
            {
                "label": "本月喜欢",
                "value": stats_payload["monthly_liked"],
                "copy": "用来判断当前方向是不是持续在产出你会留下的工作。",
            },
            {
                "label": "活跃天数",
                "value": stats_payload["active_days"],
                "copy": "系统已经连续记录的推荐历史天数。",
            },
            {
                "label": "日均喜欢",
                "value": f"{stats_payload['avg_daily_likes']:.1f}",
                "copy": "粗略反映你每天能从收件箱里筛出多少真正值得保留的论文。",
            },
        ]

        context = {
            "title": "阅读统计 - arXiv Recommender",
            "headline_metrics": headline_metrics,
            "rhythm_cards": rhythm_cards,
        }
        context.update(stats_payload)
        context.update(page_context)
        return context
