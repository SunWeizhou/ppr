"""Paper detail viewmodel — builds context for the paper detail page."""
from __future__ import annotations
import json
from datetime import datetime
from typing import Optional
from logger_config import get_logger
from app_paths import CACHE_DIR, HISTORY_DIR
from app.services.paper_utils import format_author_text, extract_primary_author
from utils import CATEGORY_NAMES

logger = get_logger(__name__)


class PaperViewModel:
    """Build template context for the paper detail page."""

    def __init__(self, state_store):
        self._store = state_store

    def to_detail_context(self, paper_id: str) -> dict:
        """Build the full detail context for a paper."""
        paper_data = self._find_paper_data(paper_id)
        if not paper_data:
            return {"error": "Paper not found", "paper_id": paper_id}

        paper = dict(paper_data)
        paper["id"] = paper_id

        # Basic formatting
        paper["author_text"] = format_author_text(paper.get("authors"), limit=6)
        paper["first_author"] = extract_primary_author(paper.get("authors"))
        paper["category_labels"] = [
            CATEGORY_NAMES.get(cat, cat) for cat in paper.get("categories", [])[:6]
        ]

        # AI analysis
        analysis = self._store.get_paper_ai_analysis(paper_id) if hasattr(self._store, 'get_paper_ai_analysis') else None
        paper["ai_analysis"] = analysis

        # Queue status
        queue_items = self._store.list_queue_items()
        queue_status = None
        for item in queue_items:
            if item.get("paper_id") == paper_id:
                queue_status = item.get("status")
                break
        paper["queue_status"] = queue_status

        # Collections
        collections = self._store.list_collections()
        paper["collections"] = collections if isinstance(collections, list) else []

        # Score details
        details = paper.get("score_details") or paper.get("score_details_json") or {}
        if isinstance(details, str):
            try:
                details = json.loads(details)
            except (TypeError, json.JSONDecodeError):
                details = {}
        paper["score_details"] = details

        # Build page context with all required template variables
        from app.viewmodels.shared import assemble_page_context
        from state_store import QUEUE_STATUS_VALUES

        page_ctx = assemble_page_context(self._store, active_tab="inbox")

        # Add queue_counts required by base_research.html
        try:
            queue_counts = {status: 0 for status in QUEUE_STATUS_VALUES}
            for item in self._store.list_queue_items():
                status = item.get("status")
                if status in queue_counts:
                    queue_counts[status] += 1
        except Exception:
            queue_counts = {}
        page_ctx.setdefault("queue_counts", queue_counts)
        page_ctx.setdefault("queue_status_values", QUEUE_STATUS_VALUES)

        # Get recommendation reason
        try:
            from app.services.scoring_service import build_recommendation_reason
            rec_reason = build_recommendation_reason(paper)
            paper["recommendation_reason"] = rec_reason
        except Exception:
            paper["recommendation_reason"] = {}

        context = {
            "title": f"{paper.get('title', 'Paper Detail')[:60]} - arXiv Recommender",
            "paper": paper,
        }
        context.update(page_ctx)
        return context

    def _find_paper_data(self, paper_id: str) -> Optional[dict]:
        """Find paper data from any available source."""
        # Try recommendation runs in SQLite first
        try:
            recent_runs = self._store.list_recommendation_runs(limit=5)
            for run in recent_runs:
                items = self._store.get_recommendation_items(run["run_id"])
                for item in items:
                    if item.get("paper_id") == paper_id or item.get("id") == paper_id:
                        return item
        except Exception:
            pass

        # Try reading from history markdown files
        import os, re
        if os.path.exists(str(HISTORY_DIR)):
            for fname in sorted(os.listdir(str(HISTORY_DIR)), reverse=True):
                if not fname.startswith("digest_") or not fname.endswith(".md"):
                    continue
                filepath = os.path.join(str(HISTORY_DIR), fname)
                try:
                    from app.viewmodels.inbox_viewmodel import InboxViewModel
                    papers, _ = InboxViewModel.parse_digest(filepath, use_cache=False)
                    for p in papers:
                        if p.get("id") == paper_id:
                            return p
                except Exception:
                    continue

        return None
