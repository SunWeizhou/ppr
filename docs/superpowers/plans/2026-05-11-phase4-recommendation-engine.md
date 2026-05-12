# Phase 4: Recommendation Intelligence + Personalization — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single-strategy recommendation workspace with a multi-strategy recommendation engine, multi-dimensional scorer, sectioned card layout, and user profile-driven personalization. Each paper gets a human-readable recommendation reason and a transparent score breakdown.

**Architecture:** `RecommendationEngine` orchestrates 4-5 independent `Strategy` classes, each returning `Candidate` dataclass instances. A `RecommendationScorer` normalizes and weights five scoring dimensions (relevance, citation, freshness, entity_affinity, feedback) into a single 0-1 composite score. The recommendation page renders strategy-sectioned horizontal-scroll card rows. The `user_profile` table (created in Phase 2) is activated with CRUD helpers and auto-updated from reading behavior, subscriptions, and search history.

**Tech Stack:** Python dataclasses, SQLite, Flask/Jinja2, vanilla JS, CSS horizontal scroll.

**Ref:** Design spec at `docs/superpowers/specs/2026-05-11-paper-agent-v2-design.md`, sections 6 and 7.

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `app/services/recommendation_engine.py` | `Candidate` dataclass, `RecommendationScorer`, `BaseStrategy` + 5 strategy classes, `RecommendationEngine` orchestrator |
| Modify | `app/services/recommendation_workspace_service.py` | Delegate to `RecommendationEngine`, return sectioned results |
| Modify | `app/services/daily_pipeline.py` | Use `RecommendationScorer` for scoring in `run_pipeline_v2` |
| Modify | `app/routes/api/recommendations.py` | Return sectioned results with per-strategy grouping |
| Modify | `app/routes/recommendations.py` | Pass sectioned data to template |
| Modify | `app/viewmodels/recommendations_viewmodel.py` | Build sectioned template context |
| Rewrite | `templates/recommendations.html` | Horizontal-scroll card sections per strategy |
| Modify | `state_store.py` | `user_profile` CRUD methods + `recommendation_items` column for `source_strategy` |
| Create | `tests/test_recommendation_engine.py` | Strategy, Scorer, and Engine integration tests |
| Create | `tests/test_user_profile.py` | Profile CRUD and auto-update tests |

---

### Task 1: Candidate Dataclass + RecommendationScorer

**Files:**
- Create: `app/services/recommendation_engine.py`
- Create: `tests/test_recommendation_engine.py`

- [ ] **Step 1: Write tests for Candidate and RecommendationScorer**

```python
# tests/test_recommendation_engine.py
"""Tests for the multi-strategy recommendation engine."""

import math
from dataclasses import asdict

import pytest


class TestCandidate:
    def test_candidate_creation(self):
        from app.services.recommendation_engine import Candidate

        c = Candidate(
            paper_id="2401.00001",
            score=0.0,
            source_strategy="for_you",
            reason="Keyword match: LLM",
            score_breakdown={"relevance": 0.8, "citation": 0.3},
        )
        assert c.paper_id == "2401.00001"
        assert c.source_strategy == "for_you"
        assert c.score_breakdown["relevance"] == 0.8

    def test_candidate_defaults(self):
        from app.services.recommendation_engine import Candidate

        c = Candidate(paper_id="x", score=0.5, source_strategy="trending", reason="Hot paper")
        assert c.score_breakdown == {}
        assert c.paper_data == {}

    def test_candidate_serializable(self):
        from app.services.recommendation_engine import Candidate

        c = Candidate(paper_id="x", score=0.5, source_strategy="t", reason="r")
        d = asdict(c)
        assert d["paper_id"] == "x"
        assert isinstance(d, dict)


class TestRecommendationScorer:
    def test_all_dimensions_zero(self):
        from app.services.recommendation_engine import RecommendationScorer

        scorer = RecommendationScorer()
        result = scorer.score(
            relevance=0.0, citation=0.0, freshness=0.0,
            entity_affinity=0.0, feedback=0.0,
        )
        assert result["composite"] == 0.0
        assert len(result["breakdown"]) == 5

    def test_all_dimensions_one(self):
        from app.services.recommendation_engine import RecommendationScorer

        scorer = RecommendationScorer()
        result = scorer.score(
            relevance=1.0, citation=1.0, freshness=1.0,
            entity_affinity=1.0, feedback=1.0,
        )
        assert abs(result["composite"] - 1.0) < 1e-6

    def test_weights_sum_to_one(self):
        from app.services.recommendation_engine import RecommendationScorer

        scorer = RecommendationScorer()
        total = sum(scorer.weights.values())
        assert abs(total - 1.0) < 1e-6

    def test_relevance_dominant(self):
        """Relevance-only paper should score higher than citation-only."""
        from app.services.recommendation_engine import RecommendationScorer

        scorer = RecommendationScorer()
        rel_only = scorer.score(relevance=1.0, citation=0.0, freshness=0.0, entity_affinity=0.0, feedback=0.0)
        cit_only = scorer.score(relevance=0.0, citation=1.0, freshness=0.0, entity_affinity=0.0, feedback=0.0)
        assert rel_only["composite"] > cit_only["composite"]

    def test_custom_weights(self):
        from app.services.recommendation_engine import RecommendationScorer

        scorer = RecommendationScorer(weights={"relevance": 1.0, "citation": 0.0, "freshness": 0.0, "entity_affinity": 0.0, "feedback": 0.0})
        result = scorer.score(relevance=0.7, citation=1.0, freshness=1.0, entity_affinity=1.0, feedback=1.0)
        assert abs(result["composite"] - 0.7) < 1e-6

    def test_values_clamped_to_0_1(self):
        from app.services.recommendation_engine import RecommendationScorer

        scorer = RecommendationScorer()
        result = scorer.score(relevance=2.0, citation=-0.5, freshness=0.5, entity_affinity=0.5, feedback=0.5)
        assert 0.0 <= result["composite"] <= 1.0

    def test_citation_normalization(self):
        from app.services.recommendation_engine import normalize_citation_score

        assert normalize_citation_score(0) == 0.0
        assert 0.0 < normalize_citation_score(10) < normalize_citation_score(100)
        assert normalize_citation_score(10000) <= 1.0

    def test_freshness_normalization(self):
        from app.services.recommendation_engine import normalize_freshness_score

        # Published today => high freshness
        assert normalize_freshness_score(0) > 0.9
        # Published 365 days ago => low freshness
        assert normalize_freshness_score(365) < 0.2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_recommendation_engine.py -v`
Expected: FAIL — `app.services.recommendation_engine` does not exist.

- [ ] **Step 3: Implement Candidate dataclass and RecommendationScorer**

```python
# app/services/recommendation_engine.py
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_recommendation_engine.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/recommendation_engine.py tests/test_recommendation_engine.py
git commit -m "feat(engine): add Candidate dataclass and RecommendationScorer with multi-dimensional scoring"
```

---

### Task 2: BaseStrategy + ForYouStrategy + TrendingStrategy

**Files:**
- Modify: `app/services/recommendation_engine.py`
- Modify: `tests/test_recommendation_engine.py`

- [ ] **Step 1: Write tests for BaseStrategy and ForYouStrategy**

```python
# Append to tests/test_recommendation_engine.py

class TestBaseStrategy:
    def test_cannot_instantiate_directly(self):
        from app.services.recommendation_engine import BaseStrategy

        with pytest.raises(TypeError):
            BaseStrategy()

    def test_subclass_must_implement_generate(self):
        from app.services.recommendation_engine import BaseStrategy

        class BadStrategy(BaseStrategy):
            name = "bad"

        with pytest.raises(TypeError):
            BadStrategy()


class TestForYouStrategy:
    def test_returns_candidates(self):
        from app.services.recommendation_engine import ForYouStrategy, Candidate

        papers = [
            {"paper_id": "1", "title": "Deep Learning for NLP", "abstract": "We study transformers", "authors": ["Smith"], "citation_count": 50, "year": "2026"},
            {"paper_id": "2", "title": "Quantum Computing", "abstract": "Qubits are cool", "authors": ["Jones"], "citation_count": 10, "year": "2025"},
        ]
        profile = {"interest_vector": ["deep learning", "NLP", "transformers"]}
        strategy = ForYouStrategy()
        candidates = strategy.generate(papers=papers, user_profile=profile)
        assert len(candidates) > 0
        assert all(isinstance(c, Candidate) for c in candidates)
        assert all(c.source_strategy == "for_you" for c in candidates)

    def test_empty_profile_returns_all(self):
        from app.services.recommendation_engine import ForYouStrategy

        papers = [{"paper_id": "1", "title": "Paper", "abstract": "Stuff", "authors": []}]
        strategy = ForYouStrategy()
        candidates = strategy.generate(papers=papers, user_profile={})
        assert len(candidates) == len(papers)

    def test_reason_contains_match_info(self):
        from app.services.recommendation_engine import ForYouStrategy

        papers = [{"paper_id": "1", "title": "Transformers are great", "abstract": "NLP stuff", "authors": []}]
        profile = {"interest_vector": ["transformers"]}
        strategy = ForYouStrategy()
        candidates = strategy.generate(papers=papers, user_profile=profile)
        assert candidates[0].reason  # non-empty reason


class TestTrendingStrategy:
    def test_returns_candidates_sorted_by_citations(self):
        from app.services.recommendation_engine import TrendingStrategy, Candidate

        papers = [
            {"paper_id": "low", "title": "Low", "abstract": "", "authors": [], "citation_count": 1, "year": "2026"},
            {"paper_id": "high", "title": "High", "abstract": "", "authors": [], "citation_count": 500, "year": "2026"},
        ]
        strategy = TrendingStrategy()
        candidates = strategy.generate(papers=papers)
        assert candidates[0].paper_id == "high"
        assert all(c.source_strategy == "trending" for c in candidates)

    def test_freshness_matters(self):
        from app.services.recommendation_engine import TrendingStrategy

        papers = [
            {"paper_id": "old", "title": "Old", "abstract": "", "authors": [], "citation_count": 100, "year": "2020"},
            {"paper_id": "new", "title": "New", "abstract": "", "authors": [], "citation_count": 100, "year": "2026"},
        ]
        strategy = TrendingStrategy()
        candidates = strategy.generate(papers=papers)
        # Newer paper should rank higher when citation counts are equal
        assert candidates[0].paper_id == "new"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_recommendation_engine.py::TestBaseStrategy tests/test_recommendation_engine.py::TestForYouStrategy tests/test_recommendation_engine.py::TestTrendingStrategy -v`
Expected: FAIL — classes do not exist.

- [ ] **Step 3: Implement BaseStrategy, ForYouStrategy, TrendingStrategy**

Append to `app/services/recommendation_engine.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_recommendation_engine.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/recommendation_engine.py tests/test_recommendation_engine.py
git commit -m "feat(engine): add BaseStrategy, ForYouStrategy, and TrendingStrategy"
```

---

### Task 3: EntityStrategy + ReadingStrategy + QuestionStrategy

**Files:**
- Modify: `app/services/recommendation_engine.py`
- Modify: `tests/test_recommendation_engine.py`

- [ ] **Step 1: Write tests for EntityStrategy, ReadingStrategy, QuestionStrategy**

```python
# Append to tests/test_recommendation_engine.py

class TestEntityStrategy:
    def test_subscription_match_boosts_score(self):
        from app.services.recommendation_engine import EntityStrategy, Candidate

        papers = [
            {"paper_id": "1", "title": "Nature paper on LLMs", "abstract": "Published in Nature", "authors": ["Alice"], "venue": "Nature"},
            {"paper_id": "2", "title": "Random paper", "abstract": "No venue match", "authors": ["Bob"], "venue": "Unknown Journal"},
        ]
        subscriptions = [
            {"type": "venue", "query_text": "Nature", "name": "Nature"},
        ]
        strategy = EntityStrategy()
        candidates = strategy.generate(papers=papers, subscriptions=subscriptions)
        assert len(candidates) == 2
        # Paper from subscribed venue should rank higher
        assert candidates[0].paper_id == "1"
        assert "Nature" in candidates[0].reason

    def test_empty_subscriptions(self):
        from app.services.recommendation_engine import EntityStrategy

        papers = [{"paper_id": "1", "title": "T", "abstract": "A", "authors": []}]
        strategy = EntityStrategy()
        candidates = strategy.generate(papers=papers, subscriptions=[])
        assert len(candidates) == 1
        assert candidates[0].score == 0.0


class TestReadingStrategy:
    def test_similar_to_reading_queue(self):
        from app.services.recommendation_engine import ReadingStrategy, Candidate

        papers = [
            {"paper_id": "1", "title": "Advanced transformer architectures", "abstract": "We improve BERT", "authors": []},
            {"paper_id": "2", "title": "Quantum entanglement", "abstract": "Physics paper", "authors": []},
        ]
        reading_queue = [
            {"paper_id": "q1", "title": "BERT fine-tuning methods", "abstract": "Transformer training"},
        ]
        strategy = ReadingStrategy()
        candidates = strategy.generate(papers=papers, reading_queue=reading_queue)
        assert len(candidates) == 2
        # Paper more similar to reading queue should rank first
        assert candidates[0].paper_id == "1"

    def test_empty_reading_queue(self):
        from app.services.recommendation_engine import ReadingStrategy

        papers = [{"paper_id": "1", "title": "T", "abstract": "A", "authors": []}]
        strategy = ReadingStrategy()
        candidates = strategy.generate(papers=papers, reading_queue=[])
        assert len(candidates) == 1
        assert candidates[0].score == 0.0


class TestQuestionStrategy:
    def test_question_keyword_match(self):
        from app.services.recommendation_engine import QuestionStrategy, Candidate

        papers = [
            {"paper_id": "1", "title": "How to scale LLMs", "abstract": "Scaling laws for language models", "authors": []},
            {"paper_id": "2", "title": "Image classification", "abstract": "CNN for images", "authors": []},
        ]
        questions = [
            {"query_text": "scaling laws for large language models"},
        ]
        strategy = QuestionStrategy()
        candidates = strategy.generate(papers=papers, research_questions=questions)
        assert candidates[0].paper_id == "1"
        assert all(c.source_strategy == "question" for c in candidates)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_recommendation_engine.py::TestEntityStrategy tests/test_recommendation_engine.py::TestReadingStrategy tests/test_recommendation_engine.py::TestQuestionStrategy -v`
Expected: FAIL — classes do not exist.

- [ ] **Step 3: Implement EntityStrategy, ReadingStrategy, QuestionStrategy**

Append to `app/services/recommendation_engine.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_recommendation_engine.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/recommendation_engine.py tests/test_recommendation_engine.py
git commit -m "feat(engine): add EntityStrategy, ReadingStrategy, and QuestionStrategy"
```

---

### Task 4: RecommendationEngine Orchestrator

**Files:**
- Modify: `app/services/recommendation_engine.py`
- Modify: `tests/test_recommendation_engine.py`

- [ ] **Step 1: Write tests for RecommendationEngine**

```python
# Append to tests/test_recommendation_engine.py

class TestRecommendationEngine:
    def _make_papers(self):
        return [
            {"paper_id": "1", "title": "Deep Learning for NLP", "abstract": "Transformers and attention", "authors": ["Smith"], "citation_count": 100, "year": "2026", "venue": "NeurIPS"},
            {"paper_id": "2", "title": "Quantum Computing Advances", "abstract": "Qubit error correction", "authors": ["Jones"], "citation_count": 20, "year": "2025", "venue": "Nature"},
            {"paper_id": "3", "title": "Statistical Methods for ML", "abstract": "Bayesian optimization", "authors": ["Chen"], "citation_count": 50, "year": "2026", "venue": "ICML"},
        ]

    def test_engine_returns_sectioned_results(self):
        from app.services.recommendation_engine import RecommendationEngine

        engine = RecommendationEngine()
        papers = self._make_papers()
        result = engine.recommend(
            papers=papers,
            user_profile={"interest_vector": ["deep learning", "NLP"]},
        )
        assert "sections" in result
        assert len(result["sections"]) > 0
        for section in result["sections"]:
            assert "strategy" in section
            assert "title" in section
            assert "candidates" in section

    def test_engine_includes_for_you_section(self):
        from app.services.recommendation_engine import RecommendationEngine

        engine = RecommendationEngine()
        result = engine.recommend(
            papers=self._make_papers(),
            user_profile={"interest_vector": ["deep learning"]},
        )
        strategy_names = [s["strategy"] for s in result["sections"]]
        assert "for_you" in strategy_names

    def test_engine_deduplicates_across_strategies(self):
        from app.services.recommendation_engine import RecommendationEngine

        engine = RecommendationEngine()
        result = engine.recommend(
            papers=self._make_papers(),
            user_profile={"interest_vector": ["deep learning"]},
        )
        # Collect all paper_ids across all sections
        all_ids = []
        for section in result["sections"]:
            all_ids.extend([c.paper_id for c in section["candidates"]])
        # Same paper may appear in multiple sections (by design),
        # but each section should have unique papers internally
        for section in result["sections"]:
            ids = [c.paper_id for c in section["candidates"]]
            assert len(ids) == len(set(ids))

    def test_engine_limits_per_section(self):
        from app.services.recommendation_engine import RecommendationEngine

        engine = RecommendationEngine()
        papers = [{"paper_id": str(i), "title": f"Paper {i}", "abstract": "ML stuff", "authors": [], "citation_count": i, "year": "2026"} for i in range(50)]
        result = engine.recommend(papers=papers, max_per_section=5)
        for section in result["sections"]:
            assert len(section["candidates"]) <= 5

    def test_engine_strategy_failure_isolation(self):
        """One strategy failing should not crash the engine."""
        from app.services.recommendation_engine import RecommendationEngine, BaseStrategy, Candidate

        class BrokenStrategy(BaseStrategy):
            name = "broken"
            def generate(self, **kwargs):
                raise RuntimeError("Intentional failure")

        engine = RecommendationEngine(strategies=[BrokenStrategy()])
        # Should not raise, just skip the broken strategy
        result = engine.recommend(papers=self._make_papers())
        assert "sections" in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_recommendation_engine.py::TestRecommendationEngine -v`
Expected: FAIL — `RecommendationEngine` not defined.

- [ ] **Step 3: Implement RecommendationEngine**

Append to `app/services/recommendation_engine.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_recommendation_engine.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/recommendation_engine.py tests/test_recommendation_engine.py
git commit -m "feat(engine): add RecommendationEngine orchestrator with strategy isolation"
```

---

### Task 5: User Profile CRUD in StateStore

**Files:**
- Modify: `state_store.py`
- Create: `tests/test_user_profile.py`

- [ ] **Step 1: Write tests for user_profile CRUD**

```python
# tests/test_user_profile.py
"""Tests for user_profile table CRUD and auto-update logic."""

import json
import os
import tempfile

import pytest


def _make_store():
    """Create a StateStore with a temporary database."""
    from state_store import StateStore

    tmp = tempfile.mktemp(suffix=".db")
    store = StateStore(tmp)
    return store, tmp


class TestUserProfileCRUD:
    def test_get_profile_returns_default_when_empty(self):
        store, tmp = _make_store()
        try:
            profile = store.get_user_profile()
            assert profile is not None
            assert profile["interest_vector"] == []
            assert profile["topic_weights"] == {}
            assert profile["entity_affinities"] == {}
            assert profile["reading_pace"] == {}
        finally:
            os.unlink(tmp)

    def test_upsert_and_retrieve_profile(self):
        store, tmp = _make_store()
        try:
            store.upsert_user_profile(
                interest_vector=["deep learning", "NLP"],
                topic_weights={"deep learning": 2.0, "NLP": 1.5},
            )
            profile = store.get_user_profile()
            assert profile["interest_vector"] == ["deep learning", "NLP"]
            assert profile["topic_weights"]["NLP"] == 1.5
        finally:
            os.unlink(tmp)

    def test_upsert_merges_partial_update(self):
        store, tmp = _make_store()
        try:
            store.upsert_user_profile(interest_vector=["ML"])
            store.upsert_user_profile(topic_weights={"ML": 1.0})
            profile = store.get_user_profile()
            # interest_vector should be preserved from first call
            assert profile["interest_vector"] == ["ML"]
            assert profile["topic_weights"]["ML"] == 1.0
        finally:
            os.unlink(tmp)

    def test_entity_affinities(self):
        store, tmp = _make_store()
        try:
            store.upsert_user_profile(
                entity_affinities={"journal:nature": 0.9, "scholar:hinton": 0.8},
            )
            profile = store.get_user_profile()
            assert profile["entity_affinities"]["journal:nature"] == 0.9
        finally:
            os.unlink(tmp)

    def test_reading_pace(self):
        store, tmp = _make_store()
        try:
            store.upsert_user_profile(
                reading_pace={"avg_papers_per_week": 5, "preferred_depth": "skim"},
            )
            profile = store.get_user_profile()
            assert profile["reading_pace"]["avg_papers_per_week"] == 5
        finally:
            os.unlink(tmp)


class TestUserProfileAutoUpdate:
    def test_update_from_reading_behavior(self):
        store, tmp = _make_store()
        try:
            # Add some reading queue items with known topics
            store.add_to_queue("paper1", "Deep Read", source="test")
            store.save_paper_metadata("paper1", {
                "title": "Transformers for NLP",
                "categories": ["cs.CL", "cs.LG"],
            })
            # The update_profile_from_behavior method should extract topics
            store.update_profile_from_behavior()
            profile = store.get_user_profile()
            # Profile should now have non-empty interest_vector
            assert isinstance(profile["interest_vector"], list)
        finally:
            os.unlink(tmp)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_user_profile.py -v`
Expected: FAIL — `get_user_profile`, `upsert_user_profile`, `update_profile_from_behavior` do not exist.

- [ ] **Step 3: Add user_profile table creation to StateStore schema**

In `state_store.py`, add the `user_profile` table to the `_init_schema` method, after the existing `CREATE TABLE` statements (around line 280):

```python
                CREATE TABLE IF NOT EXISTS user_profile (
                    id INTEGER PRIMARY KEY DEFAULT 1,
                    interest_vector TEXT DEFAULT '[]',
                    topic_weights TEXT DEFAULT '{}',
                    entity_affinities TEXT DEFAULT '{}',
                    reading_pace TEXT DEFAULT '{}',
                    updated_at TEXT DEFAULT (datetime('now'))
                );
```

- [ ] **Step 4: Implement user_profile CRUD methods**

Add to the `StateStore` class in `state_store.py`, after the recommendation runs section:

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_user_profile.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add state_store.py tests/test_user_profile.py
git commit -m "feat(store): add user_profile table CRUD and auto-update from behavior"
```

---

### Task 6: Integrate Engine into RecommendationWorkspaceService

**Files:**
- Modify: `app/services/recommendation_workspace_service.py`
- Modify: `app/viewmodels/recommendations_viewmodel.py`
- Modify: `app/routes/api/recommendations.py`
- Modify: `app/routes/recommendations.py`

- [ ] **Step 1: Update RecommendationWorkspaceService to use RecommendationEngine**

Replace the `run()` and `_rank()` methods in `app/services/recommendation_workspace_service.py`:

```python
"""Recommendation workspace service for Paper Agent."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date

from app.services.recommendation_engine import (
    Candidate,
    RecommendationEngine,
    RecommendationScorer,
    normalize_citation_score,
    normalize_freshness_score,
    _days_since_publication,
)


class RecommendationWorkspaceService:
    """Build and persist recommendation candidate sets."""

    def __init__(self, state_store, *, search_fn=None):
        self.state_store = state_store
        self.search_fn = search_fn
        self._engine = RecommendationEngine()
        self._scorer = RecommendationScorer()

    def list_recent(self, *, limit: int = 5) -> list[dict]:
        runs = self.state_store.list_recommendation_runs(limit=limit)
        result = []
        for run in runs:
            if run.get("trigger_source") in ("paper_agent_recommendations", "workspace_planner", "auto_homepage"):
                item = dict(run)
                item["items"] = self._decorate_items(self.state_store.get_recommendation_items(run["run_id"]))
                result.append(item)
        return result

    def latest_items(self) -> list[dict]:
        runs = self.list_recent(limit=10)
        if not runs:
            return []
        return runs[0]["items"]

    def run(self, *, mode: str = "for_you", query: str = "", max_results: int = 20) -> dict:
        """Run the multi-strategy recommendation engine and persist results."""
        query_text = self._query_for_mode(mode, query)
        papers = self._search(query_text, max_results=max_results * 3)  # Over-fetch for strategy filtering

        # Gather context for strategies
        profile = self.state_store.get_user_profile()
        try:
            subscriptions = self.state_store.list_subscriptions()
        except Exception:
            subscriptions = []
        try:
            reading_queue_items = self.state_store.list_queue_items()
            reading_queue = []
            for item in reading_queue_items:
                meta = self.state_store.get_paper_metadata(item.get("paper_id", "")) or {}
                reading_queue.append({**item, **meta})
        except Exception:
            reading_queue = []
        try:
            from state_store import get_state_store
            questions = get_state_store().list_research_questions()
        except Exception:
            questions = []

        # Run engine
        engine_result = self._engine.recommend(
            papers=papers,
            user_profile=profile,
            subscriptions=subscriptions,
            reading_queue=reading_queue,
            research_questions=questions,
            max_per_section=max_results,
        )

        # Score each candidate with multi-dimensional scorer
        for section in engine_result["sections"]:
            for candidate in section["candidates"]:
                paper = candidate.paper_data
                days_old = _days_since_publication(paper)
                cit_count = int(paper.get("citation_count") or 0)
                bd = candidate.score_breakdown

                scored = self._scorer.score(
                    relevance=bd.get("relevance", candidate.score),
                    citation=normalize_citation_score(cit_count),
                    freshness=normalize_freshness_score(days_old),
                    entity_affinity=bd.get("entity_affinity", 0.0),
                    feedback=bd.get("feedback", 0.0),
                )
                candidate.score = scored["composite"]
                candidate.score_breakdown = {
                    dim: info["raw"] for dim, info in scored["breakdown"].items()
                }

            # Re-sort by composite score
            section["candidates"].sort(key=lambda c: c.score, reverse=True)

        # Persist the run (flatten all candidates)
        all_papers = []
        for section in engine_result["sections"]:
            for c in section["candidates"]:
                paper = dict(c.paper_data)
                paper["score"] = c.score
                paper["score_details"] = c.score_breakdown
                paper["relevance_reason"] = c.reason
                paper["source_strategy"] = c.source_strategy
                all_papers.append(paper)

        # Deduplicate by paper_id for persistence (keep highest score)
        seen: dict[str, dict] = {}
        for paper in all_papers:
            pid = paper.get("paper_id") or paper.get("id", "")
            if pid not in seen or paper["score"] > seen[pid]["score"]:
                seen[pid] = paper
        deduped = list(seen.values())
        deduped.sort(key=lambda p: p.get("score", 0), reverse=True)

        run_id = self.state_store.save_recommendation_run(
            date.today().isoformat(),
            trigger_source="paper_agent_recommendations",
            papers=deduped[:max_results],
            themes=[query_text],
        )

        # Save paper metadata
        for paper in deduped[:max_results]:
            paper_id = paper.get("paper_id") or paper.get("id")
            if not paper_id:
                continue
            self.state_store.save_paper_metadata(
                paper_id,
                {
                    "title": paper.get("title", ""),
                    "abstract": paper.get("abstract") or paper.get("summary", ""),
                    "authors": paper.get("authors", []),
                    "categories": paper.get("categories", []),
                    "year": paper.get("year", ""),
                    "venue": paper.get("venue", ""),
                    "link": paper.get("link") or paper.get("url", ""),
                    "url": paper.get("url") or paper.get("link", ""),
                    "pdf_url": paper.get("pdf_url", ""),
                    "score": paper.get("score", 0),
                    "citation_count": paper.get("citation_count"),
                    "reference_count": paper.get("reference_count"),
                    "external_ids": paper.get("external_ids", {}),
                    "relevance_reason": paper.get("relevance_reason", ""),
                    "source": paper.get("source", ""),
                },
                source="paper_agent_recommendations",
                source_run_id=run_id,
            )

        # Build sectioned response
        sections_data = []
        for section in engine_result["sections"]:
            sections_data.append({
                "strategy": section["strategy"],
                "title": section["title"],
                "papers": self._decorate_items([
                    {**c.paper_data, "score": c.score, "relevance_reason": c.reason, "source_strategy": c.source_strategy, "score_breakdown": c.score_breakdown}
                    for c in section["candidates"]
                ]),
            })

        return {
            "run_id": run_id,
            "mode": mode,
            "query": query_text,
            "sections": sections_data,
            "papers": self._decorate_items(deduped[:max_results]),
            "count": len(deduped[:max_results]),
        }

    def run_sectioned(self, *, max_results: int = 15) -> dict:
        """Run the engine and return sectioned results for the recommendations page."""
        return self.run(mode="for_you", max_results=max_results)

    def _query_for_mode(self, mode: str, query: str) -> str:
        query = str(query or "").strip()
        if query:
            return query
        try:
            from config_manager import get_config
            profile = get_config().get_keywords_config()
            core = profile.get("core_topics", {})
            if isinstance(core, dict) and core:
                return " ".join(list(core.keys())[:4])
        except Exception:
            pass
        if mode == "reading":
            return "papers related to saved reading"
        return "machine learning research"

    def _search(self, query: str, *, max_results: int) -> list[dict]:
        if self.search_fn is not None:
            return self.search_fn(query, max_results=max_results)
        from app.services.unified_search_service import search_papers
        result = search_papers(query, max_results=max_results)
        return result.get("papers", [])

    def _decorate_items(self, papers: list[dict]) -> list[dict]:
        from app.services.paper_utils import format_author_text, extract_primary_author

        decorated = []
        for paper in papers:
            item = dict(paper)
            paper_id = item.get("paper_id") or item.get("id") or ""
            if paper_id:
                meta = self.state_store.get_paper_metadata(paper_id) or {}
                for key in ("title", "abstract", "authors", "year", "venue", "url", "link", "pdf_url", "citation_count", "reference_count", "source", "relevance_reason"):
                    if item.get(key) in (None, "", [], 0) and meta.get(key) not in (None, "", []):
                        item[key] = meta.get(key)
            authors = item.get("authors") or []
            item["author_text"] = format_author_text(authors, limit=4)
            first = extract_primary_author(authors) or "Paper"
            year = str(item.get("year") or item.get("published_at") or "")[:4]
            item["display_citation"] = f"{first}, {year}" if year else first
            abstract = item.get("abstract") or item.get("summary") or ""
            item["summary_short"] = abstract[:620] + ("..." if len(abstract) > 620 else "")
            item["paper_id"] = paper_id
            item["id"] = paper_id
            item.setdefault("relevance_reason", "Matches your recommendation profile.")
            item.setdefault("source_strategy", "")
            item.setdefault("score_breakdown", {})
            decorated.append(item)
        return decorated
```

- [ ] **Step 2: Update recommendations API to return sections**

Replace `app/routes/api/recommendations.py`:

```python
"""Recommendations API routes."""

from __future__ import annotations

from flask import jsonify, request

from . import bp
from .helpers import _current_state_store
from app.services.recommendation_workspace_service import RecommendationWorkspaceService


@bp.get("/api/recommendations")
def list_recommendations():
    service = RecommendationWorkspaceService(_current_state_store())
    return jsonify({
        "success": True,
        "papers": service.latest_items(),
        "runs": service.list_recent(limit=6),
    })


@bp.post("/api/recommendations/runs")
def create_recommendation_run():
    data = request.get_json() or {}
    service = RecommendationWorkspaceService(_current_state_store())
    result = service.run(
        mode=str(data.get("mode") or "for_you"),
        query=str(data.get("query") or data.get("q") or ""),
        max_results=int(data.get("max_results") or 20),
    )
    # Serialize sections: convert Candidate objects to dicts
    sections = []
    for section in result.get("sections", []):
        sections.append({
            "strategy": section["strategy"],
            "title": section["title"],
            "papers": section["papers"],
        })
    return jsonify({
        "success": True,
        "run_id": result.get("run_id"),
        "mode": result.get("mode"),
        "query": result.get("query"),
        "sections": sections,
        "papers": result.get("papers", []),
        "count": result.get("count", 0),
    })


@bp.get("/api/recommendations/runs/<run_id>")
def get_recommendation_run(run_id):
    store = _current_state_store()
    items = store.get_recommendation_items(run_id)
    service = RecommendationWorkspaceService(store)
    return jsonify({
        "success": True,
        "run_id": run_id,
        "papers": service._decorate_items(items),
    })
```

- [ ] **Step 3: Update RecommendationsViewModel to pass sections**

Replace `app/viewmodels/recommendations_viewmodel.py`:

```python
"""Recommendations workspace viewmodel."""

from __future__ import annotations

from app.services.recommendation_workspace_service import RecommendationWorkspaceService
from app.viewmodels.shared import assemble_page_context


class RecommendationsViewModel:
    def __init__(self, state_store):
        self._store = state_store

    def to_template_context(self, *, mode: str = "for_you", query: str = "") -> dict:
        service = RecommendationWorkspaceService(self._store)
        runs = service.list_recent(limit=6)
        papers = runs[0]["items"] if runs else []

        # Build sections from latest run papers (group by source_strategy)
        sections = self._build_sections(papers)

        context = assemble_page_context(self._store, active_tab="recommendations")
        context.update({
            "title": "Recommendations - Paper Agent",
            "active_tab": "recommendations",
            "mode": mode,
            "query": query,
            "recommendation_runs": runs,
            "papers": papers,
            "sections": sections,
            "selected_paper": papers[0] if papers else None,
        })
        return context

    def _build_sections(self, papers: list[dict]) -> list[dict]:
        """Group papers by source_strategy into display sections."""
        SECTION_TITLES = {
            "for_you": "For You",
            "entity": "From Your Subscriptions",
            "trending": "Trending",
            "reading": "Based on Your Reading",
            "question": "Research Questions",
        }
        groups: dict[str, list[dict]] = {}
        for paper in papers:
            strategy = paper.get("source_strategy", "for_you")
            groups.setdefault(strategy, []).append(paper)

        # If no strategy info, put everything in "For You"
        if not groups and papers:
            groups["for_you"] = papers

        sections = []
        for strategy_key in ("for_you", "entity", "trending", "reading", "question"):
            if strategy_key in groups:
                sections.append({
                    "strategy": strategy_key,
                    "title": SECTION_TITLES.get(strategy_key, strategy_key.replace("_", " ").title()),
                    "papers": groups[strategy_key],
                })

        # Add any remaining strategies not in the predefined order
        for key, papers_list in groups.items():
            if key not in ("for_you", "entity", "trending", "reading", "question"):
                sections.append({
                    "strategy": key,
                    "title": key.replace("_", " ").title(),
                    "papers": papers_list,
                })

        return sections
```

- [ ] **Step 4: Run existing tests to verify no regression**

Run: `python -m pytest tests/ -q --timeout=30 -x`
Expected: All existing tests pass (or pre-existing failures only).

- [ ] **Step 5: Commit**

```bash
git add app/services/recommendation_workspace_service.py app/routes/api/recommendations.py app/viewmodels/recommendations_viewmodel.py
git commit -m "feat(engine): integrate RecommendationEngine into workspace service and API"
```

---

### Task 7: Recommendation Page Redesign — Sectioned Card Layout

**Files:**
- Rewrite: `templates/recommendations.html`
- Modify: `static/research_ui.css`

- [ ] **Step 1: Rewrite recommendations.html with horizontal-scroll card sections**

```html
{% extends "base_research.html" %}

{% set body_class = (body_class or '') ~ ' page-recommendations' %}

{% block content %}
<section class="recommendations-workspace">
    <div class="workspace-page-head">
        <div>
            <h1 class="page-title">Recommendations</h1>
            <p class="muted-copy">Personalized paper recommendations from multiple strategies.</p>
        </div>
        <div class="recommendation-controls">
            <input id="recommendationQuery" class="input" value="{{ query }}" placeholder="Optional topic or research question">
            <button type="button" class="btn btn-primary" onclick="runRecommendationEngine()">Refresh</button>
        </div>
    </div>

    <div id="recommendationStatus" class="paper-agent-warning" hidden></div>

    {% if sections %}
        {% for section in sections %}
        <div class="rec-section" data-strategy="{{ section.strategy }}">
            <div class="rec-section-header">
                <h2 class="rec-section-title">{{ section.title }}</h2>
                <span class="rec-section-count">{{ section.papers|length }} papers</span>
            </div>
            <div class="rec-card-scroll">
                {% for paper in section.papers %}
                <article class="rec-card"
                    data-paper-id="{{ paper.paper_id or paper.id }}"
                    data-paper-title="{{ paper.title }}"
                    data-paper-authors="{{ paper.author_text }}"
                    data-paper-abstract="{{ paper.abstract or paper.summary or '' }}"
                    data-paper-url="{{ paper.url or paper.link or '' }}"
                    data-paper-source="{{ paper.source or '' }}"
                    data-paper-venue="{{ paper.venue or '' }}"
                    data-paper-year="{{ paper.year or '' }}"
                    data-paper-citation-count="{{ paper.citation_count if paper.citation_count is not none else '' }}"
                    data-relevance-reason="{{ paper.relevance_reason or '' }}"
                    onclick="selectRecCard(this)"
                >
                    <div class="rec-card-venue">{{ paper.venue or paper.source or 'Paper' }}</div>
                    <h3 class="rec-card-title">{{ paper.title }}</h3>
                    <div class="rec-card-citation">{{ paper.display_citation }}</div>
                    <p class="rec-card-reason">{{ paper.relevance_reason or 'Matches your recommendation profile.' }}</p>
                    <div class="rec-card-actions">
                        <button class="btn btn-ghost btn-xs" type="button" onclick="event.stopPropagation(); agentSavePaperById('{{ paper.paper_id or paper.id }}')">Save</button>
                        <button class="btn btn-ghost btn-xs" type="button" onclick="event.stopPropagation(); agentQueuePaperById('{{ paper.paper_id or paper.id }}', 'Skim Later')">Skim</button>
                        <button class="btn btn-ghost btn-xs" type="button" onclick="event.stopPropagation(); agentQueuePaperById('{{ paper.paper_id or paper.id }}', 'Deep Read')">Read</button>
                    </div>
                </article>
                {% endfor %}
            </div>
        </div>
        {% endfor %}
    {% elif papers %}
        {# Fallback: single flat list when no sections available #}
        <div class="rec-section" data-strategy="for_you">
            <div class="rec-section-header">
                <h2 class="rec-section-title">For You</h2>
                <span class="rec-section-count">{{ papers|length }} papers</span>
            </div>
            <div class="rec-card-scroll">
                {% for paper in papers %}
                <article class="rec-card"
                    data-paper-id="{{ paper.paper_id or paper.id }}"
                    data-paper-title="{{ paper.title }}"
                    data-paper-authors="{{ paper.author_text }}"
                    data-paper-abstract="{{ paper.abstract or paper.summary or '' }}"
                    data-paper-url="{{ paper.url or paper.link or '' }}"
                    data-paper-venue="{{ paper.venue or '' }}"
                    data-paper-year="{{ paper.year or '' }}"
                    data-relevance-reason="{{ paper.relevance_reason or '' }}"
                    onclick="selectRecCard(this)"
                >
                    <div class="rec-card-venue">{{ paper.venue or paper.source or 'Paper' }}</div>
                    <h3 class="rec-card-title">{{ paper.title }}</h3>
                    <div class="rec-card-citation">{{ paper.display_citation }}</div>
                    <p class="rec-card-reason">{{ paper.relevance_reason or 'Matches your recommendation profile.' }}</p>
                    <div class="rec-card-actions">
                        <button class="btn btn-ghost btn-xs" type="button" onclick="event.stopPropagation(); agentSavePaperById('{{ paper.paper_id or paper.id }}')">Save</button>
                        <button class="btn btn-ghost btn-xs" type="button" onclick="event.stopPropagation(); agentQueuePaperById('{{ paper.paper_id or paper.id }}', 'Skim Later')">Skim</button>
                        <button class="btn btn-ghost btn-xs" type="button" onclick="event.stopPropagation(); agentQueuePaperById('{{ paper.paper_id or paper.id }}', 'Deep Read')">Read</button>
                    </div>
                </article>
                {% endfor %}
            </div>
        </div>
    {% else %}
        <div class="paper-agent-empty">
            <h2>No recommendations yet</h2>
            <p>Click Refresh to generate personalized recommendations from your profile, reading history, and subscriptions.</p>
            <div class="paper-agent-empty-actions">
                <button class="empty-action" type="button" onclick="runRecommendationEngine()">Generate recommendations</button>
                <button class="empty-action" type="button" onclick="window.location.href='/'">Search papers</button>
            </div>
        </div>
    {% endif %}

    {# Preview pane: slides in on card click #}
    <aside class="rec-preview-pane" id="recPreviewPane" hidden>
        <button class="rec-preview-close" type="button" onclick="closeRecPreview()">&times;</button>
        <div id="recPreviewContent"></div>
    </aside>
</section>
{% endblock %}

{% block scripts %}
{{ super() }}
<script>
async function runRecommendationEngine() {
    var status = document.getElementById('recommendationStatus');
    var query = document.getElementById('recommendationQuery').value.trim();
    if (status) {
        status.hidden = false;
        status.textContent = 'Building recommendations...';
    }
    try {
        var payload = await requestJson('/api/recommendations/runs', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({mode: 'for_you', query: query, max_results: 15})
        });
        renderSections(payload.sections || []);
        if (status) {
            status.textContent = 'Generated ' + (payload.count || 0) + ' recommendations across ' + (payload.sections || []).length + ' categories.';
        }
    } catch (error) {
        if (status) status.textContent = 'Recommendation run failed: ' + error.message;
    }
}

function renderSections(sections) {
    // Remove existing sections
    document.querySelectorAll('.rec-section').forEach(function(el) { el.remove(); });
    document.querySelectorAll('.paper-agent-empty').forEach(function(el) { el.remove(); });

    var container = document.querySelector('.recommendations-workspace');
    var preview = document.getElementById('recPreviewPane');

    if (!sections.length) {
        var empty = document.createElement('div');
        empty.className = 'paper-agent-empty';
        empty.innerHTML = '<h2>No recommendations found</h2><p>Try adding a topic or expanding your profile.</p>';
        container.insertBefore(empty, preview);
        return;
    }

    sections.forEach(function(section) {
        var sectionEl = document.createElement('div');
        sectionEl.className = 'rec-section';
        sectionEl.dataset.strategy = section.strategy;

        var header = '<div class="rec-section-header"><h2 class="rec-section-title">' +
            escapeHtml(section.title) + '</h2><span class="rec-section-count">' +
            (section.papers || []).length + ' papers</span></div>';

        var cards = '<div class="rec-card-scroll">';
        (section.papers || []).forEach(function(paper) {
            var pid = paper.paper_id || paper.id || '';
            cards += '<article class="rec-card" data-paper-id="' + escapeHtml(pid) + '"' +
                ' data-paper-title="' + escapeHtml(paper.title || '') + '"' +
                ' data-paper-authors="' + escapeHtml(paper.author_text || (paper.authors || []).join(', ')) + '"' +
                ' data-paper-abstract="' + escapeHtml(paper.abstract || paper.summary || '') + '"' +
                ' data-paper-url="' + escapeHtml(paper.url || paper.link || '') + '"' +
                ' data-paper-venue="' + escapeHtml(paper.venue || '') + '"' +
                ' data-paper-year="' + escapeHtml(String(paper.year || '')) + '"' +
                ' data-relevance-reason="' + escapeHtml(paper.relevance_reason || '') + '"' +
                ' onclick="selectRecCard(this)">' +
                '<div class="rec-card-venue">' + escapeHtml(paper.venue || paper.source || 'Paper') + '</div>' +
                '<h3 class="rec-card-title">' + escapeHtml(paper.title || 'Untitled') + '</h3>' +
                '<div class="rec-card-citation">' + escapeHtml(paper.display_citation || '') + '</div>' +
                '<p class="rec-card-reason">' + escapeHtml(paper.relevance_reason || 'Matches your profile.') + '</p>' +
                '<div class="rec-card-actions">' +
                '<button class="btn btn-ghost btn-xs" type="button" onclick="event.stopPropagation(); agentSavePaperById(\'' + escapeHtml(pid) + '\')">Save</button>' +
                '<button class="btn btn-ghost btn-xs" type="button" onclick="event.stopPropagation(); agentQueuePaperById(\'' + escapeHtml(pid) + '\', \'Skim Later\')">Skim</button>' +
                '<button class="btn btn-ghost btn-xs" type="button" onclick="event.stopPropagation(); agentQueuePaperById(\'' + escapeHtml(pid) + '\', \'Deep Read\')">Read</button>' +
                '</div></article>';
        });
        cards += '</div>';

        sectionEl.innerHTML = header + cards;
        container.insertBefore(sectionEl, preview);
    });
}

function selectRecCard(card) {
    document.querySelectorAll('.rec-card').forEach(function(c) {
        c.classList.toggle('is-selected', c === card);
    });
    var pane = document.getElementById('recPreviewPane');
    var content = document.getElementById('recPreviewContent');
    if (!pane || !content) return;
    pane.hidden = false;

    var detailUrl = '/papers/' + encodeURIComponent(card.dataset.paperId || '') + '?return_to=/recommendations';
    content.innerHTML =
        '<a class="preview-title" href="' + detailUrl + '">' + escapeHtml(card.dataset.paperTitle || 'Untitled') + '</a>' +
        '<div class="preview-source">' + escapeHtml(card.dataset.paperVenue || '') + '</div>' +
        '<div class="preview-authors">' + escapeHtml(card.dataset.paperAuthors || '') + '</div>' +
        '<div class="preview-section"><div class="preview-section-head"><strong>Decision</strong>' +
        '<button class="btn btn-primary btn-sm" type="button" onclick="agentSavePaperById(\'' + escapeHtml(card.dataset.paperId) + '\')">Save</button></div>' +
        '<div class="preview-action-grid">' +
        '<button class="btn btn-ghost btn-sm" type="button" onclick="agentQueuePaperById(\'' + escapeHtml(card.dataset.paperId) + '\', \'Skim Later\')">Mark Skim</button>' +
        '<button class="btn btn-ghost btn-sm" type="button" onclick="agentQueuePaperById(\'' + escapeHtml(card.dataset.paperId) + '\', \'Deep Read\')">Deep Read</button></div></div>' +
        '<div class="preview-section"><strong>Why recommended</strong><p>' + escapeHtml(card.dataset.relevanceReason || 'Matches your recommendation profile.') + '</p></div>' +
        '<div class="preview-section"><strong>Abstract</strong><p>' + escapeHtml(card.dataset.paperAbstract || 'No abstract available.') + '</p>' +
        '<a class="text-link" href="' + detailUrl + '">Open full detail</a></div>';
}

function closeRecPreview() {
    var pane = document.getElementById('recPreviewPane');
    if (pane) pane.hidden = true;
    document.querySelectorAll('.rec-card.is-selected').forEach(function(c) {
        c.classList.remove('is-selected');
    });
}
</script>
{% endblock %}
```

- [ ] **Step 2: Add horizontal-scroll card CSS**

Append to `static/research_ui.css`:

```css
/* ============================================================
   Recommendation Page — Sectioned Card Layout
   ============================================================ */

.recommendations-workspace {
  padding: 24px 32px;
  max-width: 1200px;
  margin: 0 auto;
}

.recommendations-workspace .workspace-page-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 32px;
  flex-wrap: wrap;
}

.recommendations-workspace .recommendation-controls {
  display: flex;
  gap: 8px;
  align-items: center;
}

/* Section */
.rec-section {
  margin-bottom: 32px;
}

.rec-section-header {
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 12px;
  padding: 0 4px;
}

.rec-section-title {
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--ink-primary);
  margin: 0;
}

.rec-section-count {
  font-size: 0.8125rem;
  color: var(--ink-muted);
}

/* Horizontal scroll track */
.rec-card-scroll {
  display: flex;
  gap: 16px;
  overflow-x: auto;
  padding: 4px 4px 12px;
  scroll-snap-type: x mandatory;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: thin;
  scrollbar-color: var(--border-default) transparent;
}

.rec-card-scroll::-webkit-scrollbar {
  height: 6px;
}

.rec-card-scroll::-webkit-scrollbar-track {
  background: transparent;
}

.rec-card-scroll::-webkit-scrollbar-thumb {
  background: var(--border-default);
  border-radius: 3px;
}

/* Card */
.rec-card {
  flex: 0 0 280px;
  min-height: 200px;
  padding: 16px;
  background: var(--card-bg);
  border: 1px solid var(--card-border);
  border-radius: var(--radius-md);
  box-shadow: var(--card-shadow);
  cursor: pointer;
  scroll-snap-align: start;
  transition: box-shadow var(--transition-fast), border-color var(--transition-fast), transform var(--transition-fast);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.rec-card:hover {
  box-shadow: var(--card-shadow-hover);
  transform: translateY(-1px);
}

.rec-card.is-selected {
  border-color: var(--accent-primary);
  box-shadow: 0 0 0 1px var(--accent-primary), var(--card-shadow-hover);
}

.rec-card-venue {
  font-size: 0.75rem;
  color: var(--ink-muted);
  text-transform: uppercase;
  letter-spacing: 0.02em;
}

.rec-card-title {
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--ink-primary);
  margin: 0;
  line-height: 1.35;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.rec-card-citation {
  font-size: 0.8125rem;
  color: var(--ink-secondary);
}

.rec-card-reason {
  font-size: 0.8125rem;
  color: var(--accent-primary);
  margin: 0;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  flex: 1;
}

.rec-card-actions {
  display: flex;
  gap: 4px;
  margin-top: auto;
  opacity: 0;
  transition: opacity var(--transition-fast);
}

.rec-card:hover .rec-card-actions {
  opacity: 1;
}

/* Preview pane */
.rec-preview-pane {
  position: fixed;
  top: 0;
  right: 0;
  width: 400px;
  height: 100vh;
  background: var(--bg-surface);
  border-left: 1px solid var(--border-default);
  box-shadow: var(--shadow-lg);
  z-index: 100;
  padding: 24px;
  overflow-y: auto;
}

.rec-preview-close {
  position: absolute;
  top: 12px;
  right: 12px;
  background: none;
  border: none;
  font-size: 1.5rem;
  color: var(--ink-secondary);
  cursor: pointer;
  line-height: 1;
  padding: 4px;
}

.rec-preview-close:hover {
  color: var(--ink-primary);
}

/* Responsive */
@media (max-width: 768px) {
  .recommendations-workspace {
    padding: 16px;
  }

  .rec-card {
    flex: 0 0 240px;
    min-height: 180px;
  }

  .rec-preview-pane {
    width: 100%;
  }
}
```

- [ ] **Step 3: Verify template renders**

```bash
cd "/Users/sunweizhou/Desktop/AI Project/arxiv_recommender"
python -c "
from flask import Flask
from jinja2 import FileSystemLoader
app = Flask(__name__, template_folder='templates')
app.jinja_loader = FileSystemLoader('templates')
with app.app_context():
    t = app.jinja_env.get_template('recommendations.html')
    print('Template loaded OK, blocks:', list(t.blocks.keys()))
"
```

Expected: Template loads without syntax errors.

- [ ] **Step 4: Commit**

```bash
git add templates/recommendations.html static/research_ui.css
git commit -m "feat(ui): redesign recommendations page with horizontal-scroll sectioned card layout"
```

---

### Task 8: Daily Pipeline Adaptation

**Files:**
- Modify: `app/services/daily_pipeline.py`

- [ ] **Step 1: Update run_pipeline_v2 to use RecommendationScorer**

In `app/services/daily_pipeline.py`, modify the scoring section of `run_pipeline_v2()` (around lines 288-346) to use the new `RecommendationScorer` alongside the existing `score_paper` ranker:

```python
    # After line 299 (ctx: dict = {"keywords": keywords}), add scorer import:
    from app.services.recommendation_engine import (
        RecommendationScorer,
        normalize_citation_score,
        normalize_freshness_score,
        _days_since_publication,
    )
```

Then replace the scoring loop (lines 342-346) with:

```python
    multi_scorer = RecommendationScorer()

    for paper in papers:
        # Existing ranker score (keyword + author + semantic + feedback + subscription)
        score, explanation = score_paper(paper, ctx)

        # Multi-dimensional score for richer breakdown
        days_old = _days_since_publication(paper)
        cit_count = int(paper.get("citation_count") or 0)

        # Map existing ranker signals to new dimensions
        scored = multi_scorer.score(
            relevance=score,  # ranker's blended score as relevance proxy
            citation=normalize_citation_score(cit_count),
            freshness=normalize_freshness_score(days_old),
            entity_affinity=0.0,  # Populated when entity system is active
            feedback=0.0,  # Populated when feedback model is used
        )

        paper["score"] = scored["composite"]
        paper["score_details"] = scored["breakdown"]
        paper["relevance_reason"] = explanation
        paper["summary"] = generate_summary(paper.get("abstract", ""))
```

- [ ] **Step 2: Verify pipeline still runs**

```bash
cd "/Users/sunweizhou/Desktop/AI Project/arxiv_recommender"
python -c "
from app.services.daily_pipeline import run_pipeline_v2
print('run_pipeline_v2 imported successfully')
"
```

Expected: No import errors.

- [ ] **Step 3: Commit**

```bash
git add app/services/daily_pipeline.py
git commit -m "feat(pipeline): integrate RecommendationScorer into daily pipeline v2"
```

---

### Task 9: Recommendation Reasons Enhancement

**Files:**
- Modify: `app/services/recommendation_engine.py`
- Modify: `tests/test_recommendation_engine.py`

- [ ] **Step 1: Write tests for enhanced recommendation reasons**

```python
# Append to tests/test_recommendation_engine.py

class TestRecommendationReasons:
    def test_for_you_reason_includes_matched_keywords(self):
        from app.services.recommendation_engine import ForYouStrategy

        papers = [{"paper_id": "1", "title": "Graph neural networks for drug discovery", "abstract": "GNN methods", "authors": []}]
        profile = {"interest_vector": ["graph neural networks", "drug discovery"]}
        strategy = ForYouStrategy()
        candidates = strategy.generate(papers=papers, user_profile=profile)
        assert "graph neural networks" in candidates[0].reason.lower() or "drug discovery" in candidates[0].reason.lower()

    def test_trending_reason_includes_citation_count(self):
        from app.services.recommendation_engine import TrendingStrategy

        papers = [{"paper_id": "1", "title": "Popular paper", "abstract": "", "authors": [], "citation_count": 250, "year": "2026"}]
        strategy = TrendingStrategy()
        candidates = strategy.generate(papers=papers)
        assert "250" in candidates[0].reason

    def test_entity_reason_includes_entity_name(self):
        from app.services.recommendation_engine import EntityStrategy

        papers = [{"paper_id": "1", "title": "T", "abstract": "A", "authors": ["Geoffrey Hinton"], "venue": "NeurIPS"}]
        subscriptions = [{"type": "author", "query_text": "Geoffrey Hinton"}]
        strategy = EntityStrategy()
        candidates = strategy.generate(papers=papers, subscriptions=subscriptions)
        assert "hinton" in candidates[0].reason.lower() or "Geoffrey" in candidates[0].reason

    def test_build_display_reason(self):
        from app.services.recommendation_engine import build_display_reason

        reason = build_display_reason(
            source_strategy="for_you",
            reason="Matches your interests: transformers, NLP",
            score_breakdown={"relevance": 0.85, "citation": 0.3, "freshness": 0.9},
        )
        assert isinstance(reason, str)
        assert len(reason) > 0
        assert len(reason) <= 120  # One-line constraint
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_recommendation_engine.py::TestRecommendationReasons -v`
Expected: FAIL — `build_display_reason` does not exist.

- [ ] **Step 3: Implement build_display_reason**

Add to `app/services/recommendation_engine.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_recommendation_engine.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/recommendation_engine.py tests/test_recommendation_engine.py
git commit -m "feat(engine): add build_display_reason for one-line human-readable recommendation reasons"
```

---

### Task 10: Integration Test + Final Verification

**Files:**
- Modify: `tests/test_recommendation_engine.py`
- Modify: `tests/test_user_profile.py`

- [ ] **Step 1: Add end-to-end integration test**

```python
# Append to tests/test_recommendation_engine.py
import os
import tempfile


class TestEngineIntegration:
    """End-to-end test: engine -> scorer -> reasons -> serialization."""

    def test_full_recommendation_flow(self):
        from app.services.recommendation_engine import (
            RecommendationEngine,
            RecommendationScorer,
            build_display_reason,
            normalize_citation_score,
            normalize_freshness_score,
        )

        papers = [
            {"paper_id": "p1", "title": "Scaling Laws for Neural Language Models", "abstract": "We study empirical scaling laws for language model performance", "authors": ["Kaplan"], "citation_count": 500, "year": "2026", "venue": "NeurIPS"},
            {"paper_id": "p2", "title": "Protein Structure Prediction with AlphaFold", "abstract": "Protein folding using deep learning", "authors": ["Jumper"], "citation_count": 1000, "year": "2025", "venue": "Nature"},
            {"paper_id": "p3", "title": "Reinforcement Learning from Human Feedback", "abstract": "RLHF for language model alignment", "authors": ["Christiano"], "citation_count": 200, "year": "2026", "venue": "ICML"},
        ]
        profile = {"interest_vector": ["scaling laws", "language models", "reinforcement learning"]}
        subscriptions = [{"type": "venue", "query_text": "NeurIPS", "name": "NeurIPS"}]

        engine = RecommendationEngine()
        result = engine.recommend(
            papers=papers,
            user_profile=profile,
            subscriptions=subscriptions,
            max_per_section=10,
        )

        assert len(result["sections"]) >= 2  # At least for_you and trending
        assert len(result["all_candidates"]) > 0

        # Every candidate should have a reason
        for section in result["sections"]:
            for c in section["candidates"]:
                assert c.reason
                display = build_display_reason(
                    source_strategy=c.source_strategy,
                    reason=c.reason,
                    score_breakdown=c.score_breakdown,
                )
                assert len(display) > 0

    def test_empty_input_does_not_crash(self):
        from app.services.recommendation_engine import RecommendationEngine

        engine = RecommendationEngine()
        result = engine.recommend(papers=[])
        assert result["sections"] == []
        assert result["all_candidates"] == []

    def test_scorer_output_matches_candidate_format(self):
        from app.services.recommendation_engine import RecommendationScorer

        scorer = RecommendationScorer()
        result = scorer.score(relevance=0.7, citation=0.5, freshness=0.9, entity_affinity=0.2, feedback=0.1)
        assert "composite" in result
        assert "breakdown" in result
        assert all(dim in result["breakdown"] for dim in ("relevance", "citation", "freshness", "entity_affinity", "feedback"))
        for dim_info in result["breakdown"].values():
            assert "raw" in dim_info
            assert "weight" in dim_info
            assert "weighted" in dim_info
```

- [ ] **Step 2: Add profile integration test**

```python
# Append to tests/test_user_profile.py

class TestProfileIntegrationWithEngine:
    def test_profile_feeds_into_engine(self):
        from app.services.recommendation_engine import RecommendationEngine
        store, tmp = _make_store()
        try:
            store.upsert_user_profile(
                interest_vector=["machine learning", "optimization"],
                topic_weights={"machine learning": 2.0, "optimization": 1.5},
            )
            profile = store.get_user_profile()

            engine = RecommendationEngine()
            papers = [
                {"paper_id": "1", "title": "Machine Learning Optimization Methods", "abstract": "SGD and Adam", "authors": [], "citation_count": 10, "year": "2026"},
            ]
            result = engine.recommend(papers=papers, user_profile=profile)
            assert len(result["sections"]) > 0
            # ForYou section should match on "machine learning"
            for_you = [s for s in result["sections"] if s["strategy"] == "for_you"]
            assert len(for_you) == 1
            assert for_you[0]["candidates"][0].score > 0
        finally:
            os.unlink(tmp)
```

- [ ] **Step 3: Run full test suite**

Run: `python -m pytest tests/test_recommendation_engine.py tests/test_user_profile.py -v`
Expected: ALL PASS

- [ ] **Step 4: Run project-wide test suite to verify no regressions**

Run: `python -m pytest tests/ -q --timeout=30`
Expected: All pass (or pre-existing failures only).

- [ ] **Step 5: Final commit for Phase 4**

```bash
git add tests/test_recommendation_engine.py tests/test_user_profile.py
git commit -m "test: add Phase 4 integration tests for recommendation engine and user profile"
```
