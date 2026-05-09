"""Tests for workspace bounded planner."""
import tempfile
import unittest
from pathlib import Path

from app.services.workspace_planner import PlannerBudget, WorkspacePlannerService
from state_store import StateStore


def _fake_papers():
    return [
        {
            "id": "2604.10001v1",
            "title": "Conformal Prediction Under Shift",
            "abstract": "This paper studies conformal prediction under distribution shift.",
            "authors": ["Alice"],
            "categories": ["stat.ML"],
            "score": 8.0,
            "summary": "Conformal prediction under shift.",
            "link": "https://arxiv.org/abs/2604.10001",
        },
        {
            "id": "2604.10002",
            "title": "Unrelated Vision Benchmark",
            "abstract": "This paper studies image classification.",
            "authors": ["Bob"],
            "categories": ["cs.CV"],
            "score": 1.0,
            "summary": "Image classification.",
            "link": "https://arxiv.org/abs/2604.10002",
        },
    ]


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
        def fake_search(keywords, *, max_results, days_back):
            return []

        planner = WorkspacePlannerService(self.store, search_fn=fake_search)
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

    def test_start_run_executes_real_phases_without_skipped_results(self):
        def fake_search(keywords, *, max_results, days_back):
            self.assertLessEqual(max_results, 10)
            self.assertEqual(days_back, 60)
            return _fake_papers()

        planner = WorkspacePlannerService(
            self.store,
            budget=PlannerBudget(max_candidates=2, max_analyses=1, days_back=60),
            search_fn=fake_search,
        )

        result = planner.start_run(self.question["id"], trigger="manual")

        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(
            [phase["name"] for phase in result["phase_results"]],
            ["plan", "discover", "rank", "analyze", "route"],
        )
        self.assertNotIn("skipped", [phase["status"] for phase in result["phase_results"]])
        self.assertEqual(result["candidate_count"], 2)
        self.assertEqual(result["queued_count"], 2)
        self.assertEqual(result["analysis_count"], 1)

    def test_start_run_routes_candidates_to_inbox_and_creates_evidence(self):
        def fake_search(keywords, *, max_results, days_back):
            return [
                {
                    "id": "2604.30001",
                    "title": "Conformal Prediction Candidate",
                    "abstract": "This paper studies conformal prediction under distribution shift.",
                    "authors": ["Alice"],
                    "categories": ["stat.ML"],
                    "score": 8.0,
                }
            ]

        planner = WorkspacePlannerService(
            self.store,
            budget=PlannerBudget(max_candidates=1, max_analyses=1),
            search_fn=fake_search,
        )

        result = planner.start_run(self.question["id"], trigger="manual")

        item = self.store.get_queue_item("2604.30001")
        metadata = self.store.get_paper_metadata("2604.30001")
        analysis = self.store.get_paper_ai_analysis("2604.30001")
        claims = self.store.list_evidence_claims(paper_id="2604.30001")

        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(item["status"], "Inbox")
        self.assertEqual(item["source"], "workspace_planner")
        self.assertEqual(item["research_question_id"], self.question["id"])
        self.assertIn("conformal prediction", item["decision_context"])
        self.assertEqual(metadata["title"], "Conformal Prediction Candidate")
        self.assertIsNotNone(analysis)
        self.assertGreaterEqual(len(claims), 1)
        self.assertEqual(claims[0]["research_question_id"], self.question["id"])
        self.assertTrue(result["recommendation_run_id"])

    def test_start_run_degrades_when_discovery_fails(self):
        def failing_search(keywords, *, max_results, days_back):
            raise RuntimeError("arxiv unavailable")

        planner = WorkspacePlannerService(
            self.store,
            budget=PlannerBudget(max_candidates=3, max_analyses=1),
            search_fn=failing_search,
        )

        result = planner.start_run(self.question["id"], trigger="manual")
        job = self.store.get_job(result["run_id"])

        self.assertEqual(result["status"], "degraded")
        self.assertEqual(job["status"], "degraded")
        self.assertEqual(result["candidate_count"], 0)
        self.assertEqual(result["queued_count"], 0)
        discover = next(phase for phase in result["phase_results"] if phase["name"] == "discover")
        route = next(phase for phase in result["phase_results"] if phase["name"] == "route")
        self.assertEqual(discover["status"], "degraded")
        self.assertIn("arxiv unavailable", discover["error"])
        self.assertEqual(route["queued_count"], 0)


class FailingAnalysisService:
    def get_or_create_analysis(self, paper, user_profile=None, recommendation_context=None, *, force=False):
        raise RuntimeError("analysis unavailable")


class WorkspacePlannerDegradationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = StateStore(str(Path(self.tmp.name) / "state.db"))
        self.question = self.store.create_research_question(
            "conformal prediction under distribution shift",
            intent_statement="Find robust methods and finite-sample guarantees.",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_start_run_routes_candidates_when_analysis_fails(self):
        def fake_search(keywords, *, max_results, days_back):
            return [
                {
                    "id": "2604.40001",
                    "title": "Analysis Failure Candidate",
                    "abstract": "Conformal prediction paper.",
                    "authors": ["Alice"],
                    "categories": ["stat.ML"],
                    "score": 8.0,
                }
            ]

        planner = WorkspacePlannerService(
            self.store,
            budget=PlannerBudget(max_candidates=1, max_analyses=1),
            search_fn=fake_search,
            analysis_service=FailingAnalysisService(),
        )

        result = planner.start_run(self.question["id"], trigger="manual")
        item = self.store.get_queue_item("2604.40001")
        analyze = next(phase for phase in result["phase_results"] if phase["name"] == "analyze")

        self.assertEqual(result["status"], "degraded")
        self.assertEqual(item["status"], "Inbox")
        self.assertEqual(result["queued_count"], 1)
        self.assertEqual(analyze["status"], "degraded")
        self.assertEqual(analyze["analysis_count"], 0)
        self.assertIn("analysis unavailable", analyze["errors"][0])
