"""Unit tests for SubscriptionRunner -- error-safe execution, dedup, and inbox lifecycle."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from state_store import StateStore
from app.services.subscription_runner import SubscriptionRunner


class SubscriptionRunnerTests(unittest.TestCase):
    """Comprehensive test suite for SubscriptionRunner."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.store = StateStore(str(self.tmp_path / "test.db"))
        self.runner = SubscriptionRunner(self.store)

    def tearDown(self):
        self.tmp.cleanup()

    # ------------------------------------------------------------------
    # 1. run_all_subscriptions returns proper summary
    # ------------------------------------------------------------------

    @patch("app.services.arxiv_source.search_by_keywords")
    def test_run_all_subscriptions_returns_summary(self, mock_search):
        """run_all_subscriptions returns a summary dict with counts."""
        sub_a = self.store.create_subscription(
            "query", "Sub A", "machine learning"
        )
        sub_b = self.store.create_subscription(
            "query", "Sub B", "natural language"
        )
        # Both subscriptions share a paper -- dedup won't double-count
        mock_search.return_value = [
            {"id": "2604.12345", "title": "A common paper"},
        ]

        result = self.runner.run_all_subscriptions()

        self.assertTrue(result["success"])
        self.assertIn("subscriptions_checked", result)
        self.assertIn("total_hits", result)
        self.assertIn("errors", result)
        self.assertIsInstance(result["errors"], list)
        # Two subscriptions were run
        self.assertEqual(result["subscriptions_checked"], 2)
        # Each got one hit (different subscriptions, so two unique hits)
        self.assertEqual(result["total_hits"], 2)

    @patch("app.services.arxiv_source.search_by_keywords")
    def test_run_all_subscriptions_with_disabled_subscriptions(
        self, mock_search
    ):
        """Disabled subscriptions are skipped."""
        self.store.create_subscription(
            "query", "Enabled", "ml", enabled=True
        )
        self.store.create_subscription(
            "query", "Disabled", "nlp", enabled=False
        )
        mock_search.return_value = [{"id": "2604.12345", "title": "Paper"}]

        result = self.runner.run_all_subscriptions()

        self.assertTrue(result["success"])
        self.assertEqual(result["subscriptions_checked"], 1)
        self.assertEqual(result["total_hits"], 1)

    @patch("app.services.arxiv_source.search_by_keywords")
    def test_run_all_subscriptions_no_subscriptions(self, mock_search):
        """No subscriptions yields zero counts."""
        result = self.runner.run_all_subscriptions()
        self.assertTrue(result["success"])
        self.assertEqual(result["subscriptions_checked"], 0)
        self.assertEqual(result["total_hits"], 0)
        self.assertEqual(result["errors"], [])
        mock_search.assert_not_called()

    # ------------------------------------------------------------------
    # 2. dedupe_hits filters out existing hits
    # ------------------------------------------------------------------

    def test_dedupe_hits_filters_existing(self):
        """Existing paper_ids for the subscription are excluded."""
        sub = self.store.create_subscription("query", "Test", "test")
        self.store.upsert_subscription_hit(
            sub["id"], "2604.12345", matched_reason="query"
        )

        paper_ids = ["2604.12345", "2604.67890", "2604.99999"]
        new_ids = self.runner.dedupe_hits(paper_ids, sub["id"])

        self.assertNotIn("2604.12345", new_ids)
        self.assertIn("2604.67890", new_ids)
        self.assertIn("2604.99999", new_ids)
        self.assertEqual(len(new_ids), 2)

    def test_dedupe_hits_empty_input(self):
        """Empty paper_ids returns an empty list."""
        sub = self.store.create_subscription("query", "Test", "test")
        result = self.runner.dedupe_hits([], sub["id"])
        self.assertEqual(result, [])

    def test_dedupe_hits_different_subscriptions(self):
        """Hits from different subscriptions are not filtered out."""
        sub_a = self.store.create_subscription("query", "A", "a")
        sub_b = self.store.create_subscription("query", "B", "b")
        self.store.upsert_subscription_hit(
            sub_a["id"], "2604.12345", matched_reason="query"
        )

        # Same paper_id should NOT be filtered for sub_b
        new_ids = self.runner.dedupe_hits(["2604.12345"], sub_b["id"])

        self.assertIn("2604.12345", new_ids)
        self.assertEqual(len(new_ids), 1)

    # ------------------------------------------------------------------
    # 3. send_hit_to_inbox succeeds for existing hits
    # ------------------------------------------------------------------

    def test_send_hit_to_inbox_returns_true_on_success(self):
        """An existing hit can be sent to the inbox."""
        sub = self.store.create_subscription("query", "Test", "test")
        hit = self.store.upsert_subscription_hit(
            sub["id"], "2604.12345", matched_reason="query"
        )

        result = self.runner.send_hit_to_inbox(hit["id"])

        self.assertTrue(result)

        # Verify the hit status was updated
        hits = self.store.list_subscription_hits(
            subscription_id=sub["id"], status="sent_to_inbox"
        )
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["paper_id"], "2604.12345")

        # Verify queue item was created
        queue = self.store.list_queue_items(status="Inbox")
        self.assertGreaterEqual(len(queue), 1)
        queue_ids = [q["paper_id"] for q in queue]
        self.assertIn("2604.12345", queue_ids)

    def test_send_hit_to_inbox_returns_false_for_missing(self):
        """A non-existent hit id returns False."""
        result = self.runner.send_hit_to_inbox(99999)
        self.assertFalse(result)

    def test_send_hit_to_inbox_idempotent(self):
        """Sending the same hit twice does not raise."""
        sub = self.store.create_subscription("query", "Test", "test")
        hit = self.store.upsert_subscription_hit(
            sub["id"], "2604.12345", matched_reason="query"
        )

        result1 = self.runner.send_hit_to_inbox(hit["id"])
        result2 = self.runner.send_hit_to_inbox(hit["id"])

        self.assertTrue(result1)
        self.assertTrue(result2)

    # ------------------------------------------------------------------
    # 4. ignore_hit succeeds for existing hits
    # ------------------------------------------------------------------

    def test_ignore_hit_returns_true_on_success(self):
        """An existing hit can be marked as ignored."""
        sub = self.store.create_subscription("query", "Test", "test")
        hit = self.store.upsert_subscription_hit(
            sub["id"], "2604.12345", matched_reason="query"
        )

        result = self.runner.ignore_hit(hit["id"])

        self.assertTrue(result)

        # Verify the hit status was updated
        hits = self.store.list_subscription_hits(
            subscription_id=sub["id"], status="ignored"
        )
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["paper_id"], "2604.12345")

    def test_ignore_hit_returns_false_for_missing(self):
        """A non-existent hit id returns False."""
        result = self.runner.ignore_hit(99999)
        self.assertFalse(result)

    def test_ignore_hit_idempotent(self):
        """Ignoring the same hit twice does not raise."""
        sub = self.store.create_subscription("query", "Test", "test")
        hit = self.store.upsert_subscription_hit(
            sub["id"], "2604.12345", matched_reason="query"
        )

        result1 = self.runner.ignore_hit(hit["id"])
        result2 = self.runner.ignore_hit(hit["id"])

        self.assertTrue(result1)
        self.assertTrue(result2)

    # ------------------------------------------------------------------
    # 5. Additional: persist_hits
    # ------------------------------------------------------------------

    def test_persist_hits_stores_and_dedupes(self):
        """persist_hits stores new hits and skips duplicates."""
        sub = self.store.create_subscription("query", "Test", "test")
        self.store.upsert_subscription_hit(
            sub["id"], "2604.12345", matched_reason="query"
        )

        # One existing, one new
        count = self.runner.persist_hits(
            sub["id"],
            ["2604.12345", "2604.67890"],
            matched_reason="query",
        )

        self.assertEqual(count, 1)

        hits = self.store.list_subscription_hits(subscription_id=sub["id"])
        self.assertEqual(len(hits), 2)

    def test_persist_hits_empty_list(self):
        """persist_hits with no paper_ids returns 0."""
        sub = self.store.create_subscription("query", "Test", "test")
        count = self.runner.persist_hits(sub["id"], [])
        self.assertEqual(count, 0)

    # ------------------------------------------------------------------
    # 6. Additional: type-specific runners
    # ------------------------------------------------------------------

    @patch("app.services.arxiv_source.search_by_keywords")
    def test_run_query_subscription_search_failure(self, mock_search):
        """run_query_subscription returns 0 on search exception."""
        mock_search.side_effect = Exception("API unavailable")
        sub = self.store.create_subscription("query", "Test", "ml")

        count = self.runner.run_query_subscription(sub)

        self.assertEqual(count, 0)

    @patch("app.services.arxiv_source.search_by_keywords")
    def test_run_author_subscription_returns_count(self, mock_search):
        """run_author_subscription finds and persists hits."""
        mock_search.return_value = [
            {"id": "2604.12345", "title": "Paper by Hinton"},
        ]
        sub = self.store.create_subscription(
            "author", "Geoffrey Hinton", "Geoffrey Hinton"
        )

        count = self.runner.run_author_subscription(sub)

        self.assertEqual(count, 1)
        hits = self.store.list_subscription_hits(subscription_id=sub["id"])
        self.assertEqual(hits[0]["paper_id"], "2604.12345")

    @patch("app.services.arxiv_source.search_by_keywords")
    def test_run_venue_subscription_returns_count(self, mock_search):
        """run_venue_subscription finds and persists hits."""
        mock_search.return_value = [
            {"id": "2604.12345", "title": "Paper in venue"},
        ]
        sub = self.store.create_subscription(
            "venue", "NeurIPS", "NeurIPS"
        )

        count = self.runner.run_venue_subscription(sub)

        self.assertEqual(count, 1)
        hits = self.store.list_subscription_hits(subscription_id=sub["id"])
        self.assertEqual(hits[0]["paper_id"], "2604.12345")


if __name__ == "__main__":
    unittest.main()
