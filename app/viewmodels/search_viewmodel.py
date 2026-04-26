"""Search page viewmodel — contextual keyword-driven paper search."""

from __future__ import annotations

from datetime import datetime

from app.services.paper_utils import (
    extract_primary_author,
    format_author_text,
    status_class,
)
from app.viewmodels.shared import assemble_page_context
from state_store import QUEUE_STATUS_VALUES
from utils import CATEGORY_NAMES


class SearchViewModel:
    """Build template context for the contextual search page."""

    def __init__(self, state_store):
        self._store = state_store

    def to_template_context(self, papers: list, keywords: list) -> dict:
        """Build the full template context for ``search_research.html``.

        Corresponds to the combined logic of ``_render_search_research()``
        and ``_decorate_search_papers()`` in web_server.py.
        """
        page_ctx = self._build_page_context()
        decorated = self._decorate_search_papers(papers)
        current_query = ", ".join(keywords)

        context = {
            "title": "Search - arXiv Recommender",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "current_query": current_query,
            "keywords": keywords,
            "papers": decorated,
        }
        context.update(page_ctx)
        return context

    # ==================================================================
    # Internal
    # ==================================================================

    def _build_page_context(self) -> dict:
        feedback = {"liked": [], "disliked": []}  # search pages don't load feedback
        base = assemble_page_context(self._store, active_tab="", feedback=feedback)
        base["queue_counts"] = self._queue_counts()
        base["queue_status_values"] = QUEUE_STATUS_VALUES
        base["recommendation_health"] = {}
        return base

    def _queue_counts(self) -> dict:
        counts = {status: 0 for status in QUEUE_STATUS_VALUES}
        for item in self._store.list_queue_items():
            status = item.get("status")
            if status in counts:
                counts[status] += 1
        return counts

    def _queue_map(self) -> dict:
        from app.services.paper_utils import normalize_queue_status

        return {
            item.get("paper_id"): normalize_queue_status(item.get("status"))
            for item in self._store.list_queue_items()
        }

    def _decorate_search_papers(self, papers: list) -> list:
        queue_map = self._queue_map()
        decorated = []

        for idx, paper in enumerate(papers, start=1):
            item = dict(paper)
            authors = item.get("authors", [])
            if isinstance(authors, list):
                author_text = ", ".join(authors[:3])
                if len(authors) > 3:
                    author_text += f" et al. ({len(authors)} authors)"
            else:
                author_text = authors

            item["rank"] = idx
            item["author_text"] = author_text
            item["first_author"] = extract_primary_author(authors)
            item["category_labels"] = [
                CATEGORY_NAMES.get(cat, cat) for cat in item.get("categories", [])[:4]
            ]
            item["queue_status"] = queue_map.get(item.get("id"))
            item["queue_status_class"] = status_class(item["queue_status"])
            item["relevance_reason"] = item.get("relevance_reason", "Keyword match")
            item["summary_short"] = (item.get("summary") or item.get("abstract") or "")[:220]
            decorated.append(item)

        return decorated
