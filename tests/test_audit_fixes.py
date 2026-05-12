"""Tests for audit-fix functions: build_recommendation_reason, recover_stale_jobs, trigger_source filtering."""

import sqlite3
import sys
import os
import unittest

# Ensure the project root is on sys.path so imports resolve
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestBuildRecommendationReason(unittest.TestCase):
    """E1: Tests for scoring_service.build_recommendation_reason."""

    def _call(self, paper, **kwargs):
        from app.services.scoring_service import build_recommendation_reason
        return build_recommendation_reason(paper, **kwargs)

    def test_matched_topics_from_core_keywords(self):
        paper = {"title": "Transformer attention mechanisms in deep learning", "abstract": "We study attention."}
        profile = {"core_keywords": {"transformer": 3.0, "attention": 2.0}}
        result = self._call(paper, user_profile=profile)
        self.assertIn("transformer", result["matched_topics"])
        self.assertIn("attention", result["matched_topics"])
        self.assertTrue(result["reason_summary"])

    def test_matched_subscriptions(self):
        paper = {"title": "Bayesian optimization for hyperparameter tuning", "abstract": ""}
        context = {"saved_searches": [{"name": "Bayesian Methods", "query_text": "bayesian optimization"}]}
        result = self._call(paper, run_context=context)
        self.assertEqual(result["matched_subscriptions"], ["Bayesian Methods"])

    def test_empty_paper_returns_fallback_summary(self):
        result = self._call({}, user_profile={}, run_context={})
        self.assertEqual(result["reason_summary"], "Recommended based on your research area")
        self.assertEqual(result["matched_topics"], [])
        self.assertEqual(result["matched_subscriptions"], [])

    def test_relevance_reason_fallback(self):
        paper = {"title": "foo", "abstract": "bar", "relevance_reason": "High keyword match"}
        result = self._call(paper, user_profile={})
        self.assertIn("High keyword match", result["reason_summary"])

    def test_return_shape(self):
        result = self._call({"title": "test"})
        for key in ("reason_summary", "matched_topics", "matched_subscriptions",
                     "zotero_similarity", "feedback_signals", "source_tags"):
            self.assertIn(key, result)
        self.assertIsInstance(result["zotero_similarity"], float)
        self.assertIsInstance(result["matched_topics"], list)


class TestRecoverStaleJobs(unittest.TestCase):
    """E2: Tests for StateStore.recover_stale_jobs."""

    def setUp(self):
        import tempfile
        from state_store import StateStore
        self._tmpdir = tempfile.TemporaryDirectory()
        self.store = StateStore(os.path.join(self._tmpdir.name, "test.db"))

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_recover_stale_running_job(self):
        """A job running for > stale_after_minutes should be marked failed."""
        job = self.store.create_job("recommendation", "manual", {})
        self.store.update_job(job["run_id"], "running")
        # Backdate the updated_at to 3 hours ago
        with self.store._connect() as conn:
            conn.execute(
                "UPDATE job_runs SET updated_at = datetime('now', '-3 hours') WHERE run_id = ?",
                (job["run_id"],),
            )
        recovered = self.store.recover_stale_jobs(stale_after_minutes=120)
        self.assertEqual(recovered, 1)
        latest = self.store.get_latest_job("recommendation")
        self.assertEqual(latest["status"], "failed")
        self.assertIn("stale", latest.get("error_text", ""))

    def test_no_recovery_for_fresh_jobs(self):
        """A recently created running job should NOT be recovered."""
        job = self.store.create_job("recommendation", "manual", {})
        self.store.update_job(job["run_id"], "running")
        recovered = self.store.recover_stale_jobs(stale_after_minutes=120)
        self.assertEqual(recovered, 0)

    def test_no_recovery_for_completed_jobs(self):
        """Already succeeded/failed jobs should not be touched."""
        job = self.store.create_job("recommendation", "manual", {})
        self.store.update_job(job["run_id"], "succeeded")
        recovered = self.store.recover_stale_jobs(stale_after_minutes=0)
        self.assertEqual(recovered, 0)


class TestTriggerSourceFiltering(unittest.TestCase):
    """E3: Tests for trigger_source parameter on list_recommendation_dates / get_recommendation_run_by_date."""

    def setUp(self):
        import tempfile
        from state_store import StateStore
        self._tmpdir = tempfile.TemporaryDirectory()
        self.store = StateStore(os.path.join(self._tmpdir.name, "test.db"))

    def tearDown(self):
        self._tmpdir.cleanup()

    def _insert_run(self, date, trigger_source):
        with self.store._connect() as conn:
            conn.execute(
                """INSERT INTO recommendation_runs
                   (run_date, trigger_source, status, paper_count, created_at)
                   VALUES (?, ?, 'succeeded', 5, datetime('now'))""",
                (date, trigger_source),
            )

    def test_list_dates_without_filter(self):
        self._insert_run("2026-05-01", "auto_homepage")
        self._insert_run("2026-04-30", "manual")
        dates = self.store.list_recommendation_dates()
        self.assertEqual(len(dates), 2)

    def test_list_dates_with_trigger_source(self):
        self._insert_run("2026-05-01", "auto_homepage")
        self._insert_run("2026-04-30", "manual")
        dates = self.store.list_recommendation_dates(trigger_source="auto_homepage")
        self.assertEqual(dates, ["2026-05-01"])

    def test_get_run_by_date_with_trigger_source(self):
        self._insert_run("2026-05-01", "auto_homepage")
        self._insert_run("2026-05-01", "manual")
        run = self.store.get_recommendation_run_by_date("2026-05-01", trigger_source="auto_homepage")
        self.assertIsNotNone(run)
        self.assertEqual(run["trigger_source"], "auto_homepage")

    def test_get_run_by_date_without_filter(self):
        self._insert_run("2026-05-01", "auto_homepage")
        run = self.store.get_recommendation_run_by_date("2026-05-01")
        self.assertIsNotNone(run)

    def test_get_run_by_date_no_match(self):
        self._insert_run("2026-05-01", "manual")
        run = self.store.get_recommendation_run_by_date("2026-05-01", trigger_source="auto_homepage")
        self.assertIsNone(run)


if __name__ == "__main__":
    unittest.main()
