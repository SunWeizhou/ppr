"""Tests for workspace bounded planner."""
import tempfile
import unittest
from pathlib import Path

from app.services.workspace_planner import PlannerBudget, WorkspacePlannerService
from state_store import StateStore


class WorkspacePlannerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = StateStore(str(Path(self.tmp.name) / "state.db"))
        self.question = self.store.create_research_question(
            "conformal prediction under distribution shift",
            intent_statement="Find robust methods and finite-sample guarantees.",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_build_plan_is_bounded_and_schema_stable(self):
        planner = WorkspacePlannerService(
            self.store,
            budget=PlannerBudget(
                max_query_rewrites=3,
                max_candidates=25,
                max_analyses=10,
                days_back=60,
                phase_budget_seconds={
                    "plan": 5,
                    "discover": 30,
                    "rank": 10,
                    "analyze": 60,
                    "route": 10,
                },
            ),
        )

        plan = planner.build_plan(self.question["id"], trigger="manual")

        self.assertEqual(plan["research_question_id"], self.question["id"])
        self.assertEqual(plan["trigger"], "manual")
        self.assertEqual(plan["max_query_rewrites"], 3)
        self.assertEqual(plan["max_candidates"], 25)
        self.assertEqual(plan["max_analyses"], 10)
        self.assertEqual(plan["days_back"], 60)
        self.assertEqual(plan["query_rewrites"][0], self.question["query_text"])
        self.assertEqual(
            [phase["name"] for phase in plan["phases"]],
            ["plan", "discover", "rank", "analyze", "route"],
        )

    def test_start_run_records_job(self):
        planner = WorkspacePlannerService(self.store)
        result = planner.start_run(self.question["id"], trigger="manual")

        job = self.store.get_job(result["run_id"])
        self.assertEqual(job["job_type"], "workspace_planner")
        self.assertEqual(job["status"], "succeeded")
        self.assertEqual(job["payload_json"]["research_question_id"], self.question["id"])
        self.assertEqual(result["status"], "succeeded")

    def test_discover_and_rank_deduplicates_versioned_candidates(self):
        def fake_search(keywords, *, max_results, days_back):
            return [
                {
                    "id": "2604.20001v1",
                    "title": "Conformal Prediction Under Shift",
                    "abstract": "Conformal prediction with distribution shift guarantees.",
                    "authors": ["Alice"],
                    "categories": ["stat.ML"],
                    "score": 2.0,
                },
                {
                    "id": "2604.20001v2",
                    "title": "Conformal Prediction Under Shift Revised",
                    "abstract": "Conformal prediction with distribution shift guarantees.",
                    "authors": ["Alice"],
                    "categories": ["stat.ML"],
                    "score": 9.0,
                },
                {
                    "id": "2604.20002",
                    "title": "Vision Systems",
                    "abstract": "A vision benchmark paper.",
                    "authors": ["Bob"],
                    "categories": ["cs.CV"],
                    "score": 1.0,
                },
            ]

        planner = WorkspacePlannerService(
            self.store,
            budget=PlannerBudget(max_candidates=2, max_analyses=0),
            search_fn=fake_search,
        )

        plan = planner.build_plan(self.question["id"], trigger="manual")
        candidates, discover_meta = planner._discover_candidates(plan)
        ranked, rank_meta = planner._rank_candidates(candidates, plan)

        self.assertEqual(discover_meta["candidate_count"], 2)
        self.assertEqual(rank_meta["ranked_count"], 2)
        self.assertEqual(ranked[0]["id"], "2604.20001")
        self.assertEqual(len([paper["id"] for paper in ranked]), len({paper["id"] for paper in ranked}))
        self.assertGreaterEqual(ranked[0]["workspace_score"], ranked[1]["workspace_score"])
