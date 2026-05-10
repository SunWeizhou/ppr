"""Tests for Reading Workbench workspace context and queue landing."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.services.queue_service import QueueService
from app.viewmodels.queue_viewmodel import QueueViewModel
from state_store import StateStore


class ReadingWorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = StateStore(str(Path(self.tmp.name) / "state.db"))
        self.question = self.store.create_research_question(
            "conformal prediction under shift",
            intent_statement="Find papers worth reading deeply.",
        )
        self.store.save_paper_metadata(
            "2604.60001",
            {
                "title": "Candidate Pack Paper",
                "abstract": "This paper studies conformal prediction under shift.",
                "authors": ["Alice"],
                "categories": ["stat.ML"],
            },
        )
        self.store.upsert_queue_item(
            "2604.60001",
            "Inbox",
            source="workspace_planner",
            note="Initial note",
            research_question_id=self.question["id"],
            decision_context="Candidate for research question: conformal prediction under shift",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_queue_update_preserves_workspace_context_when_omitted(self):
        service = QueueService(self.store)

        item, _ = service.update_status(
            "2604.60001",
            "Skim Later",
            source="queue_note",
            note="Read the experiment section.",
        )

        self.assertEqual(item["status"], "Skim Later")
        self.assertEqual(item["note"], "Read the experiment section.")
        self.assertEqual(item["research_question_id"], self.question["id"])
        self.assertEqual(
            item["decision_context"],
            "Candidate for research question: conformal prediction under shift",
        )

    def test_queue_viewmodel_supports_inbox_and_uses_canonical_statuses(self):
        context = QueueViewModel(QueueService(self.store), self.store).to_template_context(
            active_status="Inbox"
        )

        self.assertEqual(context["active_status"], "Inbox")
        self.assertIn("Inbox", context["active_statuses"])
        self.assertNotIn("In Progress", context["active_statuses"])
        self.assertEqual(len(context["queue_items"]), 1)
        self.assertEqual(context["queue_items"][0]["id"], "2604.60001")
        self.assertEqual(context["queue_items"][0]["title"], "Candidate Pack Paper")

    def test_queue_route_renders_inbox_status(self):
        import app.routes.queue as queue_routes
        import web_server

        old_store = queue_routes.STATE_STORE
        queue_routes.STATE_STORE = self.store
        try:
            response = web_server.app.test_client().get("/queue?status=Inbox")
        finally:
            queue_routes.STATE_STORE = old_store

        self.assertEqual(response.status_code, 200)
        body = response.data.decode("utf-8", errors="replace")
        self.assertIn("2604.60001", body)
        self.assertIn("Inbox", body)

    def test_resolved_queue_papers_include_workspace_and_evidence_context(self):
        self.store.create_evidence_claim(
            paper_id="2604.60001",
            research_question_id=self.question["id"],
            claim="The abstract directly mentions conformal prediction under shift.",
            evidence_text="conformal prediction under shift",
            evidence_source="abstract",
            claim_type="factual",
            analyst="rule",
        )

        papers = QueueService(self.store).resolve_papers(status="Inbox")

        paper = papers[0]
        self.assertEqual(paper["research_question_id"], self.question["id"])
        self.assertEqual(paper["active_research_question"]["query_text"], self.question["query_text"])
        self.assertEqual(
            paper["decision_context"],
            "Candidate for research question: conformal prediction under shift",
        )
        self.assertEqual(paper["evidence_summary"]["total"], 1)
        self.assertEqual(paper["evidence_claims"][0]["claim_type"], "factual")
        self.assertEqual(
            paper["detail_url"],
            f"/papers/2604.60001?research_question_id={self.question['id']}",
        )

    def test_queue_template_renders_workspace_decision_contract(self):
        template = Path("templates/queue_research.html").read_text(encoding="utf-8")

        self.assertIn("Candidate Decision Workbench", template)
        self.assertIn("data-research-question-id", template)
        self.assertIn("data-decision-context", template)
        self.assertIn("data-evidence-claims", template)
        self.assertIn("detailResearchQuestion", template)
        self.assertIn("detailEvidenceClaims", template)
        self.assertIn("queueWorkspaceOptions", template)
        self.assertNotIn("In Progress", template)

    def test_reading_viewmodel_active_items_include_workspace_context(self):
        QueueService(self.store).update_status("2604.60001", "Deep Read", source="test")

        from app.viewmodels.reading_viewmodel import ReadingViewModel

        context = ReadingViewModel(self.store).to_template_context(tab="active")

        paper = context["deep_read_items"][0]
        self.assertEqual(paper["research_question_id"], self.question["id"])
        self.assertEqual(paper["active_research_question"]["query_text"], self.question["query_text"])
        self.assertIn("research_question_id=", paper["detail_url"])

    def test_reading_template_preserves_workspace_context(self):
        template = Path("templates/reading.html").read_text(encoding="utf-8")

        self.assertIn("data-research-question-id", template)
        self.assertIn("data-decision-context", template)
        self.assertIn("data-detail-url", template)
        self.assertIn("queueReadingPaper", template)
        self.assertIn("evidence_summary", template)
