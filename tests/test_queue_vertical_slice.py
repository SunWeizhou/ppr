import inspect
import json
import tempfile
import unittest
from pathlib import Path

from state_store import StateStore


class QueueVerticalSliceTests(unittest.TestCase):
    def test_queue_service_resolves_papers_and_preserves_notes(self):
        from app.services.queue_service import QueueService

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache_dir = root / "cache"
            history_dir = root / "history"
            cache_dir.mkdir()
            history_dir.mkdir()
            (cache_dir / "user_feedback.json").write_text(
                json.dumps({"liked": ["2604.11111v2"], "disliked": ["2604.33333v1"]}),
                encoding="utf-8",
            )
            (cache_dir / "favorite_papers.json").write_text(
                json.dumps(
                    {
                        "2604.22222v3": {
                            "title": "Favorite Queue Paper",
                            "abstract": "Favorite abstract",
                            "authors": "Ada Lovelace",
                            "score": 8.5,
                        }
                    }
                ),
                encoding="utf-8",
            )
            (cache_dir / "paper_cache.json").write_text(
                json.dumps(
                    {
                        "2604.33333": {
                            "title": "Cached Queue Paper",
                            "abstract": "Cached abstract",
                            "authors": "Grace Hopper",
                            "score": 4.0,
                        }
                    }
                ),
                encoding="utf-8",
            )
            (history_dir / "digest_2026-04-25.md").write_text(
                """
# arXiv Daily Digest

**Research Themes:** conformal prediction

## 1. History Queue Paper

**Authors:** Emmy Noether, David Hilbert

**arXiv:** [2604.11111v2](https://arxiv.org/abs/2604.11111v2)

**Summary:** History paper abstract.

**Relevance:** core match

**Score:** 7.0
""",
                encoding="utf-8",
            )

            store = StateStore(str(root / "state.db"))
            service = QueueService(store, cache_dir=cache_dir, history_dir=history_dir)
            service.update_item("2604.11111v2", "Skim Later", note="keep this", source="test")
            service.update_item("2604.11111", "Deep Read", note=None, source="test")
            service.update_item("2604.22222v3", "Saved", note="favorite", source="test")
            service.update_item("2604.33333v1", "Archived", note="cached", source="test")

            papers = service.resolve_papers(status=None)

        by_id = {paper["id"]: paper for paper in papers}
        self.assertEqual(by_id["2604.11111"]["title"], "History Queue Paper")
        self.assertEqual(by_id["2604.11111"]["queue_status"], "Deep Read")
        self.assertEqual(by_id["2604.11111"]["queue_note"], "keep this")
        self.assertTrue(by_id["2604.11111"]["is_liked"])
        self.assertEqual(by_id["2604.22222"]["title"], "Favorite Queue Paper")
        self.assertEqual(by_id["2604.33333"]["title"], "Cached Queue Paper")
        self.assertTrue(by_id["2604.33333"]["is_disliked"])
        self.assertEqual(by_id["2604.33333"]["queue_status_class"], "status-archived")

    def test_queue_service_records_single_and_bulk_status_events(self):
        from app.services.queue_service import QueueService

        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(str(Path(tmp) / "state.db"))
            service = QueueService(store)

            item, event_id = service.update_status(
                "2604.44444v2",
                "Skim Later",
                source="api_test",
                note="single",
            )
            bulk_items = service.bulk_update_status(
                ["2604.55555v1", "2604.66666v3"],
                "Deep Read",
                source="bulk_test",
                note="bulk",
            )
            events = store.export_state()["interaction_events"]

        self.assertEqual(item["paper_id"], "2604.44444")
        self.assertIsInstance(event_id, int)
        self.assertEqual([item["paper_id"] for item in bulk_items], ["2604.55555", "2604.66666"])
        self.assertEqual([event["event_type"] for event in events], ["queue_status_changed"] * 3)
        self.assertEqual(events[0]["payload_json"]["note"], "single")
        self.assertEqual(events[1]["payload_json"]["status"], "Deep Read")

    def test_queue_routes_no_longer_forward_to_web_server_queue_handlers(self):
        import app.routes.api as api_routes
        import app.routes.queue as queue_routes

        queue_source = Path("app/routes/queue.py").read_text(encoding="utf-8")
        api_manage_queue_source = inspect.getsource(api_routes.manage_queue)
        api_bulk_source = inspect.getsource(api_routes.manage_queue_bulk)

        self.assertNotIn("import web_server", queue_source)
        self.assertNotIn("_resolve_queue_papers", queue_source)
        self.assertNotIn("web_server.manage_queue", api_manage_queue_source)
        self.assertNotIn("web_server.manage_queue_bulk", api_bulk_source)
        self.assertIn("QueueService", queue_source)
        self.assertIn("QueueService", Path("app/routes/api.py").read_text(encoding="utf-8"))

    def test_queue_api_keeps_existing_json_shape_via_service(self):
        import web_server
        from app.routes import api as api_routes

        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(str(Path(tmp) / "state.db"))
            original_store = web_server.STATE_STORE
            original_api_store = getattr(api_routes, "STATE_STORE", None)
            web_server.STATE_STORE = store
            api_routes.STATE_STORE = store
            try:
                client = web_server.app.test_client()
                create_response = client.post(
                    "/api/queue",
                    json={"paper_id": "2604.77777v2", "status": "Skim Later", "note": "read intro"},
                )
                preserve_response = client.post(
                    "/api/queue",
                    json={"paper_id": "2604.77777", "status": "Deep Read"},
                )
                list_response = client.get("/api/queue?status=Deep%20Read")
                invalid_response = client.post(
                    "/api/queue/bulk",
                    json={"paper_ids": ["2604.88888"], "status": "Unknown"},
                )
            finally:
                web_server.STATE_STORE = original_store
                if original_api_store is None:
                    delattr(api_routes, "STATE_STORE")
                else:
                    api_routes.STATE_STORE = original_api_store

        self.assertEqual(create_response.status_code, 200)
        self.assertIn("event_id", create_response.get_json())
        self.assertEqual(preserve_response.status_code, 200)
        self.assertEqual(preserve_response.get_json()["item"]["note"], "read intro")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.get_json()["items"][0]["paper_id"], "2604.77777")
        self.assertEqual(invalid_response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
