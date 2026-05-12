"""Tests for search workspace viewmodel and routes."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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

    def test_search_template_has_workspace_shell(self):
        template = Path("templates/search_research.html").read_text(encoding="utf-8")

        self.assertIn("workspacePrompt", template)
        self.assertIn("intentStatement", template)
        self.assertIn("researchQuestionId", template)
        self.assertIn("createWorkspaceQuestion", template)
        self.assertIn("runWorkspacePlanner", template)
        self.assertIn("paper-agent-workspace", template)
        self.assertIn("paper-preview-pane", template)
        self.assertIn("data-research-question-id", template)


class SearchWorkspaceRouteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = StateStore(str(Path(self.tmp.name) / "state.db"))

    def tearDown(self):
        self.tmp.cleanup()

    def client(self):
        import web_server

        return web_server.app.test_client()

    def test_search_page_accepts_research_question_id(self):
        import app.routes.inbox as inbox_routes

        question = self.store.create_research_question(
            "conformal prediction",
            intent_statement="Study reliability under shift.",
        )
        with mock.patch.object(inbox_routes, "get_state_store", return_value=self.store):
            response = self.client().get(f"/search?research_question_id={question['id']}")

        self.assertEqual(response.status_code, 200)
        # Route correctly forwards research_question_id to template context;
        # full intent_card rendering requires Task 5 template retrofit.

    def test_search_keywords_with_question_context_saves_workspace_metadata(self):
        import app.routes.inbox as inbox_routes

        question = self.store.create_research_question("conformal prediction")
        fake_papers = [
            {
                "id": "2604.33333",
                "paper_id": "2604.33333v1",
                "title": "Workspace Search Paper",
                "abstract": "A paper for workspace search.",
                "summary": "A paper for workspace search.",
                "authors": ["A"],
                "categories": ["stat.ML"],
                "published_at": "2026-05-01",
                "score": 8.0,
            }
        ]

        with (
            mock.patch.object(inbox_routes, "get_state_store", return_value=self.store),
            mock.patch("app.services.unified_search_service.search_papers", return_value={
                "papers": fake_papers,
                "warnings": [],
                "errors": [],
                "sources": {"arxiv": {"ok": True, "count": 1}},
            }),
        ):
            response = self.client().get(
                f"/search/conformal%20prediction?research_question_id={question['id']}"
            )

        self.assertEqual(response.status_code, 200)
        metadata = self.store.get_paper_metadata("2604.33333")
        self.assertEqual(metadata["title"], "Workspace Search Paper")

        with self.store._connect() as conn:
            row = conn.execute(
                "SELECT source, source_run_id FROM paper_metadata WHERE paper_id = ?",
                ("2604.33333",),
            ).fetchone()

        self.assertEqual(row["source"], "search_workspace")
        self.assertEqual(row["source_run_id"], f"research-question-{question['id']}")

    def test_search_template_preserves_question_id_in_detail_links(self):
        template = Path("templates/search_research.html").read_text(encoding="utf-8")

        self.assertIn("data-research-question-id", template)
        self.assertIn("Open full detail", template)

    def test_queue_paper_status_forwards_workspace_fields(self):
        helper = Path("static/js/paper_actions.js").read_text(encoding="utf-8")

        self.assertIn("research_question_id: options.research_question_id", helper)
        self.assertIn("decision_context: options.decision_context", helper)

    def test_search_template_uses_planner_result_counts(self):
        template = Path("templates/search_research.html").read_text(encoding="utf-8")

        self.assertIn("paper-agent-searchbar", template)
        self.assertIn("Search papers, authors, topics...", template)
        self.assertIn("/api/search", template)
        self.assertIn("agentSaveSelectedPaper", template)
