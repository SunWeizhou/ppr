"""Bounded planner skeleton for workspace-first research runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Callable, Dict, List, Tuple

from app.services.ai_analysis_service import AIAnalysisService
from app.services.ranker import score_paper
from state_store import _canonical_paper_id


def _default_search_fn(keywords, *, max_results: int, days_back: int) -> List[Dict]:
    from arxiv_recommender_v5 import search_by_keywords

    return search_by_keywords(keywords, max_results=max_results, days_back=days_back)


@dataclass(frozen=True)
class PlannerBudget:
    max_query_rewrites: int = 3
    max_candidates: int = 25
    max_analyses: int = 10
    days_back: int = 60
    phase_budget_seconds: Dict[str, int] = field(
        default_factory=lambda: {
            "plan": 5,
            "discover": 30,
            "rank": 10,
            "analyze": 60,
            "route": 10,
        }
    )


class WorkspacePlannerService:
    """Create bounded planner runs.

    Phase 1 records deterministic run plans only. Network fetch, ranking, and UI
    routing are implemented in later phases against this stable contract.
    """

    def __init__(
        self,
        state_store,
        budget: PlannerBudget | None = None,
        *,
        search_fn: Callable | None = None,
        analysis_service: AIAnalysisService | None = None,
    ):
        self.state_store = state_store
        self.budget = budget or PlannerBudget()
        self.search_fn = search_fn or _default_search_fn
        self.analysis_service = analysis_service or AIAnalysisService(state_store)

    def build_plan(self, research_question_id: int, *, trigger: str = "manual") -> Dict:
        question = self.state_store.get_research_question(research_question_id)
        if question is None:
            raise ValueError(f"Unknown research question: {research_question_id}")
        if question["status"] != "active":
            raise ValueError(f"Research question is not active: {research_question_id}")

        phase_names = ("plan", "discover", "rank", "analyze", "route")
        return {
            "research_question_id": research_question_id,
            "trigger": trigger,
            "query_text": question["query_text"],
            "intent_statement": question.get("intent_statement", ""),
            "query_rewrites": self._query_terms(question),
            "max_query_rewrites": self.budget.max_query_rewrites,
            "max_candidates": self.budget.max_candidates,
            "max_analyses": self.budget.max_analyses,
            "days_back": self.budget.days_back,
            "phases": [
                {
                    "name": name,
                    "time_budget_seconds": int(self.budget.phase_budget_seconds.get(name, 0)),
                }
                for name in phase_names
            ],
        }

    # ------------------------------------------------------------------
    #  Query and normalization helpers
    # ------------------------------------------------------------------

    def _query_terms(self, question: Dict) -> List[str]:
        values = [
            str(question.get("query_text") or "").strip(),
            str(question.get("intent_statement") or "").strip(),
        ]
        terms: List[str] = []
        for value in values:
            if not value:
                continue
            for part in value.replace(";", ",").split(","):
                candidate = part.strip()
                if candidate and candidate.lower() not in {term.lower() for term in terms}:
                    terms.append(candidate)
        return terms[: self.budget.max_query_rewrites] or [question["query_text"]]

    def _normalize_paper(self, paper: Dict) -> Dict:
        item = dict(paper or {})
        paper_id = _canonical_paper_id(item.get("id") or item.get("paper_id") or "")
        item["id"] = paper_id
        item["paper_id"] = paper_id
        item.setdefault("title", "")
        item.setdefault("abstract", item.get("summary", ""))
        item.setdefault("summary", item.get("abstract", ""))
        item.setdefault("authors", [])
        item.setdefault("categories", [])
        return item

    # ------------------------------------------------------------------
    #  Discovery and ranking
    # ------------------------------------------------------------------

    def _discover_candidates(self, plan: Dict) -> Tuple[List[Dict], Dict]:
        candidates_by_id: Dict[str, Dict] = {}
        per_query_limit = max(1, min(10, self.budget.max_candidates))
        for query in plan["query_rewrites"]:
            papers = self.search_fn(
                [query],
                max_results=per_query_limit,
                days_back=self.budget.days_back,
            ) or []
            for raw in papers:
                paper = self._normalize_paper(raw)
                paper_id = paper.get("id")
                if not paper_id:
                    continue
                existing = candidates_by_id.get(paper_id)
                if existing is None or float(paper.get("score", 0) or 0) > float(existing.get("score", 0) or 0):
                    candidates_by_id[paper_id] = paper
        candidates = list(candidates_by_id.values())[: self.budget.max_candidates]
        return candidates, {"candidate_count": len(candidates)}

    def _rank_candidates(self, candidates: List[Dict], plan: Dict) -> Tuple[List[Dict], Dict]:
        ranked = []
        ctx = {"keywords": plan["query_rewrites"]}
        for index, paper in enumerate(candidates):
            match_score, reason = score_paper(paper, ctx)
            source_score = min(float(paper.get("score", 0) or 0) / 10.0, 1.0)
            workspace_score = max(match_score, source_score)
            item = dict(paper)
            item["workspace_score"] = workspace_score
            item["score"] = workspace_score
            item["score_details"] = {
                "workspace": workspace_score,
                "keyword": match_score,
                "source": source_score,
            }
            item["relevance_reason"] = item.get("relevance_reason") or reason
            item["_planner_input_index"] = index
            ranked.append(item)
        ranked.sort(key=lambda paper: (-paper["workspace_score"], paper["_planner_input_index"]))
        ranked = ranked[: self.budget.max_candidates]
        for rank, paper in enumerate(ranked, start=1):
            paper["rank"] = rank
            paper.pop("_planner_input_index", None)
        return ranked, {"ranked_count": len(ranked)}

    def start_run(self, research_question_id: int, *, trigger: str = "manual") -> Dict:
        plan = self.build_plan(research_question_id, trigger=trigger)
        job = self.state_store.create_job(
            "workspace_planner",
            trigger_source=trigger,
            payload=plan,
            status="running",
        )
        result = {
            "run_id": job["run_id"],
            "status": "succeeded",
            "phase_results": [
                {"name": phase["name"], "status": "skipped", "reason": "phase1_contract_only"}
                for phase in plan["phases"]
            ],
        }
        self.state_store.update_job(job["run_id"], "succeeded", result=result)
        return result
