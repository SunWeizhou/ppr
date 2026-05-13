"""Search page viewmodel — contextual keyword-driven paper search."""

from __future__ import annotations

from datetime import datetime

from app.services.paper_utils import (
    extract_primary_author,
    format_author_text,
    status_class,
)
from app.services.workspace_service import WorkspaceService
from app.viewmodels.shared import assemble_page_context
from app.data._constants import QUEUE_STATUS_VALUES
from utils import CATEGORY_NAMES


class SearchViewModel:
    """Build template context for the contextual search page."""

    def __init__(self, state_store):
        self._store = state_store

    def to_template_context(
        self,
        papers: list,
        keywords: list,
        *,
        research_question_id: int | None = None,
        planner_result: dict | None = None,
        raw_query: str | None = None,
        search_sources: dict | None = None,
        search_warnings: list[str] | None = None,
        search_errors: list[str] | None = None,
    ) -> dict:
        """Build the full template context for ``search_research.html``."""
        page_ctx = self._build_page_context()
        decorated = self._decorate_search_papers(papers)
        current_query = raw_query or ", ".join(keywords)

        workspace_context = self._build_workspace_context(
            papers,
            current_query,
            research_question_id=research_question_id,
            planner_result=planner_result,
        )

        selected_paper = decorated[0] if decorated else None
        context = {
            "title": "Search - Paper Agent",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "current_query": current_query,
            "keywords": keywords,
            "papers": decorated,
            "selected_paper": selected_paper,
            "search_warnings": search_warnings or [],
            "search_errors": search_errors or [],
            "source_statuses": self._build_source_statuses(
                search_sources or {},
                search_warnings or [],
                search_errors or [],
                has_query=bool(current_query),
            ),
        }
        context.update(workspace_context)
        context.update(page_ctx)
        return context

    # ==================================================================
    # Workspace helpers
    # ==================================================================

    def _build_workspace_context(
        self,
        papers: list,
        current_query: str,
        *,
        research_question_id: int | None,
        planner_result: dict | None,
    ) -> dict:
        questions = self._store.list_research_questions(status="active")
        active_question = None
        if research_question_id is not None:
            active_question = self._store.get_research_question(research_question_id)

        if active_question is None and current_query:
            active_question = {
                "id": None,
                "query_text": current_query,
                "intent_statement": current_query,
                "status": "draft",
                "source": "search",
            }

        stats = None
        if active_question and active_question.get("id"):
            try:
                stats = WorkspaceService(self._store).workspace_stats(active_question["id"])
            except ValueError:
                stats = None

        intent_card = self._intent_card(active_question, current_query)
        return {
            "research_questions": questions,
            "active_research_question": active_question,
            "active_research_question_id": active_question.get("id") if active_question else None,
            "intent_card": intent_card,
            "workspace_stats": stats,
            "workspace_brief": self._workspace_brief(papers),
            "planner_result": planner_result,
        }

    def _intent_card(self, active_question: dict | None, current_query: str) -> dict:
        query_text = ""
        intent_statement = ""
        status = "draft"
        source = "search"
        if active_question:
            query_text = active_question.get("query_text", "")
            intent_statement = active_question.get("intent_statement", "") or query_text
            status = active_question.get("status", "draft")
            source = active_question.get("source", "search")
        elif current_query:
            query_text = current_query
            intent_statement = current_query
        return {
            "query_text": query_text,
            "intent_statement": intent_statement,
            "status": status,
            "source": source,
        }

    def _workspace_brief(self, papers: list) -> dict:
        if not papers:
            return {
                "mode": "empty",
                "candidate_count": 0,
                "top_categories": [],
                "message": "Start with a research question to build a candidate set.",
            }
        category_counts = {}
        for paper in papers:
            for category in (paper.get("categories") or [])[:4]:
                category_counts[category] = category_counts.get(category, 0) + 1
        top_categories = [
            category for category, _count in sorted(
                category_counts.items(),
                key=lambda item: (-item[1], item[0]),
            )[:4]
        ]
        return {
            "mode": "results",
            "candidate_count": len(papers),
            "top_categories": top_categories,
            "message": f"{len(papers)} candidate papers are ready for review.",
        }

    @staticmethod
    def _build_source_statuses(
        sources: dict,
        warnings: list[str],
        errors: list[str],
        *,
        has_query: bool,
    ) -> list[dict]:
        labels = {
            "arxiv": "arXiv",
            "semantic_scholar": "Semantic Scholar",
            "openalex": "OpenAlex",
        }
        messages = {
            "ok": "Available",
            "failed": "Temporarily unavailable",
            "not_requested": "Ready",
            "idle": "Ready",
        }
        warning_text = " ".join(str(item) for item in warnings + errors)
        statuses = []
        for key, label in labels.items():
            state = str(sources.get(key) or ("not_requested" if has_query else "idle"))
            message = messages.get(state, state.replace("_", " ").title())
            if state == "failed" and label in warning_text:
                message = next(
                    (item for item in warnings + errors if label in str(item)),
                    message,
                )
            statuses.append({
                "key": key,
                "label": label,
                "state": state,
                "message": message,
            })
        return statuses

    # ==================================================================
    # Internal
    # ==================================================================

    def _build_page_context(self) -> dict:
        feedback = {"liked": [], "disliked": []}  # search pages don't load feedback
        base = assemble_page_context(self._store, active_tab="search", feedback=feedback)
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
            item["paper_id"] = item.get("paper_id") or item.get("id")
            item["id"] = item.get("id") or item["paper_id"]
            item["author_text"] = author_text
            item["display_citation"] = self._display_citation(item, authors)
            item["first_author"] = extract_primary_author(authors)
            item["category_labels"] = [
                CATEGORY_NAMES.get(cat, cat) for cat in item.get("categories", [])[:4]
            ]
            item["queue_status"] = queue_map.get(item.get("id"))
            item["queue_status_class"] = status_class(item["queue_status"])
            item["relevance_reason"] = item.get("relevance_reason", "Keyword match")
            item["summary_short"] = (item.get("summary") or item.get("abstract") or "")[:520]
            decorated.append(item)

        return decorated

    @staticmethod
    def _display_citation(item: dict, authors) -> str:
        first = ""
        if isinstance(authors, list) and authors:
            first = str(authors[0]).split()[-1]
        elif isinstance(authors, str) and authors:
            first = authors.split(",")[0].split()[-1]
        year = str(item.get("year") or item.get("published_at") or item.get("date") or "")[:4]
        if first and year.isdigit():
            return f"{first}, {year}"
        return first or year or "Untitled"
