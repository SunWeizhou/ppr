"""Tests for Paper Detail evidence-center workspace context."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.viewmodels.paper_viewmodel import PaperViewModel
from state_store import StateStore


class PaperDetailEvidenceViewModelTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = StateStore(str(Path(self.tmp.name) / "state.db"))
        self.paper_id = "2604.12345"
        self.store.save_paper_metadata(
            self.paper_id,
            {
                "title": "Evidence Center Paper",
                "abstract": "This paper studies conformal prediction under distribution shift.",
                "authors": ["Alice"],
                "categories": ["stat.ML"],
            },
        )
        self.question = self.store.create_research_question(
            "conformal prediction under shift",
            intent_statement="Find finite-sample reliability results.",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_detail_context_loads_evidence_claims_for_active_question(self):
        first = self.store.create_evidence_claim(
            paper_id=self.paper_id,
            research_question_id=self.question["id"],
            claim="The paper addresses conformal prediction under shift.",
            evidence_text="conformal prediction under distribution shift",
            evidence_source="abstract",
            claim_type="factual",
            analyst="rule",
        )
        second = self.store.create_evidence_claim(
            paper_id=self.paper_id,
            research_question_id=self.question["id"],
            claim="The paper may require a deep read for guarantees.",
            evidence_text="finite-sample reliability results",
            evidence_source="metadata",
            claim_type="interpretive",
            analyst="rule",
        )
        self.store.upsert_paper_ai_analysis(
            self.paper_id,
            {
                "one_sentence_summary": "A conformal prediction paper.",
                "problem": "Distribution shift.",
                "method": "Finite-sample analysis.",
                "contribution": "Reliability framing.",
                "limitations": "Abstract-only evidence.",
                "why_it_matters": "It matches the workspace question.",
                "recommended_reading_level": "deep_read",
            },
            model_name="test-model",
            prompt_version="test",
            evidence_claim_ids=[second["id"], first["id"]],
        )

        ctx = PaperViewModel(self.store).to_detail_context(
            f"{self.paper_id}v2",
            research_question_id=self.question["id"],
        )

        paper = ctx["paper"]
        self.assertEqual(paper["active_research_question"]["id"], self.question["id"])
        self.assertEqual(paper["active_research_question_id"], self.question["id"])
        self.assertEqual([claim["id"] for claim in paper["evidence_claims"]], [second["id"], first["id"]])
        self.assertEqual(paper["evidence_summary"]["total"], 2)
        self.assertEqual(paper["evidence_summary"]["by_type"]["factual"], 1)
        self.assertEqual(paper["evidence_summary"]["by_type"]["interpretive"], 1)

    def test_detail_context_uses_queue_question_when_url_has_no_question(self):
        self.store.upsert_queue_item(
            self.paper_id,
            "Deep Read",
            research_question_id=self.question["id"],
            decision_context="Core paper for this workspace.",
        )

        ctx = PaperViewModel(self.store).to_detail_context(self.paper_id)

        paper = ctx["paper"]
        self.assertEqual(paper["active_research_question_id"], self.question["id"])
        self.assertEqual(paper["decision_context"], "Core paper for this workspace.")
        self.assertEqual(paper["workspace_context"]["source"], "queue")


class PaperDetailEvidenceRouteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = StateStore(str(Path(self.tmp.name) / "state.db"))
        self.paper_id = "2604.55555"
        self.store.save_paper_metadata(
            self.paper_id,
            {
                "title": "Route Evidence Paper",
                "abstract": "Route-level evidence rendering.",
                "authors": ["Bob"],
                "categories": ["cs.AI"],
            },
        )
        self.question = self.store.create_research_question("route evidence")
        self.store.create_evidence_claim(
            paper_id=self.paper_id,
            research_question_id=self.question["id"],
            claim="Route evidence claim is visible.",
            evidence_text="Route-level evidence rendering.",
            evidence_source="abstract",
            claim_type="factual",
            analyst="rule",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_route_passes_research_question_id_to_detail_context(self):
        import app.routes.inbox as inbox_routes
        from app.viewmodels.paper_viewmodel import PaperViewModel
        import web_server

        captured = {}
        original = PaperViewModel.to_detail_context

        def spy(viewmodel, paper_id, research_question_id=None):
            captured["paper_id"] = paper_id
            captured["research_question_id"] = research_question_id
            return original(viewmodel, paper_id, research_question_id=research_question_id)

        with (
            mock.patch.object(inbox_routes, "get_state_store", return_value=self.store),
            mock.patch.object(PaperViewModel, "to_detail_context", spy),
        ):
            response = web_server.app.test_client().get(
                f"/papers/{self.paper_id}?research_question_id={self.question['id']}"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(captured["paper_id"], self.paper_id)
        self.assertEqual(captured["research_question_id"], self.question["id"])


class PaperDetailEvidenceTemplateTests(unittest.TestCase):
    def test_template_contains_evidence_center_contract(self):
        template = Path("templates/paper_detail.html").read_text(encoding="utf-8")

        self.assertIn("Evidence-Linked Claims", template)
        self.assertIn("paper.get('evidence_claims'", template)
        self.assertIn("active_research_question", template)
        self.assertIn("data-research-question-id", template)
        self.assertIn("createEvidenceClaimsDOM", template)
        self.assertIn("decision_context", template)


class PaperDetailEvidenceRenderingTests(unittest.TestCase):
    def test_route_renders_question_and_evidence_claim(self):
        import app.routes.inbox as inbox_routes
        import web_server

        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(str(Path(tmp) / "state.db"))
            paper_id = "2604.66666"
            store.save_paper_metadata(
                paper_id,
                {
                    "title": "Rendered Evidence Paper",
                    "abstract": "Rendered evidence appears in the abstract.",
                    "authors": ["Carol"],
                    "categories": ["stat.ML"],
                },
            )
            question = store.create_research_question("rendered evidence question")
            store.create_evidence_claim(
                paper_id=paper_id,
                research_question_id=question["id"],
                claim="Rendered evidence claim is visible.",
                evidence_text="Rendered evidence appears in the abstract.",
                evidence_source="abstract",
                claim_type="factual",
                analyst="rule",
            )

            with mock.patch.object(inbox_routes, "get_state_store", return_value=store):
                response = web_server.app.test_client().get(
                    f"/papers/{paper_id}?research_question_id={question['id']}"
                )

        body = response.data.decode("utf-8", errors="replace")
        self.assertEqual(response.status_code, 200)
        self.assertIn("rendered evidence question", body)
        self.assertIn("Rendered evidence claim is visible.", body)
