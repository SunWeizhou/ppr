"""Tests for search workspace viewmodel and routes."""
import tempfile
import unittest
from pathlib import Path

from app.viewmodels.search_viewmodel import SearchViewModel
from state_store import StateStore


class SearchWorkspaceViewModelTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = StateStore(str(Path(self.tmp.name) / "state.db"))

    def tearDown(self):
        self.tmp.cleanup()

    def test_search_context_includes_workspace_fields(self):
        question = self.store.create_research_question(
            "conformal prediction under shift",
            intent_statement="Find robust finite-sample guarantees.",
        )
        self.store.upsert_queue_item(
            "2604.11111",
            "Deep Read",
            research_question_id=question["id"],
        )

        context = SearchViewModel(self.store).to_template_context(
            [],
            [],
            research_question_id=question["id"],
            planner_result={"run_id": "run-1", "status": "succeeded"},
        )

        self.assertEqual(context["active_research_question"]["id"], question["id"])
        self.assertEqual(context["intent_card"]["query_text"], question["query_text"])
        self.assertEqual(context["workspace_stats"]["active_reading_count"], 1)
        self.assertEqual(context["planner_result"]["run_id"], "run-1")
        self.assertEqual(context["workspace_brief"]["mode"], "empty")

    def test_workspace_brief_summarizes_search_results(self):
        question = self.store.create_research_question("causal inference")
        context = SearchViewModel(self.store).to_template_context(
            [
                {
                    "id": "2604.12345",
                    "title": "Causal Paper",
                    "abstract": "A method for causal inference.",
                    "authors": ["A"],
                    "categories": ["stat.ML"],
                    "score": 4.2,
                }
            ],
            ["causal", "inference"],
            research_question_id=question["id"],
        )

        brief = context["workspace_brief"]
        self.assertEqual(brief["mode"], "results")
        self.assertEqual(brief["candidate_count"], 1)
        self.assertIn("stat.ML", brief["top_categories"])
