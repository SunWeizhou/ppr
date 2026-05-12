"""Recommendation workspace service for Paper Agent."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date

from app.services.recommendation_engine import (
    Candidate,
    RecommendationEngine,
    RecommendationScorer,
    normalize_citation_score,
    normalize_freshness_score,
    _days_since_publication,
)


class RecommendationWorkspaceService:
    """Build and persist recommendation candidate sets."""

    def __init__(self, state_store, *, search_fn=None):
        self.state_store = state_store
        self.search_fn = search_fn
        self._engine = RecommendationEngine()
        self._scorer = RecommendationScorer()

    def list_recent(self, *, limit: int = 5) -> list[dict]:
        runs = self.state_store.list_recommendation_runs(limit=limit)
        result = []
        for run in runs:
            if run.get("trigger_source") in ("paper_agent_recommendations", "workspace_planner", "auto_homepage"):
                item = dict(run)
                item["items"] = self._decorate_items(self.state_store.get_recommendation_items(run["run_id"]))
                result.append(item)
        return result

    def latest_items(self) -> list[dict]:
        runs = self.list_recent(limit=10)
        if not runs:
            return []
        return runs[0]["items"]

    def run(self, *, mode: str = "for_you", query: str = "", max_results: int = 20) -> dict:
        """Run the multi-strategy recommendation engine and persist results."""
        query_text = self._query_for_mode(mode, query)
        papers = self._search(query_text, max_results=max_results * 3)  # Over-fetch for strategy filtering

        # Gather context for strategies
        profile = self.state_store.get_user_profile()
        try:
            subscriptions = self.state_store.list_subscriptions()
        except Exception:
            subscriptions = []
        try:
            reading_queue_items = self.state_store.list_queue_items()
            reading_queue = []
            for item in reading_queue_items:
                meta = self.state_store.get_paper_metadata(item.get("paper_id", "")) or {}
                reading_queue.append({**item, **meta})
        except Exception:
            reading_queue = []
        try:
            questions = self.state_store.list_research_questions()
        except Exception:
            questions = []

        # Run engine
        engine_result = self._engine.recommend(
            papers=papers,
            user_profile=profile,
            subscriptions=subscriptions,
            reading_queue=reading_queue,
            research_questions=questions,
            max_per_section=max_results,
        )

        # Score each candidate with multi-dimensional scorer
        for section in engine_result["sections"]:
            for candidate in section["candidates"]:
                paper = candidate.paper_data
                days_old = _days_since_publication(paper)
                cit_count = int(paper.get("citation_count") or 0)
                bd = candidate.score_breakdown

                scored = self._scorer.score(
                    relevance=bd.get("relevance", candidate.score),
                    citation=normalize_citation_score(cit_count),
                    freshness=normalize_freshness_score(days_old),
                    entity_affinity=bd.get("entity_affinity", 0.0),
                    feedback=bd.get("feedback", 0.0),
                )
                candidate.score = scored["composite"]
                candidate.score_breakdown = {
                    dim: info["raw"] for dim, info in scored["breakdown"].items()
                }

            # Re-sort by composite score
            section["candidates"].sort(key=lambda c: c.score, reverse=True)

        # Persist the run (flatten all candidates)
        all_papers = []
        for section in engine_result["sections"]:
            for c in section["candidates"]:
                paper = dict(c.paper_data)
                paper["score"] = c.score
                paper["score_details"] = c.score_breakdown
                paper["relevance_reason"] = c.reason
                paper["source_strategy"] = c.source_strategy
                all_papers.append(paper)

        # Deduplicate by paper_id for persistence (keep highest score)
        seen: dict[str, dict] = {}
        for paper in all_papers:
            pid = paper.get("paper_id") or paper.get("id", "")
            if pid not in seen or paper["score"] > seen[pid]["score"]:
                seen[pid] = paper
        deduped = list(seen.values())
        deduped.sort(key=lambda p: p.get("score", 0), reverse=True)

        run_id = self.state_store.save_recommendation_run(
            date.today().isoformat(),
            trigger_source="paper_agent_recommendations",
            papers=deduped[:max_results],
            themes=[query_text],
        )

        # Save paper metadata
        for paper in deduped[:max_results]:
            paper_id = paper.get("paper_id") or paper.get("id")
            if not paper_id:
                continue
            self.state_store.save_paper_metadata(
                paper_id,
                {
                    "title": paper.get("title", ""),
                    "abstract": paper.get("abstract") or paper.get("summary", ""),
                    "authors": paper.get("authors", []),
                    "categories": paper.get("categories", []),
                    "year": paper.get("year", ""),
                    "venue": paper.get("venue", ""),
                    "link": paper.get("link") or paper.get("url", ""),
                    "url": paper.get("url") or paper.get("link", ""),
                    "pdf_url": paper.get("pdf_url", ""),
                    "score": paper.get("score", 0),
                    "citation_count": paper.get("citation_count"),
                    "reference_count": paper.get("reference_count"),
                    "external_ids": paper.get("external_ids", {}),
                    "relevance_reason": paper.get("relevance_reason", ""),
                    "source": paper.get("source", ""),
                },
                source="paper_agent_recommendations",
                source_run_id=run_id,
            )

        # Build sectioned response
        sections_data = []
        for section in engine_result["sections"]:
            sections_data.append({
                "strategy": section["strategy"],
                "title": section["title"],
                "papers": self._decorate_items([
                    {**c.paper_data, "score": c.score, "relevance_reason": c.reason, "source_strategy": c.source_strategy, "score_breakdown": c.score_breakdown}
                    for c in section["candidates"]
                ]),
            })

        return {
            "run_id": run_id,
            "mode": mode,
            "query": query_text,
            "sections": sections_data,
            "papers": self._decorate_items(deduped[:max_results]),
            "count": len(deduped[:max_results]),
        }

    def run_sectioned(self, *, max_results: int = 15) -> dict:
        """Run the engine and return sectioned results for the recommendations page."""
        return self.run(mode="for_you", max_results=max_results)

    def _query_for_mode(self, mode: str, query: str) -> str:
        query = str(query or "").strip()
        if query:
            return query
        try:
            from config_manager import get_config
            profile = get_config().get_keywords_config()
            core = profile.get("core_topics", {})
            if isinstance(core, dict) and core:
                return " ".join(list(core.keys())[:4])
        except Exception:
            pass
        if mode == "reading":
            return "papers related to saved reading"
        return "machine learning research"

    def _search(self, query: str, *, max_results: int) -> list[dict]:
        if self.search_fn is not None:
            return self.search_fn(query, max_results=max_results)
        from app.services.unified_search_service import search_papers
        result = search_papers(query, max_results=max_results)
        return result.get("papers", [])

    def _decorate_items(self, papers: list[dict]) -> list[dict]:
        from app.services.paper_utils import format_author_text, extract_primary_author

        decorated = []
        for paper in papers:
            item = dict(paper)
            paper_id = item.get("paper_id") or item.get("id") or ""
            if paper_id:
                meta = self.state_store.get_paper_metadata(paper_id) or {}
                for key in ("title", "abstract", "authors", "year", "venue", "url", "link", "pdf_url", "citation_count", "reference_count", "source", "relevance_reason"):
                    if item.get(key) in (None, "", [], 0) and meta.get(key) not in (None, "", []):
                        item[key] = meta.get(key)
            authors = item.get("authors") or []
            item["author_text"] = format_author_text(authors, limit=4)
            first = extract_primary_author(authors) or "Paper"
            year = str(item.get("year") or item.get("published_at") or "")[:4]
            item["display_citation"] = f"{first}, {year}" if year else first
            abstract = item.get("abstract") or item.get("summary") or ""
            item["summary_short"] = abstract[:620] + ("..." if len(abstract) > 620 else "")
            item["paper_id"] = paper_id
            item["id"] = paper_id
            item.setdefault("relevance_reason", "Matches your recommendation profile.")
            item.setdefault("source_strategy", "")
            item.setdefault("score_breakdown", {})
            decorated.append(item)
        return decorated