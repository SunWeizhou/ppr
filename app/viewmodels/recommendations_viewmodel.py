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

        # Build sections from latest run papers (group by source_strategy)
        sections = self._build_sections(papers)

        context = assemble_page_context(self._store, active_tab="recommendations")
        context.update({
            "title": "Recommendations - Paper Agent",
            "active_tab": "recommendations",
            "mode": mode,
            "query": query,
            "recommendation_runs": runs,
            "papers": papers,
            "sections": sections,
            "selected_paper": papers[0] if papers else None,
        })
        return context

    def _build_sections(self, papers: list[dict]) -> list[dict]:
        """Group papers by source_strategy into display sections."""
        SECTION_TITLES = {
            "for_you": "For You",
            "entity": "From Your Subscriptions",
            "trending": "Trending",
            "reading": "Based on Your Reading",
            "question": "Research Questions",
        }
        groups: dict[str, list[dict]] = {}
        for paper in papers:
            strategy = paper.get("source_strategy", "for_you")
            groups.setdefault(strategy, []).append(paper)

        # If no strategy info, put everything in "For You"
        if not groups and papers:
            groups["for_you"] = papers

        sections = []
        for strategy_key in ("for_you", "entity", "trending", "reading", "question"):
            if strategy_key in groups:
                sections.append({
                    "strategy": strategy_key,
                    "title": SECTION_TITLES.get(strategy_key, strategy_key.replace("_", " ").title()),
                    "papers": groups[strategy_key],
                })

        # Add any remaining strategies not in the predefined order
        for key, papers_list in groups.items():
            if key not in ("for_you", "entity", "trending", "reading", "question"):
                sections.append({
                    "strategy": key,
                    "title": key.replace("_", " ").title(),
                    "papers": papers_list,
                })

        return sections