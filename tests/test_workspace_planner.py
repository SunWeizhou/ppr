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
                phase_budget_seconds={
                    "plan": 5,
                    "discover": 30,
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
        self.assertEqual(plan["query_rewrites"][0], self.question["query_text"])
        self.assertEqual(
            [phase["name"] for phase in plan["phases"]],
            ["plan", "discover", "analyze", "route"],
        )

    def test_start_run_records_job(self):
        planner = WorkspacePlannerService(self.store)
        result = planner.start_run(self.question["id"], trigger="manual")

        job = self.store.get_job(result["run_id"])
        self.assertEqual(job["job_type"], "workspace_planner")
        self.assertEqual(job["status"], "succeeded")
        self.assertEqual(job["payload_json"]["research_question_id"], self.question["id"])
        self.assertEqual(result["status"], "succeeded")
