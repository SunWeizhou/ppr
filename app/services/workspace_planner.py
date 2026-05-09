"""Bounded planner skeleton for workspace-first research runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass(frozen=True)
class PlannerBudget:
    max_query_rewrites: int = 3
    max_candidates: int = 25
    max_analyses: int = 10
    phase_budget_seconds: Dict[str, int] = field(
        default_factory=lambda: {
            "plan": 5,
            "discover": 30,
            "analyze": 60,
            "route": 10,
        }
    )


class WorkspacePlannerService:
    """Create bounded planner runs.

    Phase 1 records deterministic run plans only. Network fetch, ranking, and UI
    routing are implemented in later phases against this stable contract.
    """

    def __init__(self, state_store, budget: PlannerBudget | None = None):
        self.state_store = state_store
        self.budget = budget or PlannerBudget()

    def build_plan(self, research_question_id: int, *, trigger: str = "manual") -> Dict:
        question = self.state_store.get_research_question(research_question_id)
        if question is None:
            raise ValueError(f"Unknown research question: {research_question_id}")
        if question["status"] != "active":
            raise ValueError(f"Research question is not active: {research_question_id}")

        phase_names = ("plan", "discover", "analyze", "route")
        return {
            "research_question_id": research_question_id,
            "trigger": trigger,
            "query_text": question["query_text"],
            "intent_statement": question.get("intent_statement", ""),
            "query_rewrites": [question["query_text"]],
            "max_query_rewrites": self.budget.max_query_rewrites,
            "max_candidates": self.budget.max_candidates,
            "max_analyses": self.budget.max_analyses,
            "phases": [
                {
                    "name": name,
                    "time_budget_seconds": int(self.budget.phase_budget_seconds.get(name, 0)),
                }
                for name in phase_names
            ],
        }

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
