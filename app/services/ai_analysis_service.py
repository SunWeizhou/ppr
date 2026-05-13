"""Cached paper AI analysis service.

The service is intentionally provider-optional: local workflows and tests must
work without external API keys or network access.
"""

from __future__ import annotations

from app.services.ai_providers import (
    FakeProvider,
    NoProvider,
    OpenAICompatibleProvider,
    fallback_analysis,
    normalize_analysis_result,
)
from app.services.evidence_claim_service import EvidenceClaimService
from app.data._constants import canonical_paper_id as _canonical_paper_id


class AIAnalysisService:
    def __init__(self, state_store, provider=None, prompt_version: str = "v1"):
        self.state_store = state_store
        self.provider = provider if provider is not None else NoProvider()
        self.prompt_version = prompt_version

    def get_analysis(self, paper_id: str) -> dict | None:
        return self.state_store.get_paper_ai_analysis(paper_id)

    def get_or_create_analysis(
        self,
        paper: dict,
        user_profile: dict | None = None,
        recommendation_context: dict | None = None,
        *,
        force: bool = False,
    ) -> dict:
        paper = dict(paper or {})
        paper_id = _canonical_paper_id(paper.get("id") or paper.get("paper_id") or "")
        if not paper_id:
            raise ValueError("Missing paper id")
        paper["id"] = paper_id

        if not force:
            cached = self.get_analysis(paper_id)
            if cached:
                has_real_provider = not isinstance(self.provider, NoProvider)
                if cached.get("status") != "not_configured" or not has_real_provider:
                    return cached

        model_name = getattr(self.provider, "model_name", self.provider.__class__.__name__)
        status = "ok"
        error_text = ""
        try:
            result = self.provider.analyze(
                paper,
                user_profile=user_profile,
                recommendation_context=recommendation_context,
            )
            analysis = normalize_analysis_result(result)
            if isinstance(self.provider, NoProvider):
                status = "not_configured"
        except Exception as exc:
            analysis = fallback_analysis()
            status = "failed"
            error_text = str(exc)

        # Build rule-based evidence claims for every analysis path
        evidence_claim_ids = []
        research_question = {}
        if isinstance(recommendation_context, dict):
            research_question = recommendation_context.get("research_question") or {}
        claim_service = EvidenceClaimService()
        try:
            rq_id = research_question.get("id") if isinstance(research_question, dict) else None
            if rq_id is not None:
                self.state_store.delete_evidence_claims(
                    paper_id=paper_id, research_question_id=rq_id
                )
            else:
                self.state_store.delete_evidence_claims(paper_id=paper_id)
            for claim in claim_service.build_rule_claims(
                paper,
                research_question=research_question,
            ):
                stored = self.state_store.create_evidence_claim(**claim)
                evidence_claim_ids.append(stored["id"])
        except Exception:
            evidence_claim_ids = []

        result = self.state_store.upsert_paper_ai_analysis(
            paper_id,
            analysis,
            model_name=model_name,
            prompt_version=self.prompt_version,
            status=status,
            error_text=error_text,
            evidence_claim_ids=evidence_claim_ids,
            confidence=None,
        )
        # Record interaction event
        self.state_store.record_event(
            "ai_analysis_generated",
            paper_id,
            {"model_name": model_name, "prompt_version": self.prompt_version, "status": status},
        )
        return result
