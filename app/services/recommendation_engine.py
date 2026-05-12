"""Multi-strategy recommendation engine with multi-dimensional scoring."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Candidate dataclass — unified output from all strategies
# ---------------------------------------------------------------------------


@dataclass
class Candidate:
    """A single recommendation candidate produced by a strategy."""

    paper_id: str
    score: float
    source_strategy: str
    reason: str
    score_breakdown: dict = field(default_factory=dict)
    paper_data: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------


def normalize_citation_score(citation_count: int | float) -> float:
    """Normalize citation count to 0-1 using log scaling.

    Uses log(1 + count) / log(1 + cap) where cap = 5000.
    Papers with 5000+ citations score ~1.0.
    """
    count = max(0, int(citation_count or 0))
    cap = 5000
    if count == 0:
        return 0.0
    return min(math.log(1 + count) / math.log(1 + cap), 1.0)


def normalize_freshness_score(days_old: int | float) -> float:
    """Normalize publication recency to 0-1 using exponential decay.

    Half-life = 90 days. A paper published today scores ~1.0,
    at 90 days ~0.5, at 365 days ~0.06.
    """
    days = max(0, float(days_old or 0))
    half_life = 90.0
    return math.exp(-0.693 * days / half_life)


# ---------------------------------------------------------------------------
# RecommendationScorer — multi-dimensional weighted scoring
# ---------------------------------------------------------------------------


_DEFAULT_WEIGHTS = {
    "relevance": 0.35,
    "citation": 0.20,
    "freshness": 0.15,
    "entity_affinity": 0.15,
    "feedback": 0.15,
}


class RecommendationScorer:
    """Compute a composite recommendation score from 5 normalized dimensions.

    Each dimension is expected in [0, 1]. Values outside this range are clamped.
    The composite score is a weighted sum using the configured weights.
    """

    def __init__(self, weights: dict[str, float] | None = None):
        self.weights = dict(weights or _DEFAULT_WEIGHTS)

    def score(
        self,
        *,
        relevance: float = 0.0,
        citation: float = 0.0,
        freshness: float = 0.0,
        entity_affinity: float = 0.0,
        feedback: float = 0.0,
    ) -> dict:
        """Return composite score and per-dimension breakdown.

        Returns:
            dict with keys:
                composite: float in [0, 1]
                breakdown: dict mapping dimension name to {raw, weight, weighted}
        """
        dims = {
            "relevance": relevance,
            "citation": citation,
            "freshness": freshness,
            "entity_affinity": entity_affinity,
            "feedback": feedback,
        }
        breakdown = {}
        composite = 0.0
        for name, raw in dims.items():
            clamped = max(0.0, min(float(raw), 1.0))
            w = self.weights.get(name, 0.0)
            weighted = clamped * w
            composite += weighted
            breakdown[name] = {
                "raw": round(clamped, 4),
                "weight": w,
                "weighted": round(weighted, 4),
            }
        composite = max(0.0, min(composite, 1.0))
        return {"composite": round(composite, 6), "breakdown": breakdown}

import abc
from datetime import datetime


# ---------------------------------------------------------------------------
# BaseStrategy — abstract base for all recommendation strategies
# ---------------------------------------------------------------------------


class BaseStrategy(abc.ABC):
    """Abstract base class for recommendation strategies."""

    name: str = "base"

    @abc.abstractmethod
    def generate(self, **kwargs: Any) -> list[Candidate]:
        """Generate recommendation candidates.

        Each strategy defines its own kwargs. Common ones:
            papers: list[dict] — candidate paper pool
            user_profile: dict — user_profile row
            state_store: StateStore — for DB queries
        """
        ...


# ---------------------------------------------------------------------------
# ForYouStrategy — profile-based keyword/interest matching
# ---------------------------------------------------------------------------


class ForYouStrategy(BaseStrategy):
    """Recommend papers matching the user's interest vector and topic weights."""

    name = "for_you"

    def generate(self, **kwargs: Any) -> list[Candidate]:
        papers: list[dict] = kwargs.get("papers", [])
        profile: dict = kwargs.get("user_profile", {})
        interests = profile.get("interest_vector", [])
        topic_weights: dict = profile.get("topic_weights", {})

        candidates = []
        for paper in papers:
            title_lower = (paper.get("title") or "").lower()
            abstract_lower = (paper.get("abstract") or "").lower()
            text = title_lower + " " + abstract_lower

            matched = []
            relevance = 0.0
            for interest in interests:
                kw = interest.lower()
                if kw in text:
                    weight = float(topic_weights.get(interest, 1.0))
                    title_hit = 3.0 if kw in title_lower else 0.0
                    abstract_hit = 1.0 if kw in abstract_lower else 0.0
                    relevance += weight * (title_hit + abstract_hit) / 4.0
                    matched.append(interest)

            # Normalize relevance to 0-1 via saturation at 3.0
            relevance_norm = min(relevance / 3.0, 1.0) if relevance > 0 else 0.1

            reason = f"Matches your interests: {', '.join(matched[:3])}" if matched else "Recommended for your research area"
            candidates.append(Candidate(
                paper_id=paper.get("paper_id") or paper.get("id", ""),
                score=relevance_norm,
                source_strategy=self.name,
                reason=reason,
                score_breakdown={"relevance": round(relevance_norm, 4)},
                paper_data=paper,
            ))
        candidates.sort(key=lambda c: c.score, reverse=True)
        return candidates


# ---------------------------------------------------------------------------
# TrendingStrategy — citation velocity + freshness
# ---------------------------------------------------------------------------


def _days_since_publication(paper: dict) -> int:
    """Estimate days since publication from year field."""
    year_str = str(paper.get("year") or paper.get("published_at") or "")[:4]
    if not year_str.isdigit():
        return 365  # Unknown age defaults to 1 year
    pub_year = int(year_str)
    now = datetime.now()
    # Approximate: assume mid-year publication
    days = (now.year - pub_year) * 365 + (now.month - 6) * 30
    return max(0, days)


class TrendingStrategy(BaseStrategy):
    """Recommend papers with high citation velocity relative to their age."""

    name = "trending"

    def generate(self, **kwargs: Any) -> list[Candidate]:
        papers: list[dict] = kwargs.get("papers", [])
        candidates = []
        for paper in papers:
            citation_count = int(paper.get("citation_count") or 0)
            days_old = _days_since_publication(paper)

            cit_score = normalize_citation_score(citation_count)
            fresh_score = normalize_freshness_score(days_old)

            # Trending = citation strength * freshness boost
            trending_score = 0.6 * cit_score + 0.4 * fresh_score

            if citation_count > 0:
                reason = f"Trending: {citation_count} citations"
            else:
                reason = "Recently published"

            candidates.append(Candidate(
                paper_id=paper.get("paper_id") or paper.get("id", ""),
                score=trending_score,
                source_strategy=self.name,
                reason=reason,
                score_breakdown={
                    "citation": round(cit_score, 4),
                    "freshness": round(fresh_score, 4),
                },
                paper_data=paper,
            ))
        candidates.sort(key=lambda c: c.score, reverse=True)
        return candidates

# ---------------------------------------------------------------------------
# EntityStrategy — aggregated from subscribed entities
# ---------------------------------------------------------------------------


class EntityStrategy(BaseStrategy):
    """Recommend papers that match subscribed entities (venues, authors, fields)."""

    name = "entity"

    def generate(self, **kwargs: Any) -> list[Candidate]:
        papers: list[dict] = kwargs.get("papers", [])
        subscriptions: list[dict] = kwargs.get("subscriptions", [])

        # Build lookup sets from subscriptions
        venue_names: list[str] = []
        author_names: list[str] = []
        field_keywords: list[str] = []
        for sub in subscriptions:
            sub_type = sub.get("type", "")
            query = (sub.get("query_text") or sub.get("name") or "").lower().strip()
            if not query:
                continue
            if sub_type in ("venue", "journal", "conference"):
                venue_names.append(query)
            elif sub_type in ("author", "scholar"):
                author_names.append(query)
            elif sub_type in ("field", "query"):
                field_keywords.append(query)

        candidates = []
        for paper in papers:
            venue = (paper.get("venue") or "").lower()
            authors_text = " ".join(paper.get("authors") or []).lower()
            title_abs = ((paper.get("title") or "") + " " + (paper.get("abstract") or "")).lower()

            affinity = 0.0
            matched_entities: list[str] = []

            for v in venue_names:
                if v in venue:
                    affinity += 0.4
                    matched_entities.append(v.title())
            for a in author_names:
                if a in authors_text:
                    affinity += 0.4
                    matched_entities.append(a.title())
            for f in field_keywords:
                if f in title_abs:
                    affinity += 0.2
                    matched_entities.append(f.title())

            affinity = min(affinity, 1.0)
            reason = f"From your subscriptions: {', '.join(matched_entities[:3])}" if matched_entities else "No subscription match"

            candidates.append(Candidate(
                paper_id=paper.get("paper_id") or paper.get("id", ""),
                score=affinity,
                source_strategy=self.name,
                reason=reason,
                score_breakdown={"entity_affinity": round(affinity, 4)},
                paper_data=paper,
            ))
        candidates.sort(key=lambda c: c.score, reverse=True)
        return candidates


# ---------------------------------------------------------------------------
# ReadingStrategy — similar to papers in reading queue
# ---------------------------------------------------------------------------


def _keyword_overlap(text_a: str, text_b: str, min_word_len: int = 4) -> float:
    """Compute Jaccard-like keyword overlap between two texts.

    Filters to words of length >= min_word_len to ignore stopwords.
    Returns value in [0, 1].
    """
    words_a = {w for w in text_a.lower().split() if len(w) >= min_word_len}
    words_b = {w for w in text_b.lower().split() if len(w) >= min_word_len}
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)


class ReadingStrategy(BaseStrategy):
    """Recommend papers similar to those in the user's reading queue."""

    name = "reading"

    def generate(self, **kwargs: Any) -> list[Candidate]:
        papers: list[dict] = kwargs.get("papers", [])
        reading_queue: list[dict] = kwargs.get("reading_queue", [])

        # Build combined text from reading queue for keyword overlap
        queue_texts = []
        for q_paper in reading_queue:
            text = (q_paper.get("title") or "") + " " + (q_paper.get("abstract") or "")
            queue_texts.append(text)
        combined_queue = " ".join(queue_texts)

        candidates = []
        for paper in papers:
            paper_text = (paper.get("title") or "") + " " + (paper.get("abstract") or "")

            if not reading_queue:
                similarity = 0.0
                reason = "Add papers to your reading queue for tailored recommendations"
            else:
                # Compute overlap against each queue paper, take max
                overlaps = [_keyword_overlap(paper_text, qt) for qt in queue_texts]
                similarity = max(overlaps) if overlaps else 0.0
                # Normalize: overlap of 0.15+ is strong
                similarity = min(similarity / 0.15, 1.0)
                if similarity > 0.3:
                    reason = "Similar to papers in your reading queue"
                else:
                    reason = "Loosely related to your reading list"

            candidates.append(Candidate(
                paper_id=paper.get("paper_id") or paper.get("id", ""),
                score=similarity,
                source_strategy=self.name,
                reason=reason,
                score_breakdown={"relevance": round(similarity, 4)},
                paper_data=paper,
            ))
        candidates.sort(key=lambda c: c.score, reverse=True)
        return candidates


# ---------------------------------------------------------------------------
# QuestionStrategy — research question targeted
# ---------------------------------------------------------------------------


class QuestionStrategy(BaseStrategy):
    """Recommend papers matching active research questions."""

    name = "question"

    def generate(self, **kwargs: Any) -> list[Candidate]:
        papers: list[dict] = kwargs.get("papers", [])
        questions: list[dict] = kwargs.get("research_questions", [])

        question_texts = []
        for q in questions:
            qt = (q.get("query_text") or "").lower()
            if qt:
                question_texts.append(qt)

        candidates = []
        for paper in papers:
            paper_text = ((paper.get("title") or "") + " " + (paper.get("abstract") or "")).lower()

            if not question_texts:
                relevance = 0.0
                reason = "Add research questions for targeted recommendations"
            else:
                overlaps = [_keyword_overlap(paper_text, qt) for qt in question_texts]
                relevance = max(overlaps) if overlaps else 0.0
                relevance = min(relevance / 0.10, 1.0)  # Normalize: 0.10 overlap is strong for questions

                if relevance > 0.3:
                    # Find best matching question
                    best_idx = overlaps.index(max(overlaps))
                    reason = f"Relevant to: {questions[best_idx].get('query_text', '')[:60]}"
                else:
                    reason = "Loosely related to your research questions"

            candidates.append(Candidate(
                paper_id=paper.get("paper_id") or paper.get("id", ""),
                score=relevance,
                source_strategy=self.name,
                reason=reason,
                score_breakdown={"relevance": round(relevance, 4)},
                paper_data=paper,
            ))
        candidates.sort(key=lambda c: c.score, reverse=True)
        return candidates

from logger_config import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Section display titles
# ---------------------------------------------------------------------------

_SECTION_TITLES: dict[str, str] = {
    "for_you": "For You",
    "entity": "From Your Subscriptions",
    "trending": "Trending",
    "reading": "Based on Your Reading",
    "question": "Research Questions",
}


# ---------------------------------------------------------------------------
# RecommendationEngine — orchestrates strategies and scoring
# ---------------------------------------------------------------------------


class RecommendationEngine:
    """Orchestrate multiple strategies and produce sectioned recommendations."""

    def __init__(self, strategies: list[BaseStrategy] | None = None):
        if strategies is not None:
            self._strategies = strategies
        else:
            self._strategies = [
                ForYouStrategy(),
                EntityStrategy(),
                TrendingStrategy(),
                ReadingStrategy(),
                QuestionStrategy(),
            ]
        self._scorer = RecommendationScorer()

    def recommend(
        self,
        *,
        papers: list[dict],
        user_profile: dict | None = None,
        subscriptions: list[dict] | None = None,
        reading_queue: list[dict] | None = None,
        research_questions: list[dict] | None = None,
        max_per_section: int = 15,
    ) -> dict:
        """Run all strategies and return sectioned results.

        Returns:
            dict with keys:
                sections: list[dict] each with {strategy, title, candidates}
                all_candidates: list[Candidate] — flattened and deduplicated
        """
        user_profile = user_profile or {}
        subscriptions = subscriptions or []
        reading_queue = reading_queue or []
        research_questions = research_questions or []

        kwargs = {
            "papers": papers,
            "user_profile": user_profile,
            "subscriptions": subscriptions,
            "reading_queue": reading_queue,
            "research_questions": research_questions,
        }

        sections: list[dict] = []
        all_candidates: list[Candidate] = []

        for strategy in self._strategies:
            try:
                candidates = strategy.generate(**kwargs)
                # Take top N per section
                top = candidates[:max_per_section]
                if top:
                    sections.append({
                        "strategy": strategy.name,
                        "title": _SECTION_TITLES.get(strategy.name, strategy.name.replace("_", " ").title()),
                        "candidates": top,
                    })
                    all_candidates.extend(top)
            except Exception as exc:
                logger.warning("Strategy %s failed: %s", strategy.name, exc)

        return {
            "sections": sections,
            "all_candidates": all_candidates,
        }

# ------------------------------------------------------------------
    # User Profile
    # ------------------------------------------------------------------

    def get_user_profile(self) -> Dict:
        """Get the singleton user profile, creating it if it doesn't exist."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM user_profile WHERE id = 1"
            ).fetchone()
        if not row:
            # Create default profile
            self.upsert_user_profile()
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT * FROM user_profile WHERE id = 1"
                ).fetchone()
        profile = self._row_to_dict(row) if row else {}
        # Parse JSON fields
        for key in ("interest_vector", "topic_weights", "entity_affinities", "reading_pace"):
            raw = profile.get(key, "")
            if isinstance(raw, str):
                try:
                    profile[key] = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    profile[key] = [] if key == "interest_vector" else {}
        return profile

    def upsert_user_profile(
        self,
        interest_vector: Optional[List[str]] = None,
        topic_weights: Optional[Dict] = None,
        entity_affinities: Optional[Dict] = None,
        reading_pace: Optional[Dict] = None,
    ) -> None:
        """Create or update the singleton user profile.

        Only provided fields are updated; None fields are left unchanged.
        """
        now = _utc_now()
        with self._lock, self._connect() as conn:
            existing = conn.execute(
                "SELECT * FROM user_profile WHERE id = 1"
            ).fetchone()

            if existing:
                existing = self._row_to_dict(existing)
                updates = {}
                if interest_vector is not None:
                    updates["interest_vector"] = json.dumps(interest_vector, ensure_ascii=False)
                if topic_weights is not None:
                    updates["topic_weights"] = json.dumps(topic_weights, ensure_ascii=False)
                if entity_affinities is not None:
                    updates["entity_affinities"] = json.dumps(entity_affinities, ensure_ascii=False)
                if reading_pace is not None:
                    updates["reading_pace"] = json.dumps(reading_pace, ensure_ascii=False)
                if updates:
                    updates["updated_at"] = now
                    set_clause = ", ".join(f"{k} = ?" for k in updates)
                    conn.execute(
                        f"UPDATE user_profile SET {set_clause} WHERE id = 1",
                        list(updates.values()),
                    )
            else:
                conn.execute(
                    """INSERT INTO user_profile(id, interest_vector, topic_weights, entity_affinities, reading_pace, updated_at)
                       VALUES (1, ?, ?, ?, ?, ?)""",
                    (
                        json.dumps(interest_vector or [], ensure_ascii=False),
                        json.dumps(topic_weights or {}, ensure_ascii=False),
                        json.dumps(entity_affinities or {}, ensure_ascii=False),
                        json.dumps(reading_pace or {}, ensure_ascii=False),
                        now,
                    ),
                )

    def update_profile_from_behavior(self) -> None:
        """Auto-update user profile from reading behavior, subscriptions, and search history.

        Extracts interest signals from:
        - Reading queue items (paper categories and topics)
        - Interaction events (liked papers)
        - Subscriptions (query texts)
        """
        # 1. Collect topics from reading queue papers
        queue_items = self.list_queue_items()
        topic_counts: Dict[str, float] = {}

        for item in queue_items:
            paper_id = item.get("paper_id", "")
            meta = self.get_paper_metadata(paper_id) or {}
            categories = meta.get("categories", [])
            if isinstance(categories, str):
                try:
                    categories = json.loads(categories)
                except (json.JSONDecodeError, TypeError):
                    categories = []

            # Weight by reading depth
            weight = 2.0 if item.get("status") == "Deep Read" else 1.0
            for cat in categories:
                topic_counts[cat] = topic_counts.get(cat, 0) + weight

            # Extract title keywords (simple approach)
            title = meta.get("title") or item.get("title") or ""
            for word in title.lower().split():
                if len(word) >= 5:  # Skip short words
                    topic_counts[word] = topic_counts.get(word, 0) + weight * 0.3

        # 2. Add subscription query texts
        try:
            subs = self.list_subscriptions()
            for sub in subs:
                query = sub.get("query_text", "")
                if query:
                    for word in query.lower().split():
                        if len(word) >= 4:
                            topic_counts[word] = topic_counts.get(word, 0) + 1.5
        except Exception:
            pass

        # 3. Build interest vector from top topics
        sorted_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)
        interest_vector = [t[0] for t in sorted_topics[:30]]
        topic_weights = {t[0]: round(t[1], 2) for t in sorted_topics[:30]}

        self.upsert_user_profile(
            interest_vector=interest_vector,
            topic_weights=topic_weights,
        )

def build_display_reason(
    *,
    source_strategy: str,
    reason: str,
    score_breakdown: dict,
) -> str:
    """Build a one-line human-readable recommendation reason.

    Combines the strategy-specific reason with the dominant scoring dimension
    to produce a concise, informative string (max ~120 chars).

    Args:
        source_strategy: Name of the strategy that produced this candidate.
        reason: Raw reason string from the strategy.
        score_breakdown: Dict mapping dimension names to 0-1 scores.

    Returns:
        A single-line human-readable reason string.
    """
    # Start with the strategy reason, truncated if needed
    base = reason[:80] if len(reason) > 80 else reason

    # Find the top non-relevance dimension to add context
    extras = []
    if score_breakdown.get("citation", 0) > 0.5:
        extras.append("highly cited")
    if score_breakdown.get("freshness", 0) > 0.8:
        extras.append("recently published")
    if score_breakdown.get("entity_affinity", 0) > 0.3:
        extras.append("from subscribed source")
    if score_breakdown.get("feedback", 0) > 0.5:
        extras.append("matches your taste")

    if extras:
        suffix = " (" + ", ".join(extras[:2]) + ")"
        if len(base) + len(suffix) <= 120:
            return base + suffix
    return base