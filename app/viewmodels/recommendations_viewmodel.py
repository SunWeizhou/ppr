"""Recommendations workspace viewmodel."""

from __future__ import annotations

from app.services.recommendation_workspace_service import RecommendationWorkspaceService
from app.viewmodels.shared import assemble_page_context


class RecommendationsViewModel:
    def __init__(self, state_store):
        self._store = state_store

    def to_template_context(self, *, mode: str = "for_you", query: str = "") -> dict:
        service = RecommendationWorkspaceService(self._store)
        runs = service.list_recent(limit=6)
        papers = runs[0]["items"] if runs else []
        context = assemble_page_context(self._store, active_tab="recommendations")
        context.update({
            "title": "Recommendations - Paper Agent",
            "active_tab": "recommendations",
            "mode": mode,
            "query": query,
            "recommendation_runs": runs,
            "papers": papers,
            "selected_paper": papers[0] if papers else None,
        })
        return context
