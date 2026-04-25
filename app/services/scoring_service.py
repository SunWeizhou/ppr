"""Compatibility facade for recommendation scoring components."""

from __future__ import annotations

from enum import Enum
from typing import Iterable, Optional

from arxiv_recommender_v5 import EnhancedScorer


class ScoringVariant(str, Enum):
    KEYWORDS_ONLY = "keywords_only"
    KEYWORDS_SEMANTIC = "keywords_semantic"
    KEYWORDS_SEMANTIC_FEEDBACK = "keywords_semantic_feedback"
    FULL_SCORER = "full_scorer"


def _score_details(paper: dict) -> dict:
    details = paper.get("score_details")
    return details if isinstance(details, dict) else {}


def _component(paper: dict, key: str) -> float:
    try:
        return float(_score_details(paper).get(key, 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _base_score(paper: dict) -> float:
    try:
        return float(paper.get("score", 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def score_papers_for_evaluation(
    papers: Iterable[dict],
    variant: ScoringVariant | str,
    *,
    labels: Optional[dict] = None,
) -> list[dict]:
    """Return evaluation-only ranked papers for an ablation variant.

    This helper never calls the live pipeline or mutates paper records.
    """
    variant = ScoringVariant(variant)
    labels = labels or {}
    scored = []
    for index, paper in enumerate(papers):
        item = dict(paper)
        relevance = _component(item, "relevance")
        semantic = _component(item, "semantic")
        feedback = _component(item, "feedback")
        if variant == ScoringVariant.KEYWORDS_ONLY:
            score = relevance if relevance else _base_score(item)
        elif variant == ScoringVariant.KEYWORDS_SEMANTIC:
            score = relevance + semantic
        elif variant == ScoringVariant.KEYWORDS_SEMANTIC_FEEDBACK:
            score = relevance + semantic + feedback
        else:
            score = _base_score(item)

        item["evaluation_score"] = score
        item["evaluation_rank_source"] = variant.value
        item["_input_index"] = index
        scored.append(item)

    return sorted(scored, key=lambda item: (-item["evaluation_score"], item["_input_index"]))


__all__ = ["EnhancedScorer", "ScoringVariant", "score_papers_for_evaluation"]
