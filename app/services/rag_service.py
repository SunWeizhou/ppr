"""Embedding and RAG services.

Builds on the existing paper_embeddings storage layer to generate and
retrieve embeddings, then perform workspace-level semantic retrieval over
abstracts, AI analyses, and user takeaways (D-ENG-3, D-ENG-4).
"""

from __future__ import annotations

import json
import math
import struct
from collections import Counter
from typing import Optional


class EmbeddingService:
    """Generate and store paper embeddings.

    The storage layer (paper_embeddings table) already exists in StateStore.
    This service adds:
      - Batch embedding generation from paper content
      - Provider-agnostic embedding via the AI provider's chat endpoint
      - Deterministic keyword-vector fallback when no provider is available
    """

    def __init__(self, state_store):
        self._store = state_store

    def ensure_embeddings(
        self,
        research_question_id: int,
        *,
        provider=None,
    ) -> int:
        """Generate embeddings for workspace papers that lack them.

        Returns the number of new embeddings created.
        """
        papers = self._store.list_workspace_papers(research_question_id) or []
        count = 0
        for wp in papers:
            pid = wp["paper_id"]
            existing = self._store.get_paper_embedding(pid)
            if existing and existing[0]:
                continue  # already has embedding
            content = self._build_embedding_text(pid, research_question_id)
            if not content:
                continue
            embedding, model_name = self._generate_embedding(content, provider=provider)
            if embedding:
                self._store.save_paper_embedding(pid, embedding, model_name=model_name)
                count += 1
        return count

    def _build_embedding_text(self, paper_id: str, rq_id: int) -> str:
        """Build a combined text representation for embedding.

        Sources: abstract + AI analysis + user takeaway (D-ENG-4).
        """
        meta = self._store.get_paper_metadata(paper_id) or {}
        parts = []

        abstract = meta.get("abstract") or meta.get("summary") or ""
        if abstract:
            parts.append(f"Abstract: {abstract}")

        # AI analysis fields
        analysis = self._store.get_paper_ai_analysis(paper_id) or {}
        for field in ("one_sentence_summary", "problem", "method", "contribution"):
            val = analysis.get(field, "")
            if val:
                parts.append(f"{field}: {val}")

        # User takeaway
        takeaway = self._store.get_reading_takeaway(paper_id, research_question_id=rq_id)
        if takeaway and takeaway.get("takeaway_text", "").strip():
            parts.append(f"Takeaway: {takeaway['takeaway_text']}")

        title = meta.get("title", "")
        if title:
            parts.insert(0, f"Title: {title}")

        return "\n\n".join(parts)

    def _generate_embedding(self, text: str, *, provider=None) -> tuple[Optional[bytes], str]:
        """Generate an embedding vector. Falls back to keyword fingerprint.

        When an AI provider is available, generates via API. Otherwise
        creates a deterministic keyword-frequency fingerprint that supports
        basic similarity search.

        Returns (embedding_bytes, model_name).
        """
        if provider is not None and hasattr(provider, "chat"):
            try:
                result = provider.chat([
                    {
                        "role": "system",
                        "content": (
                            "Generate a dense embedding vector for the following text. "
                            "Return it as a JSON array of 128 floats. "
                            "Respond with ONLY the JSON array, no other text."
                        ),
                    },
                    {"role": "user", "content": text[:2000]},
                ])
                if result:
                    vec = json.loads(result.strip())
                    if isinstance(vec, list) and len(vec) == 128:
                        provider_name = getattr(provider, "model_name", "unknown")
                        return struct.pack(f"{len(vec)}f", *vec), f"provider:{provider_name}"
            except Exception:
                pass

        # Deterministic keyword-frequency fallback fingerprint
        return self._keyword_fingerprint(text), "keyword-fallback-v1"

    @staticmethod
    def _keyword_fingerprint(text: str) -> bytes:
        """Create a deterministic keyword-frequency fingerprint.

        Produces a 256-dimensional float vector where each dimension
        represents the TF score for a common academic keyword.
        """
        keywords = [
            "learning", "model", "network", "data", "deep", "neural",
            "training", "method", "algorithm", "optimization", "attention",
            "transformer", "classification", "regression", "prediction",
            "feature", "representation", "generative", "reinforcement",
            "supervised", "unsupervised", "semi-supervised", "transfer",
            "federated", "privacy", "differential", "distributed",
            "graph", "convolutional", "recurrent", "lstm", "gru",
            "encoder", "decoder", "autoencoder", "variational",
            "bayesian", "probabilistic", "density", "sampling",
            "latent", "embedding", "token", "sequence",
            "normalization", "batch", "layer", "dropout", "regularization",
            "loss", "objective", "gradient", "backpropagation",
            "convergence", "generalization", "overfitting", "underfitting",
            "evaluation", "benchmark", "dataset", "metric", "accuracy",
            "precision", "recall", "f1", "auc", "roc", "perplexity",
            "nlp", "vision", "multimodal", "robotics",
            "recommendation", "system", "search", "ranking", "filtering",
            "knowledge", "reasoning", "inference", "causal", "explainability",
            "fairness", "robustness", "efficiency", "scalability",
            "architecture", "design", "framework", "pipeline", "workflow",
            "experiment", "result", "analysis", "comparison", "ablation",
            "baseline", "state-of-the-art", "sota", "performance",
        ]

        words = text.lower().split()
        word_freq = Counter(words)
        total = len(words) or 1
        vec = [word_freq.get(kw, 0) / total for kw in keywords]

        # Pad to 256 dimensions
        while len(vec) < 256:
            vec.append(0.0)
        return struct.pack(f"{len(vec)}f", *vec)


class RagRetrievalService:
    """Workspace-level semantic retrieval over read papers.

    Retrieves papers using embedding similarity when available, with
    keyword-based fallback.
    """

    def __init__(self, state_store):
        self._store = state_store

    def query(
        self,
        research_question_id: int,
        query_text: str,
        *,
        max_results: int = 5,
        paper_ids: Optional[list] = None,
    ) -> list[dict]:
        """Retrieve the most relevant read/key papers for a query.

        If paper_ids is provided, only those papers are considered (RAG Q&A mode).
        Otherwise falls back to all read + key_confirmed workspace papers.
        """
        query_text = query_text.strip()
        if not query_text:
            return []

        query_tokens = set(query_text.lower().split())

        # Collect candidate papers
        candidates: list[dict] = []
        if paper_ids is not None:
            # RAG Q&A mode: only the user-selected papers
            target_ids = set(paper_ids)
            for pid in target_ids:
                meta = self._store.get_paper_metadata(pid) or {}
                if meta:
                    candidates.append({
                        "paper_id": pid,
                        "title": meta.get("title", pid),
                        "authors": meta.get("authors", []),
                        "author_text": ", ".join((meta.get("authors") or [])[:3]) or "Unknown",
                        "abstract": meta.get("abstract") or meta.get("summary", ""),
                        "relationship": "rag_selected",
                        "score": 0.0,
                    })
        else:
            for rel in ("read", "key_confirmed"):
                for wp in (self._store.list_workspace_papers(research_question_id, relationship=rel) or []):
                    meta = self._store.get_paper_metadata(wp["paper_id"]) or {}
                    candidates.append({
                        "paper_id": wp["paper_id"],
                        "title": meta.get("title", wp["paper_id"]),
                        "authors": meta.get("authors", []),
                        "author_text": ", ".join((meta.get("authors") or [])[:3]) or "Unknown",
                        "abstract": meta.get("abstract") or meta.get("summary", ""),
                        "relationship": wp.get("relationship", rel),
                        "score": 0.0,
                    })

        if not candidates:
            return []

        # Build enriched text for scoring (memo has higher weight)
        for c in candidates:
            enriched = self._build_rag_context(c["paper_id"])
            c["_rag_context"] = enriched

        # Try embedding similarity
        query_embedding = self._make_query_fingerprint(query_text)
        for c in candidates:
            emb = self._store.get_paper_embedding(c["paper_id"])
            if emb and emb[0]:
                c["score"] = self._cosine_similarity(query_embedding, emb[0])
            else:
                c["score"] = self._keyword_score_enriched(c, query_tokens)

        candidates.sort(key=lambda c: c["score"], reverse=True)
        return candidates[:max_results]

    def _build_rag_context(self, paper_id: str) -> str:
        """Build enriched text for a paper for RAG retrieval.

        Memo / takeaway text is weighted higher (duplicated) because it's
        the most valuable content for literature review.
        """
        meta = self._store.get_paper_metadata(paper_id) or {}
        parts = []

        title = meta.get("title", "")
        if title:
            parts.append(f"Title: {title}")

        abstract = meta.get("abstract") or meta.get("summary", "")
        if abstract:
            parts.append(f"Abstract: {abstract}")

        # AI analysis fields
        analysis = self._store.get_paper_ai_analysis(paper_id) or {}
        for field in ("one_sentence_summary", "problem", "method", "contribution"):
            val = analysis.get(field, "")
            if val:
                parts.append(f"{field}: {val}")

        # Memo / takeaway — duplicated for higher TF weight
        takeaway = self._store.get_reading_takeaway(paper_id)
        if takeaway and takeaway.get("takeaway_text", "").strip():
            memo_text = f"Memo: {takeaway['takeaway_text']}"
            parts.append(memo_text)
            parts.append(memo_text)  # duplicate for 2x weight

        return "\n\n".join(parts)

    @staticmethod
    def _keyword_score_enriched(paper: dict, query_tokens: set) -> float:
        """Keyword overlap using enriched RAG context (includes memo dupe)."""
        if not query_tokens:
            return 0.0
        text = (
            (paper.get("title") or "").lower() + " " +
            (paper.get("_rag_context") or paper.get("abstract") or "")[:2000].lower()
        )
        text_tokens = set(text.split())
        overlap = query_tokens & text_tokens
        if not overlap:
            return 0.0
        return min(1.0, len(overlap) / max(len(query_tokens), 1))

    @staticmethod
    def _make_query_fingerprint(text: str) -> bytes:
        """Create a keyword fingerprint for the query text."""
        return EmbeddingService._keyword_fingerprint(text)

    @staticmethod
    def _keyword_score(paper: dict, query_tokens: set) -> float:
        """Simple keyword overlap score between query and paper content."""
        if not query_tokens:
            return 0.0
        text = (
            (paper.get("title") or "").lower() + " " +
            (paper.get("abstract") or "")[:500].lower()
        )
        text_tokens = set(text.split())
        overlap = query_tokens & text_tokens
        if not overlap:
            return 0.0
        return min(1.0, len(overlap) / max(len(query_tokens), 1))

    @staticmethod
    def _cosine_similarity(vec1_bytes: bytes, vec2_bytes: bytes) -> float:
        """Compute cosine similarity between two packed float vectors.

        If the vectors have incompatible dimensions the result is 0.0
        to avoid silently producing meaningless scores.
        """
        try:
            dim1 = len(vec1_bytes) // 4
            dim2 = len(vec2_bytes) // 4
            if dim1 != dim2:
                return 0.0
            v1 = list(struct.unpack(f"{dim1}f", vec1_bytes))
            v2 = list(struct.unpack(f"{dim2}f", vec2_bytes))
        except struct.error:
            return 0.0
        dot = sum(a * b for a, b in zip(v1, v2))
        n1 = math.sqrt(sum(a * a for a in v1))
        n2 = math.sqrt(sum(b * b for b in v2))
        if n1 == 0 or n2 == 0:
            return 0.0
        return dot / (n1 * n2)
