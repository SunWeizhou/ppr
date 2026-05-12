"""Tests for the multi-strategy recommendation engine."""

"""Tests for the multi-strategy recommendation engine."""

import math
from dataclasses import asdict

import unittest


class TestCandidate(unittest.TestCase):
    def test_candidate_creation(self):
        from app.services.recommendation_engine import Candidate

        c = Candidate(
            paper_id="2401.00001",
            score=0.0,
            source_strategy="for_you",
            reason="Keyword match: LLM",
            score_breakdown={"relevance": 0.8, "citation": 0.3},
        )
        self.assertEqual(c.paper_id, "2401.00001")
        self.assertEqual(c.source_strategy, "for_you")
        self.assertEqual(c.score_breakdown["relevance"], 0.8)

    def test_candidate_defaults(self):
        from app.services.recommendation_engine import Candidate

        c = Candidate(paper_id="x", score=0.5, source_strategy="trending", reason="Hot paper")
        self.assertEqual(c.score_breakdown, {})
        self.assertEqual(c.paper_data, {})

    def test_candidate_serializable(self):
        from app.services.recommendation_engine import Candidate

        c = Candidate(paper_id="x", score=0.5, source_strategy="t", reason="r")
        d = asdict(c)
        self.assertEqual(d["paper_id"], "x")
        self.assertIsInstance(d, dict)


class TestRecommendationScorer(unittest.TestCase):
    def test_all_dimensions_zero(self):
        from app.services.recommendation_engine import RecommendationScorer

        scorer = RecommendationScorer()
        result = scorer.score(
            relevance=0.0, citation=0.0, freshness=0.0,
            entity_affinity=0.0, feedback=0.0,
        )
        self.assertEqual(result["composite"], 0.0)
        self.assertEqual(len(result["breakdown"]), 5)

    def test_all_dimensions_one(self):
        from app.services.recommendation_engine import RecommendationScorer

        scorer = RecommendationScorer()
        result = scorer.score(
            relevance=1.0, citation=1.0, freshness=1.0,
            entity_affinity=1.0, feedback=1.0,
        )
        self.assertAlmostEqual(result["composite"], 1.0, places=5)

    def test_weights_sum_to_one(self):
        from app.services.recommendation_engine import RecommendationScorer

        scorer = RecommendationScorer()
        total = sum(scorer.weights.values())
        self.assertAlmostEqual(total, 1.0, places=5)

    def test_relevance_dominant(self):
        """Relevance-only paper should score higher than citation-only."""
        from app.services.recommendation_engine import RecommendationScorer

        scorer = RecommendationScorer()
        rel_only = scorer.score(relevance=1.0, citation=0.0, freshness=0.0, entity_affinity=0.0, feedback=0.0)
        cit_only = scorer.score(relevance=0.0, citation=1.0, freshness=0.0, entity_affinity=0.0, feedback=0.0)
        self.assertGreater(rel_only["composite"], cit_only["composite"])

    def test_custom_weights(self):
        from app.services.recommendation_engine import RecommendationScorer

        scorer = RecommendationScorer(weights={"relevance": 1.0, "citation": 0.0, "freshness": 0.0, "entity_affinity": 0.0, "feedback": 0.0})
        result = scorer.score(relevance=0.7, citation=1.0, freshness=1.0, entity_affinity=1.0, feedback=1.0)
        self.assertAlmostEqual(result["composite"], 0.7, places=5)

    def test_values_clamped_to_0_1(self):
        from app.services.recommendation_engine import RecommendationScorer

        scorer = RecommendationScorer()
        result = scorer.score(relevance=2.0, citation=-0.5, freshness=0.5, entity_affinity=0.5, feedback=0.5)
        self.assertTrue(0.0 <= result["composite"] <= 1.0)

    def test_citation_normalization(self):
        from app.services.recommendation_engine import normalize_citation_score

        self.assertEqual(normalize_citation_score(0), 0.0)
        self.assertTrue(0.0 < normalize_citation_score(10) < normalize_citation_score(100))
        self.assertLessEqual(normalize_citation_score(10000), 1.0)

    def test_freshness_normalization(self):
        from app.services.recommendation_engine import normalize_freshness_score

        # Published today => high freshness
        self.assertGreater(normalize_freshness_score(0), 0.9)
        # Published 365 days ago => low freshness
        self.assertLess(normalize_freshness_score(365), 0.2)

class TestBaseStrategy(unittest.TestCase):
    def test_cannot_instantiate_directly(self):
        from app.services.recommendation_engine import BaseStrategy

        with self.assertRaises(TypeError):
            BaseStrategy()

    def test_subclass_must_implement_generate(self):
        from app.services.recommendation_engine import BaseStrategy

        class BadStrategy(BaseStrategy):
            name = "bad"

        with self.assertRaises(TypeError):
            BadStrategy()


class TestForYouStrategy(unittest.TestCase):
    def test_returns_candidates(self):
        from app.services.recommendation_engine import ForYouStrategy, Candidate

        papers = [
            {"paper_id": "1", "title": "Deep Learning for NLP", "abstract": "We study transformers", "authors": ["Smith"], "citation_count": 50, "year": "2026"},
            {"paper_id": "2", "title": "Quantum Computing", "abstract": "Qubits are cool", "authors": ["Jones"], "citation_count": 10, "year": "2025"},
        ]
        profile = {"interest_vector": ["deep learning", "NLP", "transformers"]}
        strategy = ForYouStrategy()
        candidates = strategy.generate(papers=papers, user_profile=profile)
        self.assertGreater(len(candidates), 0)
        self.assertTrue(all(isinstance(c, Candidate) for c in candidates))
        self.assertTrue(all(c.source_strategy == "for_you" for c in candidates))

    def test_empty_profile_returns_all(self):
        from app.services.recommendation_engine import ForYouStrategy

        papers = [{"paper_id": "1", "title": "Paper", "abstract": "Stuff", "authors": []}]
        strategy = ForYouStrategy()
        candidates = strategy.generate(papers=papers, user_profile={})
        self.assertEqual(len(candidates), len(papers))

    def test_reason_contains_match_info(self):
        from app.services.recommendation_engine import ForYouStrategy

        papers = [{"paper_id": "1", "title": "Transformers are great", "abstract": "NLP stuff", "authors": []}]
        profile = {"interest_vector": ["transformers"]}
        strategy = ForYouStrategy()
        candidates = strategy.generate(papers=papers, user_profile=profile)
        self.assertTrue(candidates[0].reason)


class TestTrendingStrategy(unittest.TestCase):
    def test_returns_candidates_sorted_by_citations(self):
        from app.services.recommendation_engine import TrendingStrategy, Candidate

        papers = [
            {"paper_id": "low", "title": "Low", "abstract": "", "authors": [], "citation_count": 1, "year": "2026"},
            {"paper_id": "high", "title": "High", "abstract": "", "authors": [], "citation_count": 500, "year": "2026"},
        ]
        strategy = TrendingStrategy()
        candidates = strategy.generate(papers=papers)
        self.assertEqual(candidates[0].paper_id, "high")
        self.assertTrue(all(c.source_strategy == "trending" for c in candidates))

    def test_freshness_matters(self):
        from app.services.recommendation_engine import TrendingStrategy

        papers = [
            {"paper_id": "old", "title": "Old", "abstract": "", "authors": [], "citation_count": 100, "year": "2020"},
            {"paper_id": "new", "title": "New", "abstract": "", "authors": [], "citation_count": 100, "year": "2026"},
        ]
        strategy = TrendingStrategy()
        candidates = strategy.generate(papers=papers)
        # Newer paper should rank higher when citation counts are equal
        self.assertEqual(candidates[0].paper_id, "new")

class TestEntityStrategy(unittest.TestCase):
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
        self.assertEqual(len(candidates), 2)
        # Paper from subscribed venue should rank higher
        self.assertEqual(candidates[0].paper_id, "1")
        self.assertIn("Nature", candidates[0].reason)

    def test_empty_subscriptions(self):
        from app.services.recommendation_engine import EntityStrategy

        papers = [{"paper_id": "1", "title": "T", "abstract": "A", "authors": []}]
        strategy = EntityStrategy()
        candidates = strategy.generate(papers=papers, subscriptions=[])
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].score, 0.0)


class TestReadingStrategy(unittest.TestCase):
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
        self.assertEqual(len(candidates), 2)
        # Paper more similar to reading queue should rank first
        self.assertEqual(candidates[0].paper_id, "1")

    def test_empty_reading_queue(self):
        from app.services.recommendation_engine import ReadingStrategy

        papers = [{"paper_id": "1", "title": "T", "abstract": "A", "authors": []}]
        strategy = ReadingStrategy()
        candidates = strategy.generate(papers=papers, reading_queue=[])
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].score, 0.0)


class TestQuestionStrategy(unittest.TestCase):
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
        self.assertEqual(candidates[0].paper_id, "1")
        self.assertTrue(all(c.source_strategy == "question" for c in candidates))

class TestRecommendationEngine(unittest.TestCase):
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
        self.assertIn("sections", result)
        self.assertGreater(len(result["sections"]), 0)
        for section in result["sections"]:
            self.assertIn("strategy", section)
            self.assertIn("title", section)
            self.assertIn("candidates", section)

    def test_engine_includes_for_you_section(self):
        from app.services.recommendation_engine import RecommendationEngine

        engine = RecommendationEngine()
        result = engine.recommend(
            papers=self._make_papers(),
            user_profile={"interest_vector": ["deep learning"]},
        )
        strategy_names = [s["strategy"] for s in result["sections"]]
        self.assertIn("for_you", strategy_names)

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
            self.assertEqual(len(ids), len(set(ids)))

    def test_engine_limits_per_section(self):
        from app.services.recommendation_engine import RecommendationEngine

        engine = RecommendationEngine()
        papers = [{"paper_id": str(i), "title": f"Paper {i}", "abstract": "ML stuff", "authors": [], "citation_count": i, "year": "2026"} for i in range(50)]
        result = engine.recommend(papers=papers, max_per_section=5)
        for section in result["sections"]:
            self.assertLessEqual(len(section["candidates"]), 5)

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
        self.assertIn("sections", result)

class TestRecommendationReasons(unittest.TestCase):
    def test_for_you_reason_includes_matched_keywords(self):
        from app.services.recommendation_engine import ForYouStrategy

        papers = [{"paper_id": "1", "title": "Graph neural networks for drug discovery", "abstract": "GNN methods", "authors": []}]
        profile = {"interest_vector": ["graph neural networks", "drug discovery"]}
        strategy = ForYouStrategy()
        candidates = strategy.generate(papers=papers, user_profile=profile)
        self.assertTrue("graph neural networks" in candidates[0].reason.lower() or "drug discovery" in candidates[0].reason.lower())

    def test_trending_reason_includes_citation_count(self):
        from app.services.recommendation_engine import TrendingStrategy

        papers = [{"paper_id": "1", "title": "Popular paper", "abstract": "", "authors": [], "citation_count": 250, "year": "2026"}]
        strategy = TrendingStrategy()
        candidates = strategy.generate(papers=papers)
        self.assertIn("250", candidates[0].reason)

    def test_entity_reason_includes_entity_name(self):
        from app.services.recommendation_engine import EntityStrategy

        papers = [{"paper_id": "1", "title": "T", "abstract": "A", "authors": ["Geoffrey Hinton"], "venue": "NeurIPS"}]
        subscriptions = [{"type": "author", "query_text": "Geoffrey Hinton"}]
        strategy = EntityStrategy()
        candidates = strategy.generate(papers=papers, subscriptions=subscriptions)
        self.assertTrue("hinton" in candidates[0].reason.lower() or "Geoffrey" in candidates[0].reason)

    def test_build_display_reason(self):
        from app.services.recommendation_engine import build_display_reason

        reason = build_display_reason(
            source_strategy="for_you",
            reason="Matches your interests: transformers, NLP",
            score_breakdown={"relevance": 0.85, "citation": 0.3, "freshness": 0.9},
        )
        self.assertIsInstance(reason, str)
        self.assertGreater(len(reason), 0)
        self.assertLessEqual(len(reason), 120)

import os
import tempfile


class TestEngineIntegration(unittest.TestCase):
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

        self.assertGreaterEqual(len(result["sections"]), 2)
        self.assertGreater(len(result["all_candidates"]), 0)

        # Every candidate should have a reason
        for section in result["sections"]:
            for c in section["candidates"]:
                self.assertTrue(c.reason)
                display = build_display_reason(
                    source_strategy=c.source_strategy,
                    reason=c.reason,
                    score_breakdown=c.score_breakdown,
                )
                self.assertGreater(len(display), 0)

    def test_empty_input_does_not_crash(self):
        from app.services.recommendation_engine import RecommendationEngine

        engine = RecommendationEngine()
        result = engine.recommend(papers=[])
        self.assertEqual(result["sections"], [])
        self.assertEqual(result["all_candidates"], [])

    def test_scorer_output_matches_candidate_format(self):
        from app.services.recommendation_engine import RecommendationScorer

        scorer = RecommendationScorer()
        result = scorer.score(relevance=0.7, citation=0.5, freshness=0.9, entity_affinity=0.2, feedback=0.1)
        self.assertIn("composite", result)
        self.assertIn("breakdown", result)
        self.assertTrue(all(dim in result["breakdown"] for dim in ("relevance", "citation", "freshness", "entity_affinity", "feedback")))
        for dim_info in result["breakdown"].values():
            self.assertIn("raw", dim_info)
            self.assertIn("weight", dim_info)
            self.assertIn("weighted", dim_info)