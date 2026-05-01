"""Paper detail viewmodel — builds context for the paper detail page."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from app.services.paper_utils import extract_primary_author, format_author_text
from app_paths import CACHE_DIR, HISTORY_DIR
from logger_config import get_logger
from utils import CATEGORY_NAMES

logger = get_logger(__name__)


def _format_event(event: dict) -> dict:
    """Convert a raw interaction_event row into a dict with display_* keys."""
    event_type = event.get("event_type", "")
    payload = event.get("payload_json", {})
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except (TypeError, json.JSONDecodeError):
            payload = {}

    created_at = event.get("created_at", "")
    display_time = ""
    if created_at:
        try:
            dt = datetime.fromisoformat(created_at)
            display_time = dt.strftime("%b %d, %H:%M")
        except (ValueError, TypeError):
            display_time = created_at

    label_map = {
        "queue_status_changed": {
            "Deep Read": "Marked for Deep Reading",
            "Skim Later": "Marked to Skim",
            "Saved": "Saved",
        },
        "feedback_relevant": "Marked as Relevant",
        "feedback_ignored": "Ignored",
        "paper_opened": "Opened on arXiv",
        "export_to_zotero": "Exported to Zotero",
    }

    if event_type == "queue_status_changed":
        status = payload.get("status", "")
        label = label_map["queue_status_changed"].get(status, f"Status: {status}")
    else:
        label = label_map.get(event_type, event_type)

    return {
        "display_label": label,
        "display_detail": "",
        "display_time": display_time,
    }


class PaperViewModel:
    """Build template context for the paper detail page."""

    def __init__(self, state_store):
        self._store = state_store

    # TODO: Extract data-enrichment blocks (related papers, subscription matches,
    # interaction history, queue status, collections) into a PaperDetailService
    # once the viewmodel grows more complex or needs reuse beyond this view.

    def to_detail_context(self, paper_id: str) -> dict:
        """Build the full detail context for a paper."""
        from state_store import _canonical_paper_id
        paper_id = _canonical_paper_id(paper_id)

        # Build page context first — needed by both the error and success paths
        from app.viewmodels.shared import assemble_page_context
        from state_store import QUEUE_STATUS_VALUES

        page_ctx = assemble_page_context(self._store, active_tab="inbox")
        try:
            queue_counts = dict.fromkeys(QUEUE_STATUS_VALUES, 0)
            for item in self._store.list_queue_items():
                status = item.get("status")
                if status in queue_counts:
                    queue_counts[status] += 1
        except Exception:
            queue_counts = {}
        page_ctx.setdefault("queue_counts", queue_counts)
        page_ctx.setdefault("queue_status_values", QUEUE_STATUS_VALUES)

        paper_data = self._find_paper_data(paper_id)
        if not paper_data:
            return {"title": "Paper Not Found - arXiv Recommender", "error": "Paper not found", "paper_id": paper_id, **page_ctx}

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

        # Related papers — find papers with similar categories from recent runs
        try:
            related = []
            runs = self._store.list_recommendation_runs(limit=5)
            paper_cats = set(paper.get("categories", []))
            for run in runs:
                items = self._store.get_recommendation_items(run["run_id"])
                for item in items:
                    if item.get("paper_id") == paper_id:
                        continue
                    item_cats = set(item.get("categories", []))
                    if paper_cats & item_cats:
                        related.append(item)
                    if len(related) >= 8:
                        break
                if len(related) >= 8:
                    break
            paper["related_papers"] = related[:8]
        except Exception:
            paper["related_papers"] = []

        # Subscription matches — which subscriptions match this paper
        try:
            matches = []
            for sub in self._store.list_subscriptions():
                sub_text = sub.get("query_text", "").lower()
                title_text = (paper.get("title", "") or "").lower()
                abstract_text = (paper.get("abstract", "") or "").lower()
                if sub_text and (sub_text in title_text or sub_text in abstract_text):
                    matches.append({"name": sub.get("name", ""), "type": sub.get("type", "")})
            paper["subscription_matches"] = matches[:10]
        except Exception:
            paper["subscription_matches"] = []

        # Interaction history from interaction_events table
        try:
            if hasattr(self._store, 'list_interaction_events'):
                raw_events = self._store.list_interaction_events(paper_id=paper_id, limit=20)
                paper["interaction_history"] = [_format_event(e) for e in raw_events[:20]]
            else:
                paper["interaction_history"] = []
        except Exception:
            paper["interaction_history"] = []

        # Queue status
        queue_items = self._store.list_queue_items()
        queue_status = None
        for item in queue_items:
            if item.get("paper_id") == paper_id:
                queue_status = item.get("status")
                break
        paper["queue_status"] = queue_status

        # Collections — only show collections that actually contain this paper
        all_collections = self._store.list_collections()
        if isinstance(all_collections, list) and hasattr(self._store, 'list_collection_papers'):
            from state_store import _canonical_paper_id
            canonical_id = _canonical_paper_id(paper_id)
            filtered = []
            for col in all_collections:
                try:
                    col_id = col.get("id") or col.get("collection_id")
                    cpapers = self._store.list_collection_papers(col_id)
                    if any(_canonical_paper_id(cp.get("paper_id", "")) == canonical_id for cp in cpapers):
                        filtered.append(col)
                except Exception:
                    continue
            paper["collections"] = filtered
        else:
            paper["collections"] = all_collections if isinstance(all_collections, list) else []

        # Score details
        details = paper.get("score_details") or paper.get("score_details_json") or {}
        if isinstance(details, str):
            try:
                details = json.loads(details)
            except (TypeError, json.JSONDecodeError):
                details = {}
        paper["score_details"] = details

        context = {
            "title": f"{paper.get('title', 'Paper Detail')[:60]} - arXiv Recommender",
            "paper": paper,
        }
        context.update(page_ctx)
        return context

    def _find_paper_data(self, paper_id: str) -> dict | None:
        """Find paper data from any available source."""
        from state_store import _canonical_paper_id

        # Try recommendation runs in SQLite first
        try:
            recent_runs = self._store.list_recommendation_runs(limit=5)
            for run in recent_runs:
                items = self._store.get_recommendation_items(run["run_id"])
                for item in items:
                    stored_id = _canonical_paper_id(item.get("paper_id") or item.get("id") or "")
                    if stored_id == paper_id:
                        return item
        except Exception:
            pass

        # Try reading from history markdown files
        import os
        import re
        if os.path.exists(str(HISTORY_DIR)):
            for fname in sorted(os.listdir(str(HISTORY_DIR)), reverse=True):
                if not fname.startswith("digest_") or not fname.endswith(".md"):
                    continue
                filepath = os.path.join(str(HISTORY_DIR), fname)
                try:
                    from app.viewmodels.inbox_viewmodel import InboxViewModel
                    papers, _ = InboxViewModel.parse_digest(filepath, use_cache=False)
                    for p in papers:
                        if _canonical_paper_id(p.get("id") or "") == paper_id:
                            return p
                except Exception:
                    continue

        return None
