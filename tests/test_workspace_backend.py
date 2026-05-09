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

    # ------------------------------------------------------------------
    #  Research Question CRUD
    # ------------------------------------------------------------------

    def test_research_question_crud(self):
        question = self.store.create_research_question(
            query_text="conformal prediction under distribution shift",
            intent_statement="Find reliable methods for conformal prediction under shift.",
            source="manual",
        )

        self.assertIsInstance(question["id"], int)
        self.assertEqual(question["status"], "active")

        fetched = self.store.get_research_question(question["id"])
        self.assertEqual(fetched["query_text"], "conformal prediction under distribution shift")

        updated = self.store.update_research_question(
            question["id"],
            status="paused",
            intent_statement="Updated intent.",
        )
        self.assertEqual(updated["status"], "paused")
        self.assertEqual(updated["intent_statement"], "Updated intent.")

        active = self.store.list_research_questions(status="active")
        paused = self.store.list_research_questions(status="paused")
        self.assertEqual(active, [])
        self.assertEqual([q["id"] for q in paused], [question["id"]])

    def test_create_research_question_rejects_invalid_status_and_source(self):
        with self.assertRaises(ValueError):
            self.store.create_research_question("x", status="later")
        with self.assertRaises(ValueError):
            self.store.create_research_question("x", source="email")

    def test_seed_research_questions_from_keywords(self):
        count = self.store.seed_research_questions_from_keywords(
            {
                "conformal prediction": {"weight": 3, "category": "core"},
                "bandits": {"weight": 1, "category": "secondary"},
                "survey": {"weight": -1, "category": "demote"},
            }
        )

        questions = self.store.list_research_questions()
        self.assertEqual(count, 2)
        self.assertEqual(
            {q["query_text"] for q in questions},
            {"conformal prediction", "bandits"},
        )

        second_count = self.store.seed_research_questions_from_keywords(
            {"conformal prediction": {"weight": 3, "category": "core"}}
        )
        self.assertEqual(second_count, 0)

    # ------------------------------------------------------------------
    #  Workspace field extensions
    # ------------------------------------------------------------------

    def test_queue_item_can_store_research_question_context(self):
        question = self.store.create_research_question("causal inference")
        item = self.store.upsert_queue_item(
            "2604.55555v1",
            "Deep Read",
            research_question_id=question["id"],
            decision_context="Useful for identification assumptions.",
        )

        self.assertEqual(item["paper_id"], "2604.55555")
        self.assertEqual(item["research_question_id"], question["id"])
        self.assertEqual(item["decision_context"], "Useful for identification assumptions.")

    def test_ai_analysis_can_store_evidence_links_and_confidence(self):
        analysis = self.store.upsert_paper_ai_analysis(
            "2604.44444",
            {"problem": "Studies robust prediction."},
            model_name="rule",
            prompt_version="workspace-v1",
            evidence_claim_ids=["claim-a", "claim-b"],
            confidence=0.72,
        )

        self.assertEqual(analysis["evidence_claim_ids"], ["claim-a", "claim-b"])
        self.assertAlmostEqual(analysis["confidence"], 0.72)

    def test_paper_metadata_keeps_workspace_source_columns_outside_metadata_json(self):
        self.store.save_paper_metadata(
            "2604.33333",
            {"title": "Source paper"},
            source="search",
            source_run_id="run-1",
            workspace_status="active",
        )

        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT source, source_run_id, workspace_status FROM paper_metadata WHERE paper_id = ?",
                ("2604.33333",),
            ).fetchone()

        self.assertEqual(row["source"], "search")
        self.assertEqual(row["source_run_id"], "run-1")
        self.assertEqual(row["workspace_status"], "active")
