import importlib
import json
import tempfile
import unittest
from pathlib import Path


class LocalProductizationTests(unittest.TestCase):
    def setUp(self):
        import sys

        import config_manager

        self._original_config_file = config_manager.CONFIG_FILE
        self._original_config_instance = config_manager.ConfigManager._instance
        self._original_arxiv_v5 = sys.modules.get("arxiv_recommender_v5")

    def tearDown(self):
        import sys

        import config_manager

        config_manager.CONFIG_FILE = self._original_config_file
        config_manager.ConfigManager._instance = None
        config_manager.get_config()
        if self._original_arxiv_v5 is not None:
            sys.modules["arxiv_recommender_v5"] = self._original_arxiv_v5
            import arxiv_recommender_v5

            importlib.reload(arxiv_recommender_v5)
            import app.services.scoring_service

            importlib.reload(app.services.scoring_service)

    def _reset_config_manager(self, config_path: Path):
        import config_manager

        config_manager = importlib.reload(config_manager)
        config_manager.CONFIG_FILE = config_path
        config_manager.ConfigManager._instance = None
        return config_manager

    def test_config_manager_migrates_legacy_keywords_when_profile_has_no_positive_topics(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = root / "user_profile.json"
            profile.write_text(
                json.dumps(
                    {
                        "version": 2,
                        "keywords": {
                            "federated learning": {"weight": -1.0, "category": "dislike"}
                        },
                        "theory_keywords": [],
                        "settings": {},
                        "sources": {},
                        "zotero": {},
                        "venue_priority": {},
                    }
                ),
                encoding="utf-8",
            )
            (root / "keywords_config.json").write_text(
                json.dumps(
                    {
                        "core_topics": {"conformal prediction": 5.0},
                        "secondary_topics": {"optimal rate": 3.0},
                        "theory_keywords": ["theorem"],
                        "demote_topics": {"benchmark": -1.0},
                        "dislike_topics": {"federated learning": -1.0},
                    }
                ),
                encoding="utf-8",
            )

            config_manager = self._reset_config_manager(profile)
            config = config_manager.ConfigManager()

            self.assertEqual(config.core_keywords["conformal prediction"], 5.0)
            self.assertEqual(config.get_keywords_by_category("secondary")["optimal rate"], 3.0)
            self.assertIn("theorem", config.theory_keywords)
            self.assertIn("benchmark", config.demote_keywords)

    def test_scorer_uses_configured_theory_keywords(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile = Path(tmp) / "user_profile.json"
            profile.write_text(
                json.dumps(
                    {
                        "version": 2,
                        "keywords": {},
                        "theory_keywords": ["lyapunov"],
                        "settings": {"theory_enabled": True},
                    }
                ),
                encoding="utf-8",
            )
            self._reset_config_manager(profile)

            import arxiv_recommender_v5

            importlib.reload(arxiv_recommender_v5)
            scorer = arxiv_recommender_v5.EnhancedScorer(None, use_semantic=False)
            score, details = scorer.compute_score(
                {
                    "id": "2604.12345v2",
                    "title": "Lyapunov Analysis for Stable Learning",
                    "abstract": "A short abstract.",
                    "authors": [],
                    "categories": [],
                }
            )

            self.assertGreater(score, 0)
            self.assertTrue(
                any(reason.get("type") == "theory" for reason in details["breakdown"])
            )

    def test_arxiv_identity_normalizes_versioned_ids(self):
        import arxiv_recommender_v5

        identity = arxiv_recommender_v5.parse_arxiv_identity("https://arxiv.org/abs/2604.12345v2")

        self.assertEqual(identity["base_id"], "2604.12345")
        self.assertEqual(identity["version"], "v2")
        self.assertEqual(identity["canonical_id"], "2604.12345")
        self.assertEqual(identity["source_url"], "https://arxiv.org/abs/2604.12345v2")

    def test_feedback_learner_uses_historical_cached_papers(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp)
            (cache_dir / "user_feedback.json").write_text(
                json.dumps({"liked": ["2604.11111v1"], "disliked": ["2604.22222v1"]}),
                encoding="utf-8",
            )
            run_dir = cache_dir / "recommendation_runs"
            run_dir.mkdir()
            (run_dir / "2026-04-22.json").write_text(
                json.dumps(
                    {
                        "papers": [
                            {
                                "id": "2604.11111v1",
                                "title": "Conformal Prediction with Guarantees",
                                "abstract": "conformal prediction theorem",
                            },
                            {
                                "id": "2604.22222v1",
                                "title": "Federated Learning Benchmark",
                                "abstract": "benchmark federated learning",
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )

            import arxiv_recommender_v5

            learner = arxiv_recommender_v5.FeedbackLearner(
                str(cache_dir / "user_feedback.json"), str(cache_dir)
            )
            result = learner.learn_from_feedback(min_feedback=1)

            self.assertEqual(result["status"], "learned")
            self.assertIn("conformal prediction", result["liked_topics"])
            self.assertIn("federated learning", result["disliked_topics"])

    def test_state_store_rejects_missing_collection_parent(self):
        from state_store import StateStore

        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(str(Path(tmp) / "state.db"))

            self.assertFalse(store.add_paper_to_collection(999, "2604.12345"))


if __name__ == "__main__":
    unittest.main()
