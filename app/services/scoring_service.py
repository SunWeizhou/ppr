"""Compatibility facade for recommendation scoring components."""

from __future__ import annotations

import re
from enum import Enum
from typing import Dict, Iterable, List, Optional

from arxiv_recommender_v5 import EnhancedScorer


class ScoringVariant(str, Enum):
    KEYWORDS_ONLY = "keywords_only"
    KEYWORDS_SEMANTIC = "keywords_semantic"
    KEYWORDS_SEMANTIC_FEEDBACK = "keywords_semantic_feedback"
    FULL_SCORER = "full_scorer"


# ---------------------------------------------------------------------------
# Structured recommendation reason builder
# ---------------------------------------------------------------------------


def build_recommendation_reason(
    paper: dict,
    user_profile: dict | None = None,
    run_context: dict | None = None,
) -> dict:
    """Build a structured recommendation reason for a paper.

    Returns a dict matching the PRD_V2 spec (section 10):
        reason_summary, matched_topics, matched_subscriptions,
        zotero_similarity, feedback_signals, source_tags

    When *user_profile* or *run_context* is None the function returns the
    richest explanation it can from the paper dict alone.
    """
    user_profile = user_profile or {}
    run_context = run_context or {}

    # ---- matched core / secondary topics ----
    matched_topics: List[str] = []
    matched_secondary: List[str] = []

    breakdown = _safe_breakdown(paper)
    for item in breakdown:
        if item.get("type") == "core_topic":
            topic = _extract_topic_from_text(item.get("text", ""))
            if topic and topic not in matched_topics:
                matched_topics.append(topic)
        elif item.get("type") == "secondary_topic":
            topic = _extract_topic_from_text(item.get("text", ""))
            if topic and topic not in matched_secondary:
                matched_secondary.append(topic)

    # If breakdown is empty, try raw keyword matching against the paper text
    if not matched_topics and not matched_secondary:
        matched_topics, matched_secondary = _match_keywords_from_profile(
            paper, user_profile
        )

    # ---- Zotero / semantic similarity ----
    zotero_similarity: float = round(
        float(_score_details(paper).get("semantic", 0) or 0), 2
    )
    # semantic score is on 0-10 scale; convert to 0-1 for zotero_similarity
    if zotero_similarity > 1:
        zotero_similarity = round(zotero_similarity / 10.0, 2)

    # ---- subscriptions (saved searches) ----
    matched_subscriptions: List[str] = []
    saved_searches = run_context.get("saved_searches") or _load_saved_searches()
    if saved_searches:
        matched_subscriptions = _match_subscriptions(paper, saved_searches)

    # ---- feedback signals ----
    feedback_signals: List[str] = []
    feedback_data = run_context.get("feedback") or _load_feedback()
    if feedback_data:
        feedback_signals = _build_feedback_signals(paper, feedback_data)

    # ---- source tags ----
    source_tags = _derive_source_tags(paper)

    # ---- human-readable summary ----
    reason_summary = _build_reason_summary(
        matched_topics=matched_topics,
        matched_secondary=matched_secondary,
        zotero_similarity=zotero_similarity,
        matched_subscriptions=matched_subscriptions,
        feedback_signals=feedback_signals,
        source_tags=source_tags,
    )

    return {
        "reason_summary": reason_summary,
        "matched_topics": matched_topics,
        "matched_subscriptions": matched_subscriptions,
        "zotero_similarity": zotero_similarity,
        "feedback_signals": feedback_signals,
        "source_tags": source_tags,
    }


# ---------------------------------------------------------------------------
# Internal helpers for build_recommendation_reason
# ---------------------------------------------------------------------------


def _safe_breakdown(paper: dict) -> list[dict]:
    """Return the score_details breakdown as a list of dicts, or an empty list."""
    details = _score_details(paper)
    breakdown = details.get("breakdown", [])
    if isinstance(breakdown, list):
        return [item for item in breakdown if isinstance(item, dict)]
    return []


def _extract_topic_from_text(text: str) -> str:
    """Extract the topic name from a breakdown text like '命中核心主题: conformal prediction'."""
    text = str(text or "").strip()
    # Chinese colon patterns
    for prefix in ("命中核心主题: ", "命中核心主题：", "相关主题: ", "相关主题：",
                     "包含理论信号: ", "包含理论信号："):
        if text.startswith(prefix):
            return text[len(prefix):].strip()
    # English patterns
    for prefix in ("Core topic: ", "Secondary topic: "):
        if text.lower().startswith(prefix.lower()):
            return text[len(prefix):].strip()
    # Fallback: try to strip common prefixes
    if ":" in text:
        return text.split(":", 1)[1].strip()
    if "：" in text:
        return text.split("：", 1)[1].strip()
    return text


def _match_keywords_from_profile(paper: dict, user_profile: dict) -> tuple[list[str], list[str]]:
    """Fallback keyword matching when no breakdown is available."""
    title = str(paper.get("title", "") or "").lower()
    abstract = str(paper.get("abstract", "") or "").lower()
    text = title + " " + abstract

    core: list[str] = []
    secondary: list[str] = []

    core_keywords = user_profile.get("core_keywords") or user_profile.get("core_topics") or {}
    if isinstance(core_keywords, dict):
        for kw in core_keywords:
            if _keyword_in_text(kw, text):
                core.append(str(kw))

    secondary_keywords = user_profile.get("secondary_keywords") or user_profile.get("secondary_topics") or {}
    if isinstance(secondary_keywords, dict):
        for kw in secondary_keywords:
            if _keyword_in_text(kw, text):
                secondary.append(str(kw))

    return core, secondary


def _keyword_in_text(keyword: str, text: str) -> bool:
    """Check if keyword appears in text using word-boundary matching."""
    kw = str(keyword).lower().strip()
    if not kw:
        return False
    if " " in kw or "-" in kw:
        return kw in text
    pattern = r"\b" + re.escape(kw) + r"\b"
    return bool(re.search(pattern, text))


def _load_saved_searches() -> list[dict]:
    """Load saved searches from the state store (best-effort)."""
    try:
        from state_store import get_state_store
        return get_state_store().list_saved_searches()
    except Exception:
        return []


def _load_feedback() -> dict:
    """Load user feedback (best-effort)."""
    try:
        from state_store import get_state_store as _gss
        from app.services.feedback_service import FeedbackService
        from app_paths import CACHE_DIR, HISTORY_DIR
        svc = FeedbackService(
            _gss(),
            feedback_file=str(CACHE_DIR / "user_feedback.json"),
            favorites_file=str(CACHE_DIR / "favorite_papers.json"),
            cache_file=str(CACHE_DIR / "paper_cache.json"),
            history_dir=str(HISTORY_DIR),
        )
        return svc.load_feedback()
    except Exception:
        return {}


def _match_subscriptions(paper: dict, saved_searches: list[dict]) -> list[str]:
    """Check which saved searches match the paper."""
    title = str(paper.get("title", "") or "")
    abstract = str(paper.get("abstract", "") or "")
    text = (title + " " + abstract).lower()

    matched: list[str] = []
    for search in saved_searches:
        if not search.get("is_active"):
            continue
        query = str(search.get("query_text", "") or "").strip()
        if not query:
            continue
        # Split query into terms and check if all appear in text
        if "," in query or "，" in query:
            terms = [t.strip() for t in re.split(r"[,，]+", query) if t.strip()]
        else:
            terms = [query]
        if terms and all(_keyword_in_text(term, text) for term in terms):
            name = search.get("name", query)
            matched.append(name)
    return matched


def _build_feedback_signals(paper: dict, feedback: dict) -> list[str]:
    """Check if the user has liked similar papers."""
    signals: list[str] = []
    paper_id = str(paper.get("id", "") or "")
    liked = set(feedback.get("liked") or [])
    disliked = set(feedback.get("disliked") or [])

    if paper_id in liked:
        signals.append("you previously liked this paper")
    if paper_id in disliked:
        signals.append("you previously ignored this paper")

    # Check queue status for deeper engagement signals
    try:
        from state_store import get_state_store
        item = get_state_store().get_queue_item(paper_id)
        if item and item.get("status") == "Deep Read":
            signals.append("you have queued similar papers for Deep Read")
    except Exception:
        pass

    return signals


def _derive_source_tags(paper: dict) -> list[str]:
    """Derive source tags from paper metadata."""
    tags: list[str] = []

    source = str(paper.get("source", "") or "").strip().lower()
    if source:
        tags.append(source)

    # Detect arXiv search
    if paper.get("id", ""):
        tags.append("arxiv_search")

    # Detect if from journal venues
    categories = paper.get("categories") or []
    journal_cats = [c for c in categories if not str(c).startswith(("cs.", "math.", "stat.", "physics", "cond-", "hep-", "quant-"))]
    if journal_cats:
        tags.append("journal_venue")

    # Detect author tracking
    if paper.get("from_author_tracking") or paper.get("from_scholars"):
        tags.append("author_subscription")

    # If no source at all, mark as unknown
    if not tags:
        tags.append("unknown")

    return tags


def _build_reason_summary(
    matched_topics: list[str],
    matched_secondary: list[str],
    zotero_similarity: float,
    matched_subscriptions: list[str],
    feedback_signals: list[str],
    source_tags: list[str],
) -> str:
    """Generate a human-readable one-line summary in natural language."""
    parts: list[str] = []

    if matched_topics:
        parts.append(f"core research topics: {', '.join(matched_topics[:3])}")
    elif matched_secondary:
        parts.append(f"related topics: {', '.join(matched_secondary[:3])}")

    if matched_subscriptions:
        parts.append(f"matches subscription: {', '.join(matched_subscriptions[:2])}")

    if zotero_similarity > 0:
        pct = int(zotero_similarity * 100)
        parts.append(f"{pct}% Zotero library similarity")

    if feedback_signals:
        # Keep it short — just mention the strongest positive signal
        positive = [s for s in feedback_signals if "liked" in s or "Deep Read" in s.lower()]
        if positive:
            parts.append("engagement history matches")

    if not parts:
        parts.append("recommended based on overall relevance score")

    # Prepend source context
    meaningful_sources = [t for t in source_tags if t not in ("arxiv_search", "unknown")]
    prefix = f"via {meaningful_sources[0]}" if meaningful_sources else "from arXiv search"

    return f"This paper was recommended {prefix} because of {'; '.join(parts)}."


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


__all__ = ["EnhancedScorer", "ScoringVariant", "score_papers_for_evaluation", "build_recommendation_reason"]
