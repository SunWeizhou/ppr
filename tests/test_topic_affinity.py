"""Unit tests for user_topic_affinity table and scoring integration."""

import tempfile
import unittest
from pathlib import Path


class TopicAffinityTests(unittest.TestCase):
    def setUp(self):
        from state_store import StateStore

        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tmp_dir.name) / "test_state.db")
        self.store = StateStore(self.db_path)

    def tearDown(self):
        self.tmp_dir.cleanup()

    # ------------------------------------------------------------------
    # Table existence
    # ------------------------------------------------------------------

    def test_affinity_table_exists(self):
        """Verify the user_topic_affinity table is created on init."""
        from state_store import StateStore

        with self.store._connect() as conn:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='user_topic_affinity'"
            ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["name"], "user_topic_affinity")

    # ------------------------------------------------------------------
    # CRUD operations
    # ------------------------------------------------------------------

    def test_upsert_and_read_affinity(self):
        """Insert a topic, read it back."""
        # Insert
        result = self.store.upsert_user_topic_affinity("ML", 5.0, 1.0)
        self.assertTrue(result)

        # Read back
        affinities = self.store.get_user_topic_affinities()
        self.assertEqual(len(affinities), 1)
        aff = affinities[0]
        self.assertEqual(aff["topic"], "ML")
        self.assertAlmostEqual(aff["positive_score"], 5.0)
        self.assertAlmostEqual(aff["negative_score"], 1.0)
        self.assertGreaterEqual(aff["source_event_count"], 1)
        self.assertIsNotNone(aff["updated_at"])

    def test_multiple_affinities(self):
        """Multiple topics are sorted by positive_score DESC."""
        self.store.upsert_user_topic_affinity("NLP", 3.0, 0.0)
        self.store.upsert_user_topic_affinity("ML", 8.0, 0.5)
        self.store.upsert_user_topic_affinity("Vision", 1.0, 2.0)

        affinities = self.store.get_user_topic_affinities()
        self.assertEqual(len(affinities), 3)
        self.assertEqual(affinities[0]["topic"], "ML")
        self.assertEqual(affinities[1]["topic"], "NLP")
        self.assertEqual(affinities[2]["topic"], "Vision")

    # ------------------------------------------------------------------
    # Event integration
    # ------------------------------------------------------------------

    def _save_test_recommendation_run(self, paper_id="2604.11111",
                                      categories=None):
        """Helper: save a recommendation run with a test paper."""
        categories = categories or ["cs.LG"]
        papers = [
            {
                "id": paper_id,
                "title": "Test Paper",
                "score": 5.0,
                "authors": ["Author A"],
                "abstract": "Test abstract for topic affinity.",
                "categories": categories,
                "score_details": {"relevance": 4.0},
                "source": "arxiv",
            }
        ]
        self.store.save_recommendation_run("2026-04-27", "topic_test", papers)

    def test_event_updates_affinity(self):
        """Record a like event, verify affinity updated for paper categories."""
        self._save_test_recommendation_run()

        # Record a like event
        event_id = self.store.record_event("like", "2604.11111")
        self.assertGreater(event_id, 0)

        # Verify affinity was created for mapped category names
        affinities = self.store.get_user_topic_affinities()
        # cs.LG -> "ML", categories: ["cs.LG"]
        ml_topics = [a for a in affinities if a["topic"] == "ML"]
        self.assertEqual(len(ml_topics), 1)
        ml_aff = ml_topics[0]
        self.assertAlmostEqual(ml_aff["positive_score"], 1.0)
        self.assertAlmostEqual(ml_aff["negative_score"], 0.0)
        self.assertGreaterEqual(ml_aff["source_event_count"], 1)

    def test_dislike_creates_negative_affinity(self):
        """Record a dislike event, verify negative score."""
        self._save_test_recommendation_run()

        self.store.record_event("dislike", "2604.11111")

        affinities = self.store.get_user_topic_affinities()
        ml_topics = [a for a in affinities if a["topic"] == "ML"]
        self.assertEqual(len(ml_topics), 1)
        ml_aff = ml_topics[0]
        self.assertAlmostEqual(ml_aff["positive_score"], 0.0)
        self.assertAlmostEqual(ml_aff["negative_score"], 1.0)

    def test_ignore_reduces_affinity(self):
        """Record an ignore event, verify negative score."""
        self._save_test_recommendation_run()

        self.store.record_event("ignore_topic", "2604.11111",
                                {"topic": "machine learning"})

        affinities = self.store.get_user_topic_affinities()
        ml_topics = [a for a in affinities if a["topic"] == "ML"]
        self.assertEqual(len(ml_topics), 1)
        ml_aff = ml_topics[0]
        self.assertAlmostEqual(ml_aff["positive_score"], 0.0)
        self.assertAlmostEqual(ml_aff["negative_score"], 1.0)

    def test_ignore_skipped_if_also_liked(self):
        """Ignore event does NOT reduce affinity if paper was also liked."""
        self._save_test_recommendation_run()

        # Like first
        self.store.record_event("like", "2604.11111")
        # Then ignore
        self.store.record_event("ignore_topic", "2604.11111",
                                {"topic": "machine learning"})

        # Negative score should remain 0 because paper was also liked
        affinities = self.store.get_user_topic_affinities()
        ml_topics = [a for a in affinities if a["topic"] == "ML"]
        self.assertEqual(len(ml_topics), 1)
        ml_aff = ml_topics[0]
        self.assertAlmostEqual(ml_aff["positive_score"], 1.0)
        self.assertAlmostEqual(ml_aff["negative_score"], 0.0)

    def test_queue_status_deep_read_creates_affinity(self):
        """Deep Read queue status creates positive affinity."""
        self._save_test_recommendation_run()

        self.store.record_event("queue_status_changed", "2604.11111",
                                {"status": "Deep Read"})

        affinities = self.store.get_user_topic_affinities()
        ml_topics = [a for a in affinities if a["topic"] == "ML"]
        self.assertEqual(len(ml_topics), 1)
        self.assertAlmostEqual(ml_topics[0]["positive_score"], 2.0)

    def test_queue_status_skim_later_creates_affinity(self):
        """Skim Later queue status creates moderate positive affinity."""
        self._save_test_recommendation_run()

        self.store.record_event("queue_status_changed", "2604.11111",
                                {"status": "Skim Later"})

        affinities = self.store.get_user_topic_affinities()
        ml_topics = [a for a in affinities if a["topic"] == "ML"]
        self.assertEqual(len(ml_topics), 1)
        self.assertAlmostEqual(ml_topics[0]["positive_score"], 1.5)

    def test_multiple_categories_all_updated(self):
        """Event updates affinity for each paper category."""
        self._save_test_recommendation_run(
            categories=["cs.LG", "stat.ML", "math.PR"]
        )

        self.store.record_event("like", "2604.11111")

        affinities = self.store.get_user_topic_affinities()
        topics = {a["topic"] for a in affinities}
        self.assertIn("ML", topics)
        self.assertIn("Stat ML", topics)
        self.assertIn("Probability", topics)
        for aff in affinities:
            self.assertAlmostEqual(aff["positive_score"], 1.0)
            self.assertAlmostEqual(aff["negative_score"], 0.0)

    def test_empty_paper_id_skips_affinity(self):
        """Recording an event with empty paper_id should not fail."""
        event_id = self.store.record_event("like", "")
        self.assertGreater(event_id, 0)
        # Should not crash and no affinities should be created
        affinities = self.store.get_user_topic_affinities()
        self.assertEqual(len(affinities), 0)

    def test_nonexistent_paper_skips_affinity(self):
        """Recording an event for a paper not in recommendation_items."""
        event_id = self.store.record_event("like", "9999.99999")
        self.assertGreater(event_id, 0)
        # Paper not in recommendation_items, so no affinities
        affinities = self.store.get_user_topic_affinities()
        self.assertEqual(len(affinities), 0)

    # ------------------------------------------------------------------
    # Scorer integration
    # ------------------------------------------------------------------

    def test_score_with_matching_affinity(self):
        """Verify EnhancedScorer._apply_topic_affinity_score returns bonus."""
        from app.services.scoring_service import EnhancedScorer

        affinities = [
            {"topic": "ML", "positive_score": 5.0, "negative_score": 0.0,
             "source_event_count": 3},
            {"topic": "Vision", "positive_score": 0.0, "negative_score": 2.0,
             "source_event_count": 2},
        ]

        scorer = EnhancedScorer(None, use_semantic=False)

        # Paper with matching category
        paper_ml = {
            "id": "2604.33333",
            "title": "ML Paper",
            "abstract": "About machine learning",
            "categories": ["cs.LG"],
        }
        bonus = scorer._apply_topic_affinity_score(paper_ml, affinities)
        self.assertGreater(bonus, 0)
        self.assertLessEqual(bonus, 2.0)

        # Paper with no matching category
        paper_other = {
            "id": "2604.44444",
            "title": "Other Paper",
            "abstract": "About something else",
            "categories": ["math.PR"],
        }
        bonus2 = scorer._apply_topic_affinity_score(paper_other, affinities)
        self.assertEqual(bonus2, 0)

    def test_score_with_empty_affinities(self):
        """Verify scorer returns 0 bonus when affinities list is empty."""
        from app.services.scoring_service import EnhancedScorer

        scorer = EnhancedScorer(None, use_semantic=False)
        paper = {
            "id": "2604.55555",
            "title": "Any Paper",
            "abstract": "Some abstract",
            "categories": ["cs.LG"],
        }
        bonus = scorer._apply_topic_affinity_score(paper, [])
        self.assertEqual(bonus, 0)

    def test_score_with_no_categories(self):
        """Verify scorer returns 0 bonus when paper has no categories."""
        from app.services.scoring_service import EnhancedScorer

        affinities = [
            {"topic": "ML", "positive_score": 5.0, "negative_score": 0.0,
             "source_event_count": 3},
        ]
        scorer = EnhancedScorer(None, use_semantic=False)
        paper = {
            "id": "2604.66666",
            "title": "No Cat Paper",
            "abstract": "No categories here",
            "categories": [],
        }
        bonus = scorer._apply_topic_affinity_score(paper, affinities)
        self.assertEqual(bonus, 0)

    def test_score_bonus_capped_at_2(self):
        """Verify topic affinity score bonus is capped at 2.0."""
        from app.services.scoring_service import EnhancedScorer

        # Very high positive score
        affinities = [
            {"topic": "ML", "positive_score": 100.0, "negative_score": 0.0,
             "source_event_count": 50},
        ]
        scorer = EnhancedScorer(None, use_semantic=False)
        paper = {
            "id": "2604.77777",
            "title": "ML Paper",
            "abstract": "About ML",
            "categories": ["cs.LG"],
        }
        bonus = scorer._apply_topic_affinity_score(paper, affinities)
        self.assertLessEqual(bonus, 2.0)

    def test_compute_score_integrates_affinity_from_store(self):
        """Verify compute_score picks up affinities from state store."""
        import state_store as _st_mod

        # Ensure singleton is None so get_state_store() returns our test store
        _st_mod._state_store = None

        # Set up the state store singleton to our test store
        _st_mod._state_store = self.store

        # Add an affinity via the proper method
        self.store.upsert_user_topic_affinity("ML", 5.0, 0.0)

        from app.services.scoring_service import EnhancedScorer

        scorer = EnhancedScorer(None, use_semantic=False)

        paper = {
            "id": "2604.33333",
            "title": "ML Paper for Integration",
            "abstract": "A paper about machine learning topics.",
            "categories": ["cs.LG"],
        }

        score, details = scorer.compute_score(paper)
        # Score should be positive (relevance from defaults + affinity bonus)
        self.assertGreater(score, 0)

        # Clean up singleton so other tests are not affected
        _st_mod._state_store = None


if __name__ == "__main__":
    unittest.main()
