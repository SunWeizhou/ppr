"""Recommendation scoring components including the EnhancedScorer."""

from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Dict, Iterable, List, Optional, Tuple

from config_manager import get_config
from logger_config import get_logger

from app.services.arxiv_source import KNOWN_AUTHORS, TOP_INSTITUTIONS
from app.services.settings_service import get_dislike_topics

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# EnhancedScorer (moved from arxiv_recommender_v5)
# ---------------------------------------------------------------------------


class EnhancedScorer:
    """Enhanced paper scorer with smart keyword matching."""

    def __init__(self, semantic: 'SemanticSimilarity' = None, use_semantic: bool = True, topic_weights: Dict[str, float] = None):
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
        self.THEORY_KEYWORDS = cm.theory_keywords
        self.DEMOTE_TOPICS = cm.demote_keywords
        self.DISLIKE_TOPICS = list(cm.dislike_keywords.keys())
        self.THEORY_ENABLED = cm._settings.theory_enabled
        # Keep SYNONYMS as class attribute (not configurable for now)
        if not hasattr(self, 'SYNONYMS'):
            self.SYNONYMS = {
                'bound': ['guarantee', 'limit', 'upper bound', 'lower bound'],
                'convergence': ['converge', 'convergent'],
                'inference': ['estimation', 'inference'],
                'regression': ['regressor', 'regress'],
            }

    def compute_score(self, paper: Dict) -> Tuple[float, Dict]:
        """Compute overall score."""
        relevance = self._compute_relevance(paper)
        author = self._compute_author_influence(paper)
        depth = self._compute_technical_depth(paper)
        semantic_sim = self._compute_semantic_score(paper)

        if self.use_semantic and semantic_sim > 0:
            total = relevance * 0.50 + author * 0.10 + depth * 0.10 + semantic_sim * 0.30
        else:
            total = relevance * 0.70 + author * 0.15 + depth * 0.15

        # Add topic affinity bonus (best-effort)
        affinity_bonus = 0.0
        try:
            affinities = self._load_topic_affinities()
            affinity_bonus = self._apply_topic_affinity_score(paper, affinities)
            total += affinity_bonus
        except Exception:
            affinity_bonus = 0.0

        details = {
            'relevance': relevance,
            'author': author,
            'depth': depth,
            'semantic': semantic_sim,
            'affinity': round(affinity_bonus, 2),
            'breakdown': self._get_breakdown(paper, semantic_sim)
        }

        return total, details

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
        matched_topics: List[str] = []

        for topic, weight in self.CORE_TOPICS.items():
            title_count = self._count_keyword(title, topic)
            abstract_count = self._count_keyword(abstract, topic)

            if title_count > 0 or abstract_count > 0:
                topic_score = weight * (min(title_count, 3) * 3.0 + min(abstract_count, 3) * 1.0) / 4.0
                score += topic_score
                matched_topics.append(topic)

        for topic, weight in self.SECONDARY_TOPICS.items():
            title_count = self._count_keyword(title, topic)
            abstract_count = self._count_keyword(abstract, topic)

            if title_count > 0 or abstract_count > 0:
                topic_score = weight * (min(title_count, 2) * 2.0 + min(abstract_count, 2) * 1.0) / 3.0
                score += topic_score

        for base_word, synonyms in self.SYNONYMS.items():
            for syn in synonyms:
                if self._count_keyword(title, syn) > 0:
                    score += 0.5

        for topic, penalty in self.DEMOTE_TOPICS.items():
            if self._count_keyword(title + ' ' + abstract, topic) > 0:
                if matched_topics:
                    score += penalty * 0.3
                else:
                    score += penalty

        for topic, weight in self.topic_weights.items():
            if topic.lower() not in self.CORE_TOPICS and topic.lower() not in self.SECONDARY_TOPICS:
                if self._count_keyword(title, topic) > 0:
                    score += weight * 0.5

        if self.THEORY_ENABLED:
            for kw in self.THEORY_KEYWORDS:
                if self._count_keyword(title + ' ' + abstract, kw) > 0:
                    score += 0.4

        for topic in get_dislike_topics():
            if self._count_keyword(title + ' ' + abstract, topic) > 0:
                if not matched_topics:
                    score -= 1.0

        if paper.get('_topic_match'):
            score += 2.0

        return min(max(score, 0), 10)

    def _compute_author_influence(self, paper: Dict) -> float:
        """Compute author influence."""
        score = 0.0
        authors_text = ' '.join(paper.get('authors', [])).lower()
        all_text = (paper.get('abstract', '') + ' ' + (paper.get('comment') or '')).lower()

        for inst in TOP_INSTITUTIONS:
            pattern = r'\b' + re.escape(inst.lower()) + r'\b'
            if re.search(pattern, all_text):
                score += 1.5
                break

        for author in KNOWN_AUTHORS:
            if author.lower() in authors_text:
                score += 2.0
                break

        venues = ['neurips', 'icml', 'iclr', 'colt', 'jmlr', 'aistats']
        for venue in venues:
            if venue in all_text:
                score += 1.5
                break

        try:
            from state_store import get_state_store
            store = get_state_store()
            author_subs = store.list_subscriptions(type="author")
            for sub in author_subs:
                author_name = (sub.get("query_text") or sub.get("name", "")).lower()
                if not author_name:
                    continue
                if author_name in authors_text or any(
                    part in authors_text for part in author_name.split() if len(part) > 2
                ):
                    score += 3.0
                    break
        except Exception as e:
            logger.debug(f"Error checking author subscriptions: {e}")

        return min(score, 5)

    @staticmethod
    def _compute_technical_depth(paper: Dict) -> float:
        """Compute technical depth."""
        text = (paper['title'] + ' ' + paper.get('abstract', '')).lower()
        score = 0.0

        indicators = [
            ('theorem', 1.0), ('proof', 1.0), ('bound', 0.8),
            ('convergence', 0.8), ('minimax', 1.0), ('asymptotic', 0.7),
            ('rademacher', 1.0), ('pac-bayes', 1.0), ('excess risk', 1.2),
            ('sample complexity', 1.0), ('statistical guarantee', 1.0)
        ]

        for indicator, weight in indicators:
            if indicator in text:
                score += weight

        if 'math.ST' in paper.get('categories', []):
            score += 1.5

        return min(score, 5)

    def _compute_semantic_score(self, paper: Dict) -> float:
        """Compute semantic similarity score (0-10 scale)."""
        if self.use_semantic and self.semantic is not None:
            sim = self.semantic.compute_similarity(paper)
            return sim * 10
        return 0.0

    def _load_topic_affinities(self) -> list:
        """Load user topic affinities from the state store (best-effort)."""
        try:
            from state_store import get_state_store
            return get_state_store().get_user_topic_affinities()
        except Exception:
            return []

    def _apply_topic_affinity_score(self, paper: dict, affinities: list) -> float:
        """Return a bonus score based on how well paper categories match user topic affinities.

        For each paper category, look up in affinities. Boost score proportionally
        to positive_score / negative_score ratio. Returns float bonus (0.0 to 2.0).
        """
        if not affinities:
            return 0.0

        categories = paper.get("categories", [])
        if not categories:
            return 0.0

        try:
            from utils import CATEGORY_NAMES
        except Exception:
            CATEGORY_NAMES = {}

        affinity_map = {a["topic"].lower(): a for a in affinities}
        bonus = 0.0

        for cat in categories:
            topic_name = CATEGORY_NAMES.get(cat, cat).lower()
            affinity = affinity_map.get(topic_name)
            if affinity:
                pos = affinity["positive_score"]
                neg = affinity["negative_score"]
                net = pos - neg
                if net > 0:
                    bonus += min(net / 5.0, 1.0)

        return min(bonus, 2.0)

    def _get_breakdown(self, paper: Dict, semantic_sim: float) -> List[Dict]:
        """Get structured breakdown with icons and score impacts."""
        reasons: List[Dict] = []
        title = paper.get('title', '')
        abstract = paper.get('abstract', '')
        title_lower = title.lower()
        abstract_lower = abstract.lower()

        for topic, weight in self.CORE_TOPICS.items():
            title_count = self._count_keyword(title_lower, topic)
            abstract_count = self._count_keyword(abstract_lower, topic)
            if title_count > 0:
                reasons.append({
                    'type': 'core_topic',
                    'icon': '\U0001f3af',
                    'text': f"命中核心主题: {topic}",
                    'location': '标题',
                    'score_impact': weight * 0.8
                })
                break
            elif abstract_count > 0:
                reasons.append({
                    'type': 'core_topic',
                    'icon': '\U0001f3af',
                    'text': f"命中核心主题: {topic}",
                    'location': '摘要',
                    'score_impact': weight * 0.3
                })
                break

        if not any(r['type'] == 'core_topic' for r in reasons):
            for topic, weight in self.SECONDARY_TOPICS.items():
                if self._count_keyword(title_lower + ' ' + abstract_lower, topic) > 0:
                    reasons.append({
                        'type': 'secondary_topic',
                        'icon': '\U0001f4cc',
                        'text': f"相关主题: {topic}",
                        'location': '',
                        'score_impact': weight * 0.2
                    })
                    break

        if semantic_sim > 0.5:
            reasons.append({
                'type': 'semantic',
                'icon': '\U0001f517',
                'text': f"与您的 Zotero 库语义相近 ({semantic_sim:.1%})",
                'location': '',
                'score_impact': semantic_sim * 0.3
            })

        authors_text = ' '.join(paper.get('authors', [])).lower()
        for author in KNOWN_AUTHORS:
            if author.lower() in authors_text:
                reasons.append({
                    'type': 'author',
                    'icon': '\U0001f464',
                    'text': f"知名作者: {author}",
                    'location': '',
                    'score_impact': 2.0
                })
                break

        all_text = title_lower + ' ' + abstract_lower + ' ' + (paper.get('comment') or '').lower()
        for inst in TOP_INSTITUTIONS:
            pattern = r'\b' + re.escape(inst.lower()) + r'\b'
            if re.search(pattern, all_text):
                reasons.append({
                    'type': 'institution',
                    'icon': '\U0001f3db️',
                    'text': f"来自 {inst}",
                    'location': '',
                    'score_impact': 1.5
                })
                break

        published = paper.get('published', '')
        if published:
            try:
                pub_date = datetime.strptime(published[:10], '%Y-%m-%d')
                days_old = (datetime.now() - pub_date).days
                if days_old <= 7:
                    reasons.append({
                        'type': 'recency',
                        'icon': '\U0001f195',
                        'text': f"近{days_old}天新论文",
                        'location': '',
                        'score_impact': 0.3
                    })
            except Exception:
                pass

        if self.THEORY_ENABLED:
            theory_matches = [
                kw for kw in self.THEORY_KEYWORDS
                if self._count_keyword(title_lower + ' ' + abstract_lower, kw) > 0
            ]
            if theory_matches:
                reasons.append({
                    'type': 'theory',
                    'icon': '\U0001f4d0',
                    'text': f"包含理论信号: {', '.join(theory_matches[:2])}",
                    'location': '',
                    'score_impact': 0.5
                })

        return reasons[:4]

    def _get_breakdown_text(self, paper: Dict, semantic_sim: float) -> str:
        """Get text-only breakdown for backwards compatibility."""
        reasons = self._get_breakdown(paper, semantic_sim)
        return '; '.join([r['text'] for r in reasons]) if reasons else '匹配您的研究兴趣'


# ---------------------------------------------------------------------------
# Existing scoring components below
# ---------------------------------------------------------------------------


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

    # ---- topic affinity reason ----
    affinity_reason = _build_affinity_reason(paper)

    return {
        "reason_summary": reason_summary,
        "matched_topics": matched_topics,
        "matched_subscriptions": matched_subscriptions,
        "zotero_similarity": zotero_similarity,
        "feedback_signals": feedback_signals,
        "source_tags": source_tags,
        "affinity_reason": affinity_reason,
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


def _build_affinity_reason(paper: dict) -> str:
    """Build a human-readable reason for topic affinity boosts, or empty string."""
    categories = paper.get("categories", [])
    if not categories:
        return ""

    try:
        from state_store import get_state_store
        affinities = get_state_store().get_user_topic_affinities()
    except Exception:
        return ""

    if not affinities:
        return ""

    try:
        from utils import CATEGORY_NAMES
    except Exception:
        CATEGORY_NAMES = {}

    affinity_map = {a["topic"].lower(): a for a in affinities}
    boosted: list[str] = []

    for cat in categories:
        topic_name = CATEGORY_NAMES.get(cat, cat).lower()
        affinity = affinity_map.get(topic_name)
        if affinity:
            pos = affinity.get("positive_score", 0) or 0
            neg = affinity.get("negative_score", 0) or 0
            net = pos - neg
            if net > 0:
                bonus = min(net / 5.0, 1.0)
                boosted.append(f"{CATEGORY_NAMES.get(cat, cat)} (+{bonus:.1f})")

    if boosted:
        return "Your topic preferences boosted the score for: " + ", ".join(boosted)
    return ""


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
