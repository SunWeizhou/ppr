"""Optional LLM-powered query rewriting with rule-based fallback."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Callable, Optional

try:
    from app.services.ai_providers import NoProvider
except ImportError:
    class NoProvider:  # type: ignore
        pass


@dataclass(frozen=True)
class RewriteResult:
    original: str
    rewritten: str
    was_rewritten: bool = False
    explanation: str = ""
    expanded_terms: list = field(default_factory=list)


# Common ML/AI abbreviations for rule-based expansion
ABBREVIATIONS: dict = {
    "RL": "reinforcement learning",
    "NLP": "natural language processing",
    "CV": "computer vision",
    "GAN": "generative adversarial network",
    "GANs": "generative adversarial networks",
    "GNN": "graph neural network",
    "GNNs": "graph neural networks",
    "LLM": "large language model",
    "LLMs": "large language models",
    "CNN": "convolutional neural network",
    "CNNs": "convolutional neural networks",
    "RNN": "recurrent neural network",
    "RNNs": "recurrent neural networks",
    "VAE": "variational autoencoder",
    "VAEs": "variational autoencoders",
    "BERT": "bidirectional encoder representations from transformers",
    "GPT": "generative pre-trained transformer",
    "RAG": "retrieval augmented generation",
    "RLHF": "reinforcement learning from human feedback",
    "DRL": "deep reinforcement learning",
    "DL": "deep learning",
    "ML": "machine learning",
    "FL": "federated learning",
    "MoE": "mixture of experts",
    "LoRA": "low-rank adaptation",
    "SFT": "supervised fine-tuning",
    "PEFT": "parameter-efficient fine-tuning",
    "ICL": "in-context learning",
    "CoT": "chain of thought",
    "ToT": "tree of thought",
    "KG": "knowledge graph",
    "KGs": "knowledge graphs",
}


class QueryRewriter:
    """Rewrite search queries for better academic search results.

    Uses LLM when available, falls back to rule-based abbreviation expansion.
    """

    def __init__(
        self,
        *,
        provider_factory: Optional[Callable] = None,
    ):
        self._provider_factory = provider_factory

    def rewrite(self, raw_query: str, context: Optional[dict] = None) -> RewriteResult:
        """Rewrite a search query. Returns RewriteResult."""
        raw_query = str(raw_query or "").strip()
        if not raw_query:
            return RewriteResult(original=raw_query, rewritten=raw_query)

        # Try LLM rewrite first
        llm_result = self._llm_rewrite(raw_query, context or {})
        if llm_result is not None:
            return llm_result

        # Fall back to rule-based
        return self._rule_based_rewrite(raw_query)

    def _llm_rewrite(self, query: str, context: dict) -> Optional[RewriteResult]:
        """Attempt LLM-powered rewrite. Returns None if no LLM available."""
        if self._provider_factory is None:
            return None
        try:
            provider = self._provider_factory()
            if provider is None or isinstance(provider, NoProvider):
                return None
            if not hasattr(provider, "chat"):
                return None

            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a search query rewriter for an academic paper search system. "
                        "Given a user's search query, rewrite it to improve search results. "
                        "Strategies: expand abbreviations, add synonyms, convert natural "
                        "language to academic keywords. Return JSON with keys: "
                        "rewritten (the improved query string), "
                        "explanation (brief reason for changes), "
                        "expanded_terms (list of terms you added or expanded). "
                        "If the query is already good, return it unchanged with "
                        "explanation 'No rewrite needed' and empty expanded_terms."
                    ),
                },
                {"role": "user", "content": query},
            ]

            content = provider.chat(messages, page_context=context)
            return self._parse_llm_response(query, content)

        except Exception:
            return None

    @staticmethod
    def _parse_llm_response(original: str, content: str) -> Optional[RewriteResult]:
        """Parse LLM response JSON into RewriteResult."""
        try:
            text = str(content or "").strip()
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                start = text.find("{")
                end = text.rfind("}")
                if start == -1 or end <= start:
                    return None
                parsed = json.loads(text[start: end + 1])

            rewritten = str(parsed.get("rewritten") or original).strip()
            explanation = str(parsed.get("explanation") or "").strip()
            expanded = parsed.get("expanded_terms") or []
            if not isinstance(expanded, list):
                expanded = []
            expanded = [str(t) for t in expanded if t]

            was_rewritten = rewritten.lower() != original.lower()
            return RewriteResult(
                original=original,
                rewritten=rewritten,
                was_rewritten=was_rewritten,
                explanation=explanation,
                expanded_terms=expanded,
            )
        except (json.JSONDecodeError, KeyError, TypeError):
            return None

    @staticmethod
    def _rule_based_rewrite(query: str) -> RewriteResult:
        """Rule-based abbreviation expansion."""
        tokens = query.split()
        expanded_terms: list = []
        new_tokens: list = []

        for token in tokens:
            clean = token.strip(".,;:!?()[]{}\"'")
            if clean in ABBREVIATIONS:
                expansion = ABBREVIATIONS[clean]
                new_tokens.append(f"{expansion} OR {clean}")
                expanded_terms.append(expansion)
            else:
                new_tokens.append(token)

        rewritten = " ".join(new_tokens)
        was_rewritten = rewritten != query

        return RewriteResult(
            original=query,
            rewritten=rewritten,
            was_rewritten=was_rewritten,
            explanation="Abbreviation expansion" if was_rewritten else "",
            expanded_terms=expanded_terms,
        )
