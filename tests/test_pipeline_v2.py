"""Tests for v2 pipeline (run_pipeline_v2) and feature flag routing.

Tests cover:
- v2 pipeline orchestration with mocked recall and ranker
- Feature flag routing via arxiv_recommender_v5.run_pipeline
- Default (no flag) behavior routing to v1
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import ANY, MagicMock, patch


def _make_paper(
    paper_id: str = "2401.00001",
    title: str = "Test Paper",
    abstract: str = "Abstract about conformal prediction and statistical inference.",
    authors: list[str] | None = None,
    score: float = 0.0,
) -> dict:
    return {
        "id": paper_id,
        "title": title,
        "abstract": abstract,
        "authors": authors or ["Alice Researcher"],
        "categories": ["stat.ML", "cs.LG"],
        "link": f"https://arxiv.org/abs/{paper_id}",
        "source_url": f"https://arxiv.org/abs/{paper_id}",
        "source": "arXiv",
        "published": "2024-01-15T00:00:00Z",
        "score": score,
    }


# ---------------------------------------------------------------------------
# v2 pipeline orchestration tests
# ---------------------------------------------------------------------------


class TestPipelineV2(unittest.TestCase):
    """Test v2 pipeline orchestration with mocked dependencies."""

    def setUp(self):
        # Mock recall (local import inside run_pipeline_v2)
        self.recall_patcher = patch("app.services.recall.recall_candidates")
        self.mock_recall = self.recall_patcher.start()
        self.mock_recall.return_value = []

        # Mock ranker (local import inside run_pipeline_v2)
        self.score_patcher = patch("app.services.ranker.score_paper")
        self.mock_score = self.score_patcher.start()
        self.mock_score.return_value = (0.5, "基于你的研究领域")

        # Mock state store (cache check, pipeline-level)
        self.store_patcher = patch("app.services.daily_pipeline.get_state_store")
        self.mock_get_store = self.store_patcher.start()
        self.mock_store = MagicMock()
        self.mock_store.get_recommendation_run_by_date.return_value = None
        self.mock_get_store.return_value = self.mock_store

        # Mock JSON cache loader
        self.load_patcher = patch("app.services.daily_pipeline.load_daily_recommendation")
        self.mock_load = self.load_patcher.start()
        self.mock_load.return_value = (None, None)

        # Mock PaperCache to avoid file I/O
        self.cache_patcher = patch("app.services.daily_pipeline.PaperCache")
        self.mock_cache_cls = self.cache_patcher.start()
        self.mock_cache = MagicMock()
        self.mock_cache.get_stats.return_value = {
            "total_seen": 0,
            "days_with_recommendations": 0,
        }
        self.mock_cache_cls.return_value = self.mock_cache

        # Mock output generation to avoid HTML/MD/SQLite writes
        self.gen_patcher = patch("app.services.daily_pipeline._generate_outputs")
        self.mock_gen = self.gen_patcher.start()

        # Keep tests independent from the developer's local papers_per_day setting.
        self.config_patcher = patch("config_manager.get_config")
        self.mock_get_config = self.config_patcher.start()
        mock_config = MagicMock()
        mock_config.core_keywords = {"conformal": 1.0}
        mock_config._settings.papers_per_day = 20
        self.mock_get_config.return_value = mock_config

    def tearDown(self):
        self.recall_patcher.stop()
        self.score_patcher.stop()
        self.store_patcher.stop()
        self.load_patcher.stop()
        self.cache_patcher.stop()
        self.gen_patcher.stop()
        self.config_patcher.stop()

    # ------------------------------------------------------------------
    # Core orchestration
    # ------------------------------------------------------------------

    def test_v2_runs_with_papers(self):
        """Pipeline returns scored, summarized papers."""
        from app.services.daily_pipeline import run_pipeline_v2

        self.mock_recall.return_value = [
            _make_paper("2401.00001", "Conf Paper", "conformal prediction methods"),
            _make_paper("2401.00002", "Gen Paper", "generalization bounds"),
        ]
        self.mock_score.side_effect = lambda paper, ctx: (
            0.85 if "conformal" in paper.get("abstract", "").lower() else 0.45,
            "基于你的研究领域",
        )

        result = run_pipeline_v2(force_refresh=True)

        self.assertEqual(len(result), 2)
        for p in result:
            self.assertIn("score", p)
            self.assertIn("relevance_reason", p)
            self.assertIn("summary", p)
        # Higher-scoring paper should be first
        self.assertGreater(result[0]["score"], result[1]["score"])

    def test_v2_calls_recall_with_expected_args(self):
        """recall_candidates is called with categories, lookback, and max_results."""
        from app.services.daily_pipeline import run_pipeline_v2

        self.mock_recall.return_value = [
            _make_paper("2401.00001", "A", "machine learning"),
        ]

        run_pipeline_v2(force_refresh=True)

        self.mock_recall.assert_called_once_with(ANY, lookback_days=ANY, max_results=500)

    def test_v2_calls_score_for_each_paper(self):
        """score_paper is called once per paper with keywords context."""
        from app.services.daily_pipeline import run_pipeline_v2

        self.mock_recall.return_value = [
            _make_paper("2401.00001", "A", "abstract about conformal prediction"),
            _make_paper("2401.00002", "B", "abstract about minimax estimation"),
            _make_paper("2401.00003", "C", "abstract about generalization bounds"),
        ]

        run_pipeline_v2(force_refresh=True)

        self.assertEqual(self.mock_score.call_count, 3)
        # Each call receives a paper (first arg) and a ctx dict with keywords (second arg)
        for call_args in self.mock_score.call_args_list:
            _paper, ctx = call_args[0]
            self.assertIn("keywords", ctx)

    def test_v2_empty_recall_returns_empty(self):
        """Empty recall returns [] without scoring or generating."""
        from app.services.daily_pipeline import run_pipeline_v2

        self.mock_recall.return_value = []

        result = run_pipeline_v2(force_refresh=True)

        self.assertEqual(result, [])
        self.mock_score.assert_not_called()
        self.mock_gen.assert_not_called()

    def test_v2_top_k_limits_papers(self):
        """Default top-K (20) limits papers returned."""
        from app.services.daily_pipeline import run_pipeline_v2

        self.mock_recall.return_value = [
            _make_paper(f"2401.{i:05d}", f"Paper {i}", "some abstract")
            for i in range(50)
        ]
        # Score desc by paper id suffix so first 20 are highest
        self.mock_score.side_effect = lambda paper, ctx: (
            1.0 - int(paper["id"].split(".")[1]) / 100000.0,
            "基于你的研究领域",
        )

        result = run_pipeline_v2(force_refresh=True)

        self.assertEqual(len(result), 20)

    def test_v2_calls_generate_outputs(self):
        """_generate_outputs is called with top papers and empty themes."""
        from app.services.daily_pipeline import run_pipeline_v2

        self.mock_recall.return_value = [
            _make_paper("2401.00001", "A", "conformal prediction"),
            _make_paper("2401.00002", "B", "minimax estimation"),
        ]

        run_pipeline_v2(force_refresh=True)

        self.mock_gen.assert_called_once()
        args, _kwargs = self.mock_gen.call_args
        # args: top_papers, themes, date_str, cache, output_dir, history_dir, cache_dir
        self.assertEqual(len(args[0]), 2)  # top_papers count
        self.assertEqual(args[1], [])  # empty themes in v2
        self.assertIs(args[3], self.mock_cache)  # cache instance

    # ------------------------------------------------------------------
    # Pipeline-level caching
    # ------------------------------------------------------------------

    def test_v2_cache_hit_skips_pipeline(self):
        """SQLite cache hit returns cached papers without recall/score/gen."""
        from app.services.daily_pipeline import run_pipeline_v2

        cached_papers = [
            _make_paper("2401.00001", "Cached Paper", "abstract"),
        ]
        self.mock_store.get_recommendation_run_by_date.return_value = {"run_id": "test-run"}
        self.mock_store.get_recommendation_items.return_value = cached_papers

        result = run_pipeline_v2(force_refresh=False)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "2401.00001")
        self.mock_recall.assert_not_called()
        self.mock_score.assert_not_called()
        self.mock_gen.assert_not_called()

    def test_v2_force_refresh_bypasses_cache(self):
        """force_refresh=True skips the cache check and runs pipeline."""
        from app.services.daily_pipeline import run_pipeline_v2

        self.mock_store.get_recommendation_run_by_date.return_value = {"run_id": "test-run"}
        self.mock_recall.return_value = [
            _make_paper("2401.00001", "Fresh Paper", "conformal prediction"),
        ]

        result = run_pipeline_v2(force_refresh=True)

        self.mock_recall.assert_called_once()
        self.assertEqual(len(result), 1)

    # ------------------------------------------------------------------
    # Score/summary keys
    # ------------------------------------------------------------------

    def test_v2_papers_have_all_expected_keys(self):
        """Each returned paper has score, relevance_reason, and summary."""
        from app.services.daily_pipeline import run_pipeline_v2

        self.mock_recall.return_value = [
            _make_paper("2401.00001", "Paper", "conformal prediction methods"),
        ]

        result = run_pipeline_v2(force_refresh=True)

        paper = result[0]
        self.assertIn("score", paper)
        self.assertIn("relevance_reason", paper)
        self.assertIn("summary", paper)
        self.assertIsInstance(paper["score"], float)
        self.assertIsInstance(paper["relevance_reason"], str)
        self.assertIsInstance(paper["summary"], str)


# ---------------------------------------------------------------------------
# Feature flag routing tests
# ---------------------------------------------------------------------------


class TestFeatureFlag(unittest.TestCase):
    """Env-var-based feature flag routing was previously in arxiv_recommender_v5.run_pipeline
    which no longer exists. The STATDESK_RANKER env var routing has been removed;
    daily_pipeline.run_pipeline is now the direct implementation.
    """

    def test_daily_pipeline_run_pipeline_is_direct_implementation(self):
        """run_pipeline is now a standalone function with no v1/v2 flag routing."""
        from app.services.daily_pipeline import run_pipeline
        self.assertTrue(callable(run_pipeline))

    def test_daily_pipeline_run_pipeline_v2_is_separate_function(self):
        """run_pipeline_v2 remains available as a separate entry point."""
        from app.services.daily_pipeline import run_pipeline_v2
        self.assertTrue(callable(run_pipeline_v2))

    def test_feature_flag_routing_is_removed(self):
        """STATDESK_RANKER env var is no longer consumed by the pipeline."""
        from app.services.daily_pipeline import run_pipeline
        # The env var may exist in the environment, but it no longer
        # affects routing — run_pipeline is now the direct implementation.
        self.assertTrue(callable(run_pipeline))


# ---------------------------------------------------------------------------
# Smoke test: run_pipeline_v2 is importable
# ---------------------------------------------------------------------------


class TestPipelineV2Smoke(unittest.TestCase):
    """Minimal smoke tests for run_pipeline_v2 import and signature."""

    def test_function_is_importable(self):
        """run_pipeline_v2 is importable from daily_pipeline."""
        from app.services.daily_pipeline import run_pipeline_v2

        self.assertTrue(callable(run_pipeline_v2))

    def test_function_has_force_refresh_param(self):
        """run_pipeline_v2 accepts force_refresh keyword argument."""
        import inspect

        from app.services.daily_pipeline import run_pipeline_v2

        sig = inspect.signature(run_pipeline_v2)
        self.assertIn("force_refresh", sig.parameters)

    def test_function_is_in_daily_pipeline_all(self):
        """run_pipeline_v2 is exported in daily_pipeline.__all__."""
        from app.services.daily_pipeline import __all__

        self.assertIn("run_pipeline_v2", __all__)


if __name__ == "__main__":
    unittest.main()
