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
from state_store import _canonical_paper_id


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

        return self.state_store.upsert_paper_ai_analysis(
            paper_id,
            analysis,
            model_name=model_name,
            prompt_version=self.prompt_version,
            status=status,
            error_text=error_text,
        )
