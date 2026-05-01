"""Recommendation scoring components including the EnhancedScorer."""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Tuple

from config_manager import get_config
from logger_config import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# EnhancedScorer (moved from arxiv_recommender_v5)
# ---------------------------------------------------------------------------


class EnhancedScorer:
    """Enhanced paper scorer with smart keyword matching."""

    def __init__(self, semantic: Optional[Any] = None, use_semantic: bool = True, topic_weights: Dict[str, float] = None):
        self.semantic = semantic
        self.use_semantic = use_semantic
        self.topic_weights = topic_weights or {}
        # Load dynamic keywords from config
        self._load_keywords()

    def _load_keywords(self):
        """Load keywords from unified config manager."""
        cm = get_config()
        self.CORE_TOPICS = cm.core_keywords
        self.SECONDARY_TOPICS = cm.get_keywords_by_category('secondary')

    def compute_score(self, paper: Dict) -> Tuple[float, Dict]:
        """Compute overall score."""
        relevance = self._compute_relevance(paper)
        semantic_sim = self._compute_semantic_score(paper)
        total = relevance * 0.70 + semantic_sim * 0.30
        return total, {'relevance': round(relevance, 2), 'semantic': round(semantic_sim, 2)}

    @staticmethod
    def _count_keyword(text: str, keyword: str) -> int:
        """Count keyword occurrences with flexible matching."""
        keyword_lower = keyword.lower()
        text_lower = text.lower()

        if ' ' in keyword_lower or '-' in keyword_lower:
            return text_lower.count(keyword_lower)
        else:
            pattern = r'\b' + re.escape(keyword_lower) + r'\b'
            return len(re.findall(pattern, text_lower))

    def _compute_relevance(self, paper: Dict) -> float:
        """Compute topic relevance with smart keyword matching."""
        title = paper.get('title', '').lower()
        abstract = paper.get('abstract', '').lower()
        score = 0.0

        for topic, weight in self.CORE_TOPICS.items():
            title_count = self._count_keyword(title, topic)
            abstract_count = self._count_keyword(abstract, topic)

            if title_count > 0 or abstract_count > 0:
                topic_score = weight * (min(title_count, 3) * 3.0 + min(abstract_count, 3) * 1.0) / 4.0
                score += topic_score

        for topic, weight in self.SECONDARY_TOPICS.items():
            title_count = self._count_keyword(title, topic)
            abstract_count = self._count_keyword(abstract, topic)

            if title_count > 0 or abstract_count > 0:
                topic_score = weight * (min(title_count, 2) * 2.0 + min(abstract_count, 2) * 1.0) / 3.0
                score += topic_score

        if paper.get('_topic_match'):
            score += 2.0

        return min(max(score, 0), 10)

    def _compute_semantic_score(self, paper: Dict) -> float:
        """Compute semantic similarity score (0-10 scale)."""
        if self.use_semantic and self.semantic is not None:
            sim = self.semantic.compute_similarity(paper)
            return sim * 10
        return 0.0


# ---------------------------------------------------------------------------
# Existing scoring components below
# ---------------------------------------------------------------------------


class ScoringVariant(str, Enum):
    KEYWORDS_ONLY = "keywords_only"
    KEYWORDS_SEMANTIC = "keywords_semantic"
    KEYWORDS_SEMANTIC_FEEDBACK = "keywords_semantic_feedback"
    FULL_SCORER = "full_scorer"
    WITHOUT_AFFINITY = "without_affinity"


# ---------------------------------------------------------------------------
# Internal helpers for score_papers_for_evaluation
# ---------------------------------------------------------------------------


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
        elif variant == ScoringVariant.WITHOUT_AFFINITY:
            # Use full score minus affinity component
            score = _base_score(item) - _component(item, "affinity")
        else:
            score = _base_score(item)

        item["evaluation_score"] = score
        item["evaluation_rank_source"] = variant.value
        item["_input_index"] = index
        scored.append(item)

    return sorted(scored, key=lambda item: (-item["evaluation_score"], item["_input_index"]))


def build_recommendation_reason(
    paper: dict,
    *,
    user_profile: dict | None = None,
    run_context: dict | None = None,
) -> dict:
    """Build a structured recommendation reason for a paper.

    Returns a dict with keys:
        reason_summary: str — one-line human-readable summary
        matched_topics: list[str] — core/secondary keywords that matched
        matched_subscriptions: list[str] — subscription names that matched
        zotero_similarity: float — semantic similarity to library (from score_details)
        feedback_signals: list[str] — feedback-related signals
        source_tags: list[str] — source/provenance tags (e.g. "arXiv", "subscription")
    """
    user_profile = user_profile or {}
    run_context = run_context or {}

    title_lower = (paper.get("title") or "").lower()
    abstract_lower = (paper.get("abstract") or paper.get("summary") or "").lower()
    text = title_lower + " " + abstract_lower

    # 1. Matched topics
    matched_topics: list[str] = []
    for category_key in ("core_keywords", "secondary_keywords"):
        keywords_dict = user_profile.get(category_key, {})
        for kw in keywords_dict:
            if kw.lower() in text and kw not in matched_topics:
                matched_topics.append(kw)

    # 2. Matched subscriptions
    matched_subscriptions: list[str] = []
    for search in run_context.get("saved_searches", []):
        query = (search.get("query_text") or search.get("name") or "").lower()
        if query and query in text:
            matched_subscriptions.append(search.get("name") or query)

    # 3. Score details
    score_details = paper.get("score_details") or {}
    zotero_similarity = 0.0
    if isinstance(score_details, dict):
        zotero_similarity = float(score_details.get("semantic", 0) or 0)

    # 4. Feedback signals
    feedback_signals: list[str] = []
    feedback = run_context.get("feedback", {})
    paper_id = paper.get("id") or paper.get("paper_id") or ""
    if paper_id and paper_id in feedback.get("liked", []):
        feedback_signals.append("Previously liked")

    # 5. Source tags
    source_tags: list[str] = []
    source = paper.get("source") or ""
    if source:
        source_tags.append(source)

    # Build summary
    parts: list[str] = []
    if matched_topics:
        parts.append(f"匹配关键词: {', '.join(matched_topics[:3])}")
    if matched_subscriptions:
        parts.append(f"命中订阅: {', '.join(matched_subscriptions[:2])}")
    if zotero_similarity > 0:
        parts.append("与你的论文库语义相似")
    if not parts:
        # Fallback: use relevance_reason if available
        rel = paper.get("relevance_reason") or paper.get("relevance") or ""
        if rel:
            parts.append(rel[:80])
        else:
            parts.append("基于你的研究领域推荐")

    return {
        "reason_summary": "; ".join(parts),
        "matched_topics": matched_topics,
        "matched_subscriptions": matched_subscriptions,
        "zotero_similarity": zotero_similarity,
        "feedback_signals": feedback_signals,
        "source_tags": source_tags,
    }


__all__ = ["EnhancedScorer", "ScoringVariant", "score_papers_for_evaluation", "build_recommendation_reason"]
