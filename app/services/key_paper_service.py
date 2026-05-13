"""Key Paper Service — scores workspace papers and suggests key candidates with explanation."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Optional


class KeyPaperService:
    """Score workspace papers and suggest key candidates with explainable breakdowns.

    Scoring dimensions (D-ENG-5):
      - citation_influence: normalized citation count (0–1)
      - topic_relevance: keyword overlap with workspace query (0–1)
      - user_signals: has takeaway + read status (0–1)
      - recency: newer papers score higher (0–1)

    Each suggestion includes a full breakdown for explainability (D-ENG-6).
    """

    def __init__(self, state_store):
        self._store = state_store

    def suggest_key_papers(
        self,
        research_question_id: int,
        *,
        max_results: int = 5,
        min_score: float = 0.15,
    ) -> list[dict]:
        """Score all read papers and return the top candidates as key paper suggestions."""
        # Gather the workspace query text for topic relevance scoring
        ws = self._store.get_research_question(research_question_id) or {}
        query_text = (ws.get("query_text") or ws.get("title") or "").lower()
        query_tokens = set(query_text.split())

        # Collect papers with "read" relationship
        read_papers = self._store.list_workspace_papers(research_question_id, relationship="read") or []
        already_key = {
            wp["paper_id"]
            for wp in (self._store.list_workspace_papers(research_question_id, relationship="key_confirmed") or [])
        }

        scored: list[dict] = []
        for wp in read_papers:
            pid = wp["paper_id"]
            if pid in already_key:
                continue

            meta = self._store.get_paper_metadata(pid) or {}
            takeaway = self._store.get_reading_takeaway(pid, research_question_id=research_question_id)
            has_takeaway = bool(takeaway and takeaway.get("takeaway_text", "").strip())

            breakdown = self._score_paper(meta, query_tokens, has_takeaway)

            composite = sum(breakdown.values()) / max(len(breakdown), 1)
            if composite < min_score:
                continue

            scored.append({
                "paper_id": pid,
                "title": meta.get("title", pid),
                "authors": meta.get("authors", []),
                "author_text": ", ".join((meta.get("authors") or [])[:3]) or "Unknown",
                "score": round(composite, 3),
                "score_breakdown": {k: round(v, 3) for k, v in breakdown.items()},
                "reason": self._build_reason(breakdown, has_takeaway),
                "has_takeaway": has_takeaway,
            })

        scored.sort(key=lambda p: p["score"], reverse=True)
        return scored[:max_results]

    # ------------------------------------------------------------------
    # Scoring dimensions
    # ------------------------------------------------------------------

    def _score_paper(
        self,
        meta: dict,
        query_tokens: set,
        has_takeaway: bool,
    ) -> dict[str, float]:
        """Compute multi-dimensional score for a single paper."""
        return {
            "citation_influence": self._score_citation(meta),
            "topic_relevance": self._score_topic(meta, query_tokens),
            "user_signals": self._score_user_signals(has_takeaway),
            "recency": self._score_recency(meta),
        }

    @staticmethod
    def _score_citation(meta: dict) -> float:
        """Normalize citation count with log scaling (0–1)."""
        count = int(meta.get("citation_count") or 0)
        if count <= 0:
            return 0.0
        return min(1.0, math.log10(count + 1) / 3.0)  # log10: 1k citations → 1.0

    @staticmethod
    def _score_topic(meta: dict, query_tokens: set) -> float:
        """Score by keyword overlap between paper title/abstract and workspace query."""
        if not query_tokens:
            return 0.3  # neutral baseline when no query tokens
        title = (meta.get("title") or "").lower()
        abstract = (meta.get("abstract") or meta.get("summary") or "")[:500].lower()
        text_tokens = set(title.split() + abstract.split())
        overlap = query_tokens & text_tokens
        if not overlap:
            return 0.0
        return min(1.0, len(overlap) / max(len(query_tokens), 1))

    @staticmethod
    def _score_user_signals(has_takeaway: bool) -> float:
        """User took action beyond reading: takeaway = strong signal."""
        return 0.8 if has_takeaway else 0.3

    @staticmethod
    def _score_recency(meta: dict) -> float:
        """More recent papers score higher. Decay over 10 years."""
        year_str = str(meta.get("year") or "")
        try:
            year = int(year_str[:4])
        except (ValueError, TypeError):
            return 0.3  # neutral baseline
        current = datetime.now(timezone.utc).year
        age = current - year
        if age < 0:
            return 0.8  # future-dated (preprint)
        return max(0.0, 1.0 - age / 10.0)

    # ------------------------------------------------------------------
    # Explainability
    # ------------------------------------------------------------------

    @staticmethod
    def _build_reason(breakdown: dict, has_takeaway: bool) -> str:
        """Generate a human-readable explanation from the scoring breakdown."""
        parts = []
        ci = breakdown.get("citation_influence", 0)
        tr = breakdown.get("topic_relevance", 0)
        us = breakdown.get("user_signals", 0)
        rec = breakdown.get("recency", 0)

        if ci > 0.5:
            parts.append("highly cited")
        elif ci > 0.2:
            parts.append("moderately cited")

        if tr > 0.5:
            parts.append("strong topic match")
        elif tr > 0.2:
            parts.append("relevant to workspace")

        if has_takeaway:
            parts.append("has user takeaway")

        if rec > 0.7:
            parts.append("recent publication")

        return "; ".join(parts) if parts else "Read paper in workspace"
