"""Unit tests for SQLite-backed recommendation run storage."""

import tempfile
import unittest
from pathlib import Path


class SqliteRecommendationTests(unittest.TestCase):
    def setUp(self):
        from state_store import StateStore

        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tmp_dir.name) / "test_state.db")
        self.store = StateStore(self.db_path)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_save_and_retrieve_recommendation_run(self):
        papers = [
            {
                "id": "2604.11111",
                "title": "First Paper",
                "score": 5.0,
                "authors": ["Author A"],
                "abstract": "Abstract 1",
                "categories": ["cs.LG"],
                "score_details": {"relevance": 4.0},
                "source": "arxiv",
            },
            {
                "id": "2604.22222",
                "title": "Second Paper",
                "score": 3.0,
                "authors": ["Author B"],
                "abstract": "Abstract 2",
                "categories": ["stat.ML"],
                "score_details": {"semantic": 2.0},
                "source": "arxiv",
            },
        ]
        run_id = self.store.save_recommendation_run("2026-04-26", "manual_test", papers)
        self.assertIsNotNone(run_id)
        self.assertIsInstance(run_id, str)
        self.assertTrue(len(run_id) > 0)

        items = self.store.get_recommendation_items(run_id)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["paper_id"], "2604.11111")
        self.assertEqual(items[0]["rank"], 1)
        self.assertAlmostEqual(items[0]["score"], 5.0)
        self.assertEqual(items[1]["paper_id"], "2604.22222")
        self.assertEqual(items[1]["rank"], 2)

    def test_retrieved_items_contain_parsed_json_fields(self):
        papers = [
            {
                "id": "2604.33333",
                "title": "JSON Fields Paper",
                "score": 4.0,
                "authors": ["Author A", "Author B"],
                "abstract": "Testing JSON fields.",
                "categories": ["cs.LG", "cs.AI"],
                "score_details": {"relevance": 3.0, "semantic": 1.0},
                "source": "arxiv",
            }
        ]
        run_id = self.store.save_recommendation_run("2026-04-26", "json_test", papers)
        items = self.store.get_recommendation_items(run_id)
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item["title"], "JSON Fields Paper")
        self.assertEqual(item["authors"], ["Author A", "Author B"])
        self.assertEqual(item["categories"], ["cs.LG", "cs.AI"])
        self.assertEqual(item["score_details"], {"relevance": 3.0, "semantic": 1.0})
        self.assertEqual(item["source"], "arxiv")

    def test_list_recommendation_runs(self):
        self.store.save_recommendation_run(
            "2026-04-25",
            "test_source_1",
            [{"id": "2604.11111", "title": "P1", "score": 1.0}],
        )
        self.store.save_recommendation_run(
            "2026-04-26",
            "test_source_2",
            [{"id": "2604.22222", "title": "P2", "score": 2.0}],
        )
        runs = self.store.list_recommendation_runs(limit=5)
        self.assertEqual(len(runs), 2)
        run_dates = {r["run_date"] for r in runs}
        self.assertIn("2026-04-25", run_dates)
        self.assertIn("2026-04-26", run_dates)

    def test_empty_run_returns_empty_items(self):
        run_id = self.store.save_recommendation_run("2026-04-26", "empty_test", [])
        items = self.store.get_recommendation_items(run_id)
        self.assertEqual(items, [])

    def test_empty_run_has_zero_paper_count(self):
        run_id = self.store.save_recommendation_run("2026-04-26", "empty_test", [])
        runs = self.store.list_recommendation_runs(limit=1)
        matching = [r for r in runs if r["run_id"] == run_id]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["paper_count"], 0)

    def test_has_running_job(self):
        """Verify the P0 fix: has_running_job works correctly."""
        self.assertFalse(self.store.has_running_job("daily_recommendation"))
        run_id = self.store.create_job("daily_recommendation", "test", {}, "running")[
            "run_id"
        ]
        self.assertTrue(self.store.has_running_job("daily_recommendation"))
        self.store.update_job(run_id, "succeeded")
        self.assertFalse(self.store.has_running_job("daily_recommendation"))

    def test_has_running_job_queued_also_counts(self):
        """Both 'queued' and 'running' statuses should be detected."""
        self.store.create_job("nightly_sync", "test", {}, "queued")
        self.assertTrue(self.store.has_running_job("nightly_sync"))
        self.assertFalse(self.store.has_running_job("daily_recommendation"))

    def test_multiple_runs_same_date(self):
        """Multiple runs on the same date should all be stored."""
        run1 = self.store.save_recommendation_run("2026-04-26", "morning", [{"id": "2604.00001", "title": "M1", "score": 1.0}])
        run2 = self.store.save_recommendation_run("2026-04-26", "evening", [{"id": "2604.00002", "title": "M2", "score": 2.0}])
        self.assertNotEqual(run1, run2)
        self.assertEqual(len(self.store.get_recommendation_items(run1)), 1)
        self.assertEqual(len(self.store.get_recommendation_items(run2)), 1)
