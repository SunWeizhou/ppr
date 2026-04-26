"""Unit tests for Subscription model, InteractionEvent tracking,
Inbox progress, and QueueViewModel features."""

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from state_store import StateStore


class SubscriptionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.store = StateStore(str(self.tmp_path / "test.db"))

    def tearDown(self):
        self.tmp.cleanup()

    # ------------------------------------------------------------------
    # Subscription CRUD
    # ------------------------------------------------------------------

    def test_create_subscription_query_type(self):
        """POST /api/subscriptions creates a query-type subscription with an id."""
        import web_server

        original_store = web_server.STATE_STORE
        web_server.STATE_STORE = self.store
        try:
            response = web_server.app.test_client().post(
                "/api/subscriptions",
                json={
                    "type": "query",
                    "name": "Test Query",
                    "query_text": "machine learning",
                },
            )
        finally:
            web_server.STATE_STORE = original_store

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["success"])
        sub = payload["subscription"]
        self.assertIsInstance(sub["id"], int)
        self.assertGreater(sub["id"], 0)
        self.assertEqual(sub["type"], "query")
        self.assertEqual(sub["name"], "Test Query")
        self.assertEqual(sub["query_text"], "machine learning")

    def test_list_subscriptions(self):
        """GET /api/subscriptions returns a list of subscriptions."""
        self.store.create_subscription("query", "Query A", "ml")
        self.store.create_subscription("author", "Author B", "Hinton")

        import web_server

        original_store = web_server.STATE_STORE
        web_server.STATE_STORE = self.store
        try:
            response = web_server.app.test_client().get("/api/subscriptions")
        finally:
            web_server.STATE_STORE = original_store

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertIsInstance(payload["subscriptions"], list)
        self.assertGreaterEqual(len(payload["subscriptions"]), 2)

    def test_filter_subscriptions_by_type(self):
        """GET /api/subscriptions?type=author filters correctly."""
        self.store.create_subscription("query", "Query X", "ml")
        self.store.create_subscription("author", "Author Y", "Hinton")

        import web_server

        original_store = web_server.STATE_STORE
        web_server.STATE_STORE = self.store
        try:
            response = web_server.app.test_client().get(
                "/api/subscriptions?type=author"
            )
        finally:
            web_server.STATE_STORE = original_store

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["success"])
        subs = payload["subscriptions"]
        self.assertGreaterEqual(len(subs), 1)
        for sub in subs:
            self.assertEqual(sub["type"], "author")

    def test_update_subscription(self):
        """PUT /api/subscriptions/<id> updates enabled/name/query_text."""
        sub = self.store.create_subscription("query", "Original", "original query")
        sub_id = sub["id"]

        import web_server

        original_store = web_server.STATE_STORE
        web_server.STATE_STORE = self.store
        try:
            response = web_server.app.test_client().put(
                f"/api/subscriptions/{sub_id}",
                json={
                    "name": "Updated",
                    "query_text": "updated query",
                    "enabled": False,
                },
            )
        finally:
            web_server.STATE_STORE = original_store

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["subscription"]["name"], "Updated")
        self.assertEqual(payload["subscription"]["query_text"], "updated query")
        self.assertEqual(payload["subscription"]["enabled"], 0)

    def test_delete_subscription(self):
        """DELETE /api/subscriptions/<id> removes it from list."""
        sub = self.store.create_subscription("query", "To Delete", "delete me")
        sub_id = sub["id"]

        import web_server

        original_store = web_server.STATE_STORE
        web_server.STATE_STORE = self.store
        try:
            del_response = web_server.app.test_client().delete(
                f"/api/subscriptions/{sub_id}"
            )
            list_response = web_server.app.test_client().get("/api/subscriptions")
        finally:
            web_server.STATE_STORE = original_store

        self.assertEqual(del_response.status_code, 200)
        self.assertTrue(del_response.get_json()["success"])

        remaining_ids = [
            s["id"] for s in list_response.get_json()["subscriptions"]
        ]
        self.assertNotIn(sub_id, remaining_ids)

    # ------------------------------------------------------------------
    # Subscription Hits
    # ------------------------------------------------------------------

    def test_subscription_hit_recording(self):
        """upsert_subscription_hit creates a hit and updates latest_hit_count."""
        sub = self.store.create_subscription("query", "Hit Test", "test query")
        sub_id = sub["id"]

        # Initially zero
        self.assertEqual(sub["latest_hit_count"], 0)

        hit = self.store.upsert_subscription_hit(
            sub_id, "2604.12345v1", matched_reason="keyword match"
        )

        self.assertEqual(hit["subscription_id"], sub_id)
        self.assertEqual(hit["paper_id"], "2604.12345")
        self.assertEqual(hit["status"], "new")

        updated_sub = self.store.get_subscription(sub_id)
        self.assertEqual(updated_sub["latest_hit_count"], 1)

        # Second hit for the same subscription
        self.store.upsert_subscription_hit(
            sub_id, "2604.99999v2", matched_reason="keyword match"
        )
        updated_sub = self.store.get_subscription(sub_id)
        self.assertEqual(updated_sub["latest_hit_count"], 2)

    def test_list_subscription_hits(self):
        """GET /api/subscriptions/<id>/hits returns hits for that subscription."""
        sub = self.store.create_subscription("query", "Hits List", "test")
        sub_id = sub["id"]
        self.store.upsert_subscription_hit(
            sub_id, "2604.11111", matched_reason="test hit"
        )

        import web_server

        original_store = web_server.STATE_STORE
        web_server.STATE_STORE = self.store
        try:
            response = web_server.app.test_client().get(
                f"/api/subscriptions/{sub_id}/hits"
            )
        finally:
            web_server.STATE_STORE = original_store

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertIsInstance(payload["hits"], list)
        self.assertGreaterEqual(len(payload["hits"]), 1)
        self.assertEqual(payload["hits"][0]["paper_id"], "2604.11111")

    # ------------------------------------------------------------------
    # InteractionEvent
    # ------------------------------------------------------------------

    def test_record_and_list_events(self):
        """StateStore.record_event creates events that can be queried."""
        self.store.record_event("like", "2604.12345", {"source": "test"})
        self.store.record_event("dislike", "2604.67890", {"source": "test"})

        snapshot = self.store.export_state()
        events = snapshot["interaction_events"]

        self.assertGreaterEqual(len(events), 2)

        event_types = [e["event_type"] for e in events]
        self.assertIn("like", event_types)
        self.assertIn("dislike", event_types)

        paper_ids = [e["paper_id"] for e in events]
        self.assertIn("2604.12345", paper_ids)
        self.assertIn("2604.67890", paper_ids)

    # ------------------------------------------------------------------
    # Inbox Progress
    # ------------------------------------------------------------------

    def test_inbox_progress_returns_counts(self):
        """GET /api/inbox/progress returns correct JSON shape with all keys."""
        today = datetime.now().strftime("%Y-%m-%d")

        # Record some events and queue items so counts are non-zero
        self.store.record_event("like", "2604.12345")
        self.store.record_event("dislike", "2604.67890")
        self.store.record_event("queue_status_changed", "2604.11111")
        self.store.upsert_queue_item("2604.12345", "Skim Later")
        self.store.upsert_queue_item("2604.67890", "Deep Read")

        import web_server

        original_store = web_server.STATE_STORE
        web_server.STATE_STORE = self.store
        try:
            response = web_server.app.test_client().get(
                f"/api/inbox/progress?date={today}&total=20"
            )
        finally:
            web_server.STATE_STORE = original_store

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["success"])

        data = payload["data"]
        for key in (
            "handled",
            "untriaged",
            "liked",
            "disliked",
            "skimmed",
            "deep_read",
            "queued",
        ):
            self.assertIn(key, data, f"Missing key: {key}")
            self.assertIsInstance(data[key], int)

        self.assertEqual(data["total"], 20)

    def test_inbox_triage_complete_records_event(self):
        """POST /api/inbox/triage-complete returns success and records event."""
        today = datetime.now().strftime("%Y-%m-%d")

        import web_server

        original_store = web_server.STATE_STORE
        web_server.STATE_STORE = self.store
        try:
            response = web_server.app.test_client().post(
                "/api/inbox/triage-complete",
                json={"date": today, "total": 20},
            )
        finally:
            web_server.STATE_STORE = original_store

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertIn("summary", payload)
        self.assertEqual(payload["summary"]["date"], today)
        self.assertEqual(payload["summary"]["papers_total"], 20)

        # Verify the event was persisted
        snapshot = self.store.export_state()
        events = snapshot["interaction_events"]
        triage_events = [
            e for e in events if e["event_type"] == "inbox_triage_complete"
        ]
        self.assertEqual(len(triage_events), 1)

    # ------------------------------------------------------------------
    # ViewModel
    # ------------------------------------------------------------------

    def test_queue_viewmodel_returns_correct_context(self):
        """QueueViewModel.to_template_context() contains all required keys."""
        from app.services.queue_service import QueueService
        from app.viewmodels.queue_viewmodel import QueueViewModel

        cache_dir = self.tmp_path / "cache"
        history_dir = self.tmp_path / "history"
        cache_dir.mkdir()
        history_dir.mkdir()

        service = QueueService(
            self.store, cache_dir=cache_dir, history_dir=history_dir
        )
        viewmodel = QueueViewModel(service, self.store)
        context = viewmodel.to_template_context()

        required_keys = [
            "title",
            "active_tab",
            "queue_counts",
            "queue_status_values",
            "queue_items",
            "active_status",
        ]
        for key in required_keys:
            self.assertIn(key, context, f"Missing required key: {key}")

        self.assertEqual(context["title"], "Queue - arXiv Recommender")
        self.assertEqual(context["active_tab"], "queue")
        self.assertEqual(context["active_status"], "Inbox")
        self.assertIsInstance(context["queue_counts"], dict)
        self.assertIsInstance(context["queue_items"], list)

    # ------------------------------------------------------------------
    # Error handling
    # ------------------------------------------------------------------

    def test_error_response_format(self):
        """API errors return {"success": false, "error": "message"} with HTTP status."""
        import web_server

        original_store = web_server.STATE_STORE
        web_server.STATE_STORE = self.store
        try:
            # POST without required 'name' field
            response = web_server.app.test_client().post(
                "/api/subscriptions",
                json={"type": "query"},
            )
        finally:
            web_server.STATE_STORE = original_store

        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertFalse(payload["success"])
        self.assertIn("error", payload)
        self.assertIsInstance(payload["error"], str)
        self.assertGreater(len(payload["error"]), 0)


if __name__ == "__main__":
    unittest.main()
