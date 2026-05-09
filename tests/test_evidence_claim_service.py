"""Tests for rule-based evidence claim generation."""
import unittest

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
