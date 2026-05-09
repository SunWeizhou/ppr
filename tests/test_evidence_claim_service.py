"""Tests for rule-based evidence claim generation."""
import tempfile
import unittest
from pathlib import Path

from app.services.evidence_claim_service import EvidenceClaimService


class EvidenceClaimServiceTests(unittest.TestCase):
    def test_rule_claims_use_abstract_and_metadata(self):
        service = EvidenceClaimService()
        paper = {
            "id": "2604.12345v2",
            "title": "Conformal Prediction Under Distribution Shift",
            "abstract": (
                "We study conformal prediction under covariate shift. "
                "The method provides finite-sample coverage guarantees."
            ),
            "categories": ["stat.ML", "cs.LG"],
        }

        claims = service.build_rule_claims(
            paper,
            research_question={
                "id": 7,
                "query_text": "finite-sample conformal prediction under shift",
            },
        )

        self.assertGreaterEqual(len(claims), 3)
        self.assertEqual({claim["paper_id"] for claim in claims}, {"2604.12345"})
        self.assertIn("abstract", {claim["evidence_source"] for claim in claims})
        self.assertIn("metadata", {claim["evidence_source"] for claim in claims})
        self.assertIn("interpretive", {claim["claim_type"] for claim in claims})
        self.assertEqual({claim["analyst"] for claim in claims}, {"rule"})

    def test_rule_claims_degrade_when_abstract_is_missing(self):
        service = EvidenceClaimService()
        claims = service.build_rule_claims(
            {"paper_id": "2604.99999", "title": "Sparse metadata only"},
            research_question={"id": 1, "query_text": "causal inference"},
        )

        self.assertTrue(any(claim["claim_type"] == "gap" for claim in claims))
        self.assertTrue(any("abstract" in claim["claim"].lower() for claim in claims))


class EvidenceClaimAIAnalysisIntegrationTests(unittest.TestCase):
    def test_ai_analysis_service_creates_rule_claims_without_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            from app.services.ai_analysis_service import AIAnalysisService
            from state_store import StateStore

            store = StateStore(str(Path(tmp) / "state.db"))
            question = store.create_research_question("conformal prediction")
            service = AIAnalysisService(store)

            analysis = service.get_or_create_analysis(
                {
                    "id": "2604.12345",
                    "title": "Conformal Prediction Under Shift",
                    "abstract": "We study conformal prediction under covariate shift.",
                    "categories": ["stat.ML"],
                },
                recommendation_context={"research_question": question},
                force=True,
            )

            claims = store.list_evidence_claims(paper_id="2604.12345")
            self.assertGreaterEqual(len(claims), 2)
            self.assertEqual(analysis["evidence_claim_ids"], [claim["id"] for claim in claims])
            self.assertEqual(analysis["status"], "not_configured")
