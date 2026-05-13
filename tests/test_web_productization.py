import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class ImportBudgetTests(unittest.TestCase):
    """Startup import time budget."""

    def test_web_server_import_is_not_slow(self):
        """Importing web_server in a subprocess must finish within 10 seconds
        on local hardware."""
        code = "import time; t=time.time(); import web_server; print(f'OK {time.time()-t:.2f}s')"
        proc = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, timeout=30,
        )
        stdout = proc.stdout.strip()
        self.assertEqual(proc.returncode, 0, msg=stdout + proc.stderr)
        # Parse elapsed from "OK X.XXs"
        parts = stdout.split()
        if len(parts) >= 2:
            elapsed = float(parts[1].rstrip("s"))
            self.assertLessEqual(elapsed, 10.0,
                                 f"web_server import took {elapsed:.2f}s (budget: 10s)")


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
                    json={"paper_id": "2604.12345v2", "status": "Inbox"},
                )
                rows = sqlite3.connect(db_path).execute(
                    "SELECT paper_id, status FROM reading_queue_items"
                ).fetchall()
            finally:
                web_server.STATE_STORE = original_store

        self.assertEqual(response.status_code, 200)
        self.assertEqual(rows, [("2604.12345", "Inbox")])

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
            web_server.STATE_STORE.upsert_queue_item("2604.55555v1", "Inbox")
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

    def test_save_paper_metadata_via_state_store(self):
        """Save paper metadata and retrieve it, verifying fields match."""
        from state_store import StateStore

        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(str(Path(tmp) / "state.db"))
            paper_id = "2604.12345"
            metadata = {
                "title": "Test Paper Title",
                "abstract": "This is a test abstract for the paper.",
                "authors": "Author One, Author Two",
                "date": "2026-04-30",
                "score": 0,
                "relevance": "从 arXiv 获取",
            }

            store.save_paper_metadata(paper_id, metadata)
            retrieved = store.get_paper_metadata(paper_id)

            self.assertIsNotNone(retrieved)
            self.assertEqual(retrieved["title"], "Test Paper Title")
            self.assertEqual(retrieved["abstract"], "This is a test abstract for the paper.")
            self.assertEqual(retrieved["authors"], "Author One, Author Two")
            self.assertEqual(retrieved["date"], "2026-04-30")
            self.assertEqual(retrieved["score"], 0)
            self.assertEqual(retrieved["relevance"], "从 arXiv 获取")

    def test_get_paper_metadata_returns_none_for_missing(self):
        """Getting metadata for a non-existent paper_id returns None."""
        from state_store import StateStore

        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(str(Path(tmp) / "state.db"))
            result = store.get_paper_metadata("9999.99999")
            self.assertIsNone(result)

    def test_save_paper_metadata_canonicalizes_paper_id(self):
        """Saving with versioned paper_id should canonicalize and be retrievable."""
        from state_store import StateStore

        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(str(Path(tmp) / "state.db"))
            metadata = {
                "title": "Versioned Paper",
                "abstract": "Abstract.",
                "authors": "Author",
                "date": "2026-04-30",
                "score": 0,
                "relevance": "from arXiv",
            }

            store.save_paper_metadata("2604.12345v2", metadata)
            # Should be retrievable without version
            retrieved = store.get_paper_metadata("2604.12345")
            self.assertIsNotNone(retrieved)
            self.assertEqual(retrieved["title"], "Versioned Paper")

    def test_setup_py_is_python_entrypoint_not_batch_script(self):
        setup_text = Path("setup.py").read_text(encoding="utf-8")

        self.assertNotIn("@echo off", setup_text.lower())
        self.assertIn("setuptools", setup_text)
        self.assertIn("arxiv-recommender=web_server:main", setup_text)

    def test_search_route_returns_page_with_results(self):
        import web_server
        from state_store import StateStore

        fake_papers = [
            {
                "id": "2604.22787",
                "paper_id": "2604.22787v1",
                "title": "Mock Conformal Prediction Paper",
                "summary": "A mocked result for conformal prediction search.",
                "abstract": "A mocked result for conformal prediction search.",
                "authors": ["Ada Lovelace", "Grace Hopper"],
                "categories": ["stat.ML"],
                "published_at": "2026-04-30",
                "link": "https://arxiv.org/abs/2604.22787",
                "score": 7.5,
            }
        ]

        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(str(Path(tmp) / "state.db"))
            client = web_server.app.test_client()
            with (
                mock.patch("app.routes.inbox.get_state_store", return_value=store),
                mock.patch(
                    "arxiv_recommender_v5.search_by_keywords",
                    return_value=fake_papers,
                ),
            ):
                response = client.get("/search/conformal%20prediction")
                self.assertEqual(response.status_code, 200)
                html = response.data.decode("utf-8")
                self.assertIn("Mock Conformal Prediction Paper", html)

                detail = client.get("/papers/2604.22787")
                self.assertEqual(detail.status_code, 200)
                self.assertIn(
                    "Mock Conformal Prediction Paper",
                    detail.data.decode("utf-8"),
                )

    def test_search_route_returns_empty_state_for_no_keywords(self):
        import web_server

        response = web_server.app.test_client().get("/search")
        self.assertEqual(response.status_code, 200)

    def test_settings_page_does_not_render_full_api_key(self):
        """The settings page must not contain a full API key in the HTML
        response body."""
        import web_server

        response = web_server.app.test_client().get("/settings")
        self.assertEqual(response.status_code, 200)
        html = response.data.decode("utf-8")
        # An unredacted key would look like "sk-..." with 20+ chars after
        # Masked form is "sk-...XYZ" (short). Check we don't leak full keys.
        import re
        long_key_pattern = re.compile(r'sk-[a-zA-Z0-9_\-]{10,}')
        matches = long_key_pattern.findall(html)
        for m in matches:
            # Allow masked form like "sk-...XXXX"
            if "..." not in m and m.count("-") <= 2:
                self.fail(f"Potential API key leak in settings HTML: {m}")

    def test_search_route_has_loading_feedback(self):
        """Verify the search template includes a loading feedback mechanism."""
        template = Path("templates/search_research.html").read_text(encoding="utf-8")
        # Should disable the search button during submit
        self.assertIn("disabled", template)
        self.assertIn("Searching", template)

    def test_today_template_does_not_require_detail_panel_elements(self):
        """The today.html template is list-only (no #paperDetailPanel).
        inbox.js must not crash when those elements are absent.
        Verify inbox.js does not contain unguarded .textContent assignments
        on these elements."""
        source = Path("static/js/inbox.js").read_text(encoding="utf-8")
        # The code should use a guard pattern (getElementById + existence check)
        # rather than assigning .textContent directly on a getElementById result.
        # Count occurrences that look guarded vs unguarded.
        self.assertNotIn(
            "document.getElementById('detailTitle').textContent",
            source,
            "inbox.js must not directly assign .textContent on detailTitle "
            "without a guard",
        )


if __name__ == "__main__":
    unittest.main()
