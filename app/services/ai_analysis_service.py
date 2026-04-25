"""Cached paper AI analysis service.

The service is intentionally provider-optional: local workflows and tests must
work without external API keys or network access.
"""

from __future__ import annotations

from state_store import _canonical_paper_id


ANALYSIS_FIELDS = (
    "one_sentence_summary",
    "problem",
    "method",
    "contribution",
    "limitations",
    "why_it_matters",
    "recommended_reading_level",
)


def _fallback_analysis(*, reading_level: str = "skim") -> dict:
    return {
        "one_sentence_summary": "",
        "problem": "",
        "method": "",
        "contribution": "",
        "limitations": "",
        "why_it_matters": "",
        "recommended_reading_level": reading_level,
    }


def _normalize_provider_result(result: dict | None) -> dict:
    normalized = _fallback_analysis()
    if isinstance(result, dict):
        for key in ANALYSIS_FIELDS:
            if result.get(key):
                normalized[key] = str(result[key])
    return normalized


class NoProvider:
    model_name = "none"

    def analyze(self, paper, user_profile=None, recommendation_context=None):
        return _fallback_analysis()


class FakeProvider:
    model_name = "fake-test-provider"

    def analyze(self, paper, user_profile=None, recommendation_context=None):
        title = paper.get("title") or "Untitled paper"
        abstract = paper.get("abstract") or paper.get("summary") or ""
        return {
            "one_sentence_summary": f"Fake analysis for {title}.",
            "problem": "Identifies the research problem from the paper metadata.",
            "method": "Summarizes the method using deterministic test-only logic.",
            "contribution": "Provides a stable generated analysis for local tests.",
            "limitations": "This fake provider does not inspect full paper text.",
            "why_it_matters": abstract[:160] or "It may matter based on the recommendation context.",
            "recommended_reading_level": "skim",
        }


class OpenAICompatibleProvider:
    model_name = "openai-compatible"

    def analyze(self, paper, user_profile=None, recommendation_context=None):
        raise NotImplementedError("OpenAI-compatible provider is not implemented in this PR")


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
            analysis = _normalize_provider_result(result)
            if isinstance(self.provider, NoProvider):
                status = "not_configured"
        except Exception as exc:
            analysis = _fallback_analysis()
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
