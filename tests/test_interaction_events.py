"""Tests for interaction_events recording via API routes.

Verifies that user actions recorded through the three instrumented endpoints
result in the expected rows in the ``interaction_events`` table.
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from state_store import StateStore


class TestInteractionEventTracking(unittest.TestCase):
    """Verify that user actions recorded via API routes
    result in interaction_events table entries."""

    def setUp(self):
        import web_server
        from app.routes import api as api_routes

        self.tmpdir = tempfile.mkdtemp()
        self.tmp_path = Path(self.tmpdir)

        # Create isolated state store
        self.store = StateStore(str(self.tmp_path / "state.db"))

        # Save originals
        self._orig_ws_store = web_server.STATE_STORE
        self._orig_api_store = api_routes.STATE_STORE

        # Patch state store for all route lookups
        web_server.STATE_STORE = self.store
        api_routes.STATE_STORE = self.store

        self.client = web_server.app.test_client()

    def tearDown(self):
        import web_server
        from app.routes import api as api_routes

        web_server.STATE_STORE = self._orig_ws_store
        api_routes.STATE_STORE = self._orig_api_store

        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    # ------------------------------------------------------------------
    # StateStore direct API tests
    # ------------------------------------------------------------------

    def test_record_event_creates_entry(self):
        """record_event returns a positive integer event_id."""
        eid = self.store.record_event("test_event", "2401.12345", {"key": "value"})
        self.assertIsInstance(eid, int)
        self.assertGreater(eid, 0)

    def test_list_interaction_events_returns_recorded_event(self):
        """Events recorded via record_event are visible in list_interaction_events."""
        self.store.record_event("test_event", "2401.12345", {"key": "value"})
        events = self.store.list_interaction_events(limit=10)
        matching = [e for e in events if e["event_type"] == "test_event"]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["paper_id"], "2401.12345")

    def test_record_event_without_paper_id(self):
        """record_event works with empty paper_id."""
        eid = self.store.record_event("system_event")
        self.assertIsInstance(eid, int)
        self.assertGreater(eid, 0)
        events = self.store.list_interaction_events(limit=10)
        matching = [e for e in events if e["event_type"] == "system_event"]
        self.assertEqual(len(matching), 1)

    # ------------------------------------------------------------------
    # POST /api/feedback
    # ------------------------------------------------------------------

    @patch("app.routes.api.feedback._feedback_service")
    def test_feedback_like_records_feedback_relevant(self, mock_feedback_svc):
        """POST /api/feedback with action=like records feedback_relevant."""
        mock_instance = mock_feedback_svc.return_value
        mock_instance.handle_feedback.return_value = (
            {"success": True, "feedback": {"liked": ["2401.12345"], "disliked": []}},
            200,
        )

        response = self.client.post(
            "/api/feedback",
            json={"paper_id": "2401.12345", "action": "like", "title": "Test Paper"},
        )
        self.assertEqual(response.status_code, 200)

        events = self.store.list_interaction_events(limit=10)
        self.assertTrue(
            any(e["event_type"] == "feedback_relevant" for e in events),
            "Expected feedback_relevant event not found",
        )

    @patch("app.routes.api.feedback._feedback_service")
    def test_feedback_dislike_records_feedback_ignored(self, mock_feedback_svc):
        """POST /api/feedback with action=dislike records feedback_ignored."""
        mock_instance = mock_feedback_svc.return_value
        mock_instance.handle_feedback.return_value = (
            {"success": True, "feedback": {"liked": [], "disliked": ["2401.12345"]}},
            200,
        )

        response = self.client.post(
            "/api/feedback",
            json={"paper_id": "2401.12345", "action": "dislike", "title": "Test Paper"},
        )
        self.assertEqual(response.status_code, 200)

        events = self.store.list_interaction_events(limit=10)
        self.assertTrue(
            any(e["event_type"] == "feedback_ignored" for e in events),
            "Expected feedback_ignored event not found",
        )

    @patch("app.routes.api.feedback._feedback_service")
    def test_feedback_other_action_does_not_record_semantic_event(
        self, mock_feedback_svc
    ):
        """Non-like/dislike actions don't create feedback_relevant or feedback_ignored."""
        mock_instance = mock_feedback_svc.return_value
        mock_instance.handle_feedback.return_value = (
            {"success": True, "event_id": 999},
            200,
        )

        response = self.client.post(
            "/api/feedback",
            json={
                "paper_id": "2401.12345",
                "action": "open_paper",
                "title": "Test Paper",
            },
        )
        self.assertEqual(response.status_code, 200)

        events = self.store.list_interaction_events(limit=10)
        self.assertFalse(
            any(
                e["event_type"] in ("feedback_relevant", "feedback_ignored")
                for e in events
            ),
            "Expected no feedback_relevant or feedback_ignored events",
        )

    # ------------------------------------------------------------------
    # POST /api/queue
    # ------------------------------------------------------------------

    def test_queue_status_records_event(self):
        """POST /api/queue records queue_status_changed."""
        response = self.client.post(
            "/api/queue",
            json={
                "paper_id": "2401.12345",
                "status": "Skim Later",
                "source": "test",
            },
        )
        self.assertEqual(response.status_code, 200)

        events = self.store.list_interaction_events(limit=10)
        self.assertTrue(
            any(e["event_type"] == "queue_status_changed" for e in events),
            "Expected queue_status_changed event not found",
        )

    def test_queue_status_event_has_status_in_payload(self):
        """queue_status_changed event payload includes the new status."""
        self.client.post(
            "/api/queue",
            json={
                "paper_id": "2401.12345",
                "status": "Deep Read",
                "source": "test",
            },
        )

        events = self.store.list_interaction_events(limit=10)
        matching = [
            e for e in events if e["event_type"] == "queue_status_changed"
            and e["paper_id"] == "2401.12345"
        ]
        self.assertGreaterEqual(len(matching), 1)
        # Check at least one has the payload status
        has_status = any(
            (e.get("payload_json") or {}).get("status") == "Deep Read"
            for e in matching
        )
        self.assertTrue(has_status)

    # ------------------------------------------------------------------
    # POST /api/queue/bulk
    # ------------------------------------------------------------------

    def test_queue_bulk_records_events(self):
        """POST /api/queue/bulk records queue_status_changed for each paper."""
        response = self.client.post(
            "/api/queue/bulk",
            json={
                "paper_ids": ["2401.12345", "2401.67890"],
                "status": "Deep Read",
                "source": "test",
            },
        )
        self.assertEqual(response.status_code, 200)

        events = self.store.list_interaction_events(limit=10)
        queue_events = [
            e for e in events if e["event_type"] == "queue_status_changed"
        ]
        # At minimum one per paper (service records one, route adds another)
        self.assertGreaterEqual(len(queue_events), 2)

    # ------------------------------------------------------------------
    # GET /api/fetch_paper/<paper_id>
    # ------------------------------------------------------------------

    @patch("app.services.arxiv_source.fetch_arxiv_metadata")
    def test_paper_opened_records_event(self, mock_fetch):
        """GET /api/fetch_paper/<id> records paper_opened."""
        mock_fetch.return_value = {
            "title": "Test Paper Title",
            "abstract": "This is a test abstract for the paper.",
            "authors": ["Author One", "Author Two"],
        }

        response = self.client.get("/api/fetch_paper/2401.12345")
        self.assertEqual(response.status_code, 200)

        events = self.store.list_interaction_events(limit=10)
        self.assertTrue(
            any(e["event_type"] == "paper_opened" for e in events),
            "Expected paper_opened event not found",
        )

    @patch("app.services.arxiv_source.fetch_arxiv_metadata")
    def test_paper_opened_event_has_correct_paper_id(self, mock_fetch):
        """paper_opened event has the correct paper_id."""
        mock_fetch.return_value = {
            "title": "Test Paper Title",
            "abstract": "This is a test abstract for the paper.",
            "authors": ["Author One", "Author Two"],
        }

        self.client.get("/api/fetch_paper/2401.12345")

        events = self.store.list_interaction_events(limit=10)
        matching = [
            e for e in events if e["event_type"] == "paper_opened"
        ]
        self.assertGreaterEqual(len(matching), 1)
        self.assertEqual(matching[0]["paper_id"], "2401.12345")
