import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class WebProductizationTests(unittest.TestCase):
    def test_save_feedback_does_not_attempt_git_commit(self):
        import web_server
        from app.services.feedback_service import FeedbackService

        with tempfile.TemporaryDirectory() as tmp:
            feedback_file = Path(tmp) / "user_feedback.json"
            original_feedback_file = web_server.FEEDBACK_FILE
            web_server.FEEDBACK_FILE = str(feedback_file)
            try:
                with mock.patch("web_server.subprocess.run") as run:
                    svc = FeedbackService(
                        web_server.STATE_STORE,
                        feedback_file=str(feedback_file),
                        favorites_file=str(Path(tmp) / "favorites.json"),
                        cache_file=str(Path(tmp) / "cache.json"),
                        history_dir=str(Path(tmp) / "history"),
                    )
                    svc.save_feedback({"liked": ["2604.12345"], "disliked": []})
                run.assert_not_called()
            finally:
                web_server.FEEDBACK_FILE = original_feedback_file

            self.assertEqual(
                json.loads(feedback_file.read_text(encoding="utf-8"))["liked"],
                ["2604.12345"],
            )

    def test_collection_paper_api_rejects_missing_collection(self):
        import web_server
        from state_store import StateStore

        with tempfile.TemporaryDirectory() as tmp:
            original_store = web_server.STATE_STORE
            web_server.STATE_STORE = StateStore(str(Path(tmp) / "state.db"))
            try:
                response = web_server.app.test_client().post(
                    "/api/collections/999/papers",
                    json={"paper_id": "2604.12345"},
                )
            finally:
                web_server.STATE_STORE = original_store

        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.get_json()["success"])

    def test_status_api_reports_recommendation_health(self):
        import web_server

        response = web_server.app.test_client().get("/api/status")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("recommendation_health", payload)
        self.assertIn("core_keyword_count", payload["recommendation_health"])
        self.assertIn("zotero", payload["recommendation_health"])

    def test_citation_api_uses_analyzer_without_missing_class_error(self):
        import arxiv_recommender_v5
        import web_server

        class FakeCitationAnalyzer:
            def __init__(self, cache_dir):
                self.cache_dir = cache_dir

            def fetch_citation_data(self, paper_id):
                return {"citations": 7, "influential_citations": 2, "references": 11}

        with mock.patch.object(arxiv_recommender_v5, "CitationAnalyzer", FakeCitationAnalyzer):
            response = web_server.app.test_client().get("/api/citation/2604.12345v2")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["citations"], 7)

    def test_feedback_api_stores_stable_arxiv_id(self):
        import web_server

        with tempfile.TemporaryDirectory() as tmp:
            feedback_file = Path(tmp) / "user_feedback.json"
            original_feedback_file = web_server.FEEDBACK_FILE
            web_server.FEEDBACK_FILE = str(feedback_file)
            try:
                response = web_server.app.test_client().post(
                    "/api/feedback",
                    json={
                        "paper_id": "2604.12345v2",
                        "action": "like",
                        "title": "Stable identity",
                    },
                )
            finally:
                web_server.FEEDBACK_FILE = original_feedback_file

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["feedback"]["liked"], ["2604.12345"])

    def test_feedback_api_merges_existing_versioned_ids_on_upgrade(self):
        import web_server

        with tempfile.TemporaryDirectory() as tmp:
            feedback_file = Path(tmp) / "user_feedback.json"
            feedback_file.write_text(
                json.dumps({"liked": ["2604.12345v1"], "disliked": ["2604.12345v2", "2604.99999v1"]}),
                encoding="utf-8",
            )
            original_feedback_file = web_server.FEEDBACK_FILE
            web_server.FEEDBACK_FILE = str(feedback_file)
            try:
                response = web_server.app.test_client().post(
                    "/api/feedback",
                    json={"paper_id": "2604.12345v3", "action": "like", "title": "Upgrade"},
                )
            finally:
                web_server.FEEDBACK_FILE = original_feedback_file

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["feedback"]["liked"], ["2604.12345"])
        self.assertEqual(response.get_json()["feedback"]["disliked"], ["2604.99999"])

    def test_queue_upgrade_merges_versioned_ids_before_new_write(self):
        import sqlite3
        import web_server
        from state_store import StateStore

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "state.db"
            StateStore(str(db_path))
            conn = sqlite3.connect(db_path)
            conn.execute(
                """
                INSERT INTO reading_queue_items(paper_id, status, source, note, tags_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("2604.12345v1", "Skim Later", "old", "", "[]", "2026-04-22T00:00:00Z"),
            )
            conn.commit()
            conn.close()

            original_store = web_server.STATE_STORE
            web_server.STATE_STORE = StateStore(str(db_path))
            try:
                response = web_server.app.test_client().post(
                    "/api/queue",
                    json={"paper_id": "2604.12345v2", "status": "Deep Read"},
                )
                rows = sqlite3.connect(db_path).execute(
                    "SELECT paper_id, status FROM reading_queue_items"
                ).fetchall()
            finally:
                web_server.STATE_STORE = original_store

        self.assertEqual(response.status_code, 200)
        self.assertEqual(rows, [("2604.12345", "Deep Read")])

    def test_state_snapshot_export_and_import_restore_whitelisted_data(self):
        import web_server
        from state_store import StateStore

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            feedback_file = root / "user_feedback.json"
            original_files = web_server.SNAPSHOT_FILES
            original_store = web_server.STATE_STORE
            web_server.SNAPSHOT_FILES = {"user_feedback": feedback_file}
            web_server.STATE_STORE = StateStore(str(root / "state.db"))
            web_server.STATE_STORE.upsert_queue_item("2604.55555v1", "Saved")
            feedback_file.write_text(json.dumps({"liked": ["2604.55555v1"], "disliked": []}), encoding="utf-8")
            try:
                export_response = web_server.app.test_client().get("/api/state/export")
                snapshot = json.loads(export_response.data.decode("utf-8"))
                feedback_file.write_text(json.dumps({"liked": [], "disliked": []}), encoding="utf-8")
                import_response = web_server.app.test_client().post("/api/state/import", json=snapshot)
                restored_feedback = json.loads(feedback_file.read_text(encoding="utf-8"))
            finally:
                web_server.SNAPSHOT_FILES = original_files
                web_server.STATE_STORE = original_store

        self.assertEqual(export_response.status_code, 200)
        self.assertEqual(import_response.status_code, 200)
        self.assertEqual(restored_feedback["liked"], ["2604.55555v1"])

    def test_setup_py_is_python_entrypoint_not_batch_script(self):
        setup_text = Path("setup.py").read_text(encoding="utf-8")

        self.assertNotIn("@echo off", setup_text.lower())
        self.assertIn("setuptools", setup_text)
        self.assertIn("arxiv-recommender=web_server:main", setup_text)


if __name__ == "__main__":
    unittest.main()
