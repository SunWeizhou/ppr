"""Tests for workspace backend — schema, CRUD, services."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from state_store import StateStore


class WorkspaceBackendSchemaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "state.db"
        self.store = StateStore(str(self.db_path))

    def tearDown(self):
        self.tmp.cleanup()

    def _columns(self, table):
        with sqlite3.connect(str(self.db_path)) as conn:
            rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return {row[1] for row in rows}

    def test_workspace_tables_exist(self):
        with sqlite3.connect(str(self.db_path)) as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        tables = {row[0] for row in rows}
        self.assertIn("research_questions", tables)
        self.assertIn("evidence_claims", tables)

    def test_workspace_columns_are_added_to_existing_tables(self):
        self.assertGreaterEqual(
            self._columns("paper_metadata"),
            {"source", "source_run_id", "first_seen_at", "workspace_status"},
        )
        self.assertGreaterEqual(
            self._columns("reading_queue_items"),
            {"research_question_id", "decision_context"},
        )
        self.assertGreaterEqual(
            self._columns("paper_ai_analyses"),
            {"evidence_claim_ids", "confidence"},
        )
        self.assertIn("research_question_id", self._columns("subscriptions"))

    def test_schema_initialization_is_idempotent(self):
        StateStore(str(self.db_path))
        StateStore(str(self.db_path))
        self.assertIn("workspace_status", self._columns("paper_metadata"))

    def test_existing_metadata_and_queue_methods_still_work(self):
        self.store.save_paper_metadata(
            "2604.12345v2",
            {"title": "Workspace compatible paper", "abstract": "A."},
        )
        self.store.upsert_queue_item("2604.12345v2", "Skim Later")

        metadata = self.store.get_paper_metadata("2604.12345")
        queue_item = self.store.get_queue_item("2604.12345")

        self.assertEqual(metadata["title"], "Workspace compatible paper")
        self.assertEqual(queue_item["status"], "Skim Later")
