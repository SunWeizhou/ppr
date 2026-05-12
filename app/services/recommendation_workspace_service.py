"""Recommendation workspace service for Paper Agent."""

from __future__ import annotations

from datetime import date

from app.services.scoring_service import build_recommendation_reason


class RecommendationWorkspaceService:
    """Build and persist recommendation candidate sets."""

    def __init__(self, state_store, *, search_fn=None):
        self.state_store = state_store
        self.search_fn = search_fn

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
        query_text = self._query_for_mode(mode, query)
        papers = self._search(query_text, max_results=max_results)
        ranked = self._rank(papers, query_text)[:max_results]
        run_id = self.state_store.save_recommendation_run(
            date.today().isoformat(),
            trigger_source="paper_agent_recommendations",
            papers=ranked,
            themes=[query_text],
        )
        for paper in ranked:
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
        return {
            "run_id": run_id,
            "mode": mode,
            "query": query_text,
            "papers": self._decorate_items(ranked),
            "count": len(ranked),
        }

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

    def _rank(self, papers: list[dict], query: str) -> list[dict]:
        ranked = []
        keywords = [part for part in query.split() if part]
        user_profile = {"keywords": keywords, "core_topics": {kw: 1 for kw in keywords}}
        for index, paper in enumerate(papers):
            item = dict(paper)
            base = float(item.get("score", 0) or 0)
            citation_bonus = min(float(item.get("citation_count") or 0) / 1000.0, 0.25)
            score = max(base, 0.45) + citation_bonus - (index * 0.002)
            item["score"] = round(score, 4)
            try:
                reason = build_recommendation_reason(item, user_profile=user_profile)
                item["recommendation_reason"] = reason
                item["relevance_reason"] = reason.get("summary") or item.get("relevance_reason") or "Matches your recommendation profile."
            except Exception:
                item["relevance_reason"] = item.get("relevance_reason") or "Matches your recommendation profile."
            ranked.append(item)
        ranked.sort(key=lambda p: float(p.get("score", 0) or 0), reverse=True)
        return ranked

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
            decorated.append(item)
        return decorated
