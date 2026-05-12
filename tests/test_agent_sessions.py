"""Test agent session, message, search history management, AgentService, and Agent API."""
import json as json_mod
import os
import tempfile
import unittest
from unittest.mock import patch


from state_store import StateStore


class TestAgentSessions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.store = StateStore(db_path=self.tmp.name)

    def tearDown(self):
        os.unlink(self.tmp.name)

    # ── Session CRUD ──

    def test_create_session_returns_dict(self):
        session = self.store.create_agent_session()
        self.assertIn("id", session)
        self.assertEqual(session["title"], "New Session")
        self.assertEqual(session["is_pinned"], 0)
        self.assertEqual(session["is_archived"], 0)
        self.assertEqual(session["message_count"], 0)

    def test_create_session_with_title(self):
        session = self.store.create_agent_session(title="Research on GNNs")
        self.assertEqual(session["title"], "Research on GNNs")

    def test_get_session_by_id(self):
        session = self.store.create_agent_session(title="Test")
        fetched = self.store.get_agent_session(session["id"])
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["title"], "Test")

    def test_get_nonexistent_session_returns_none(self):
        self.assertIsNone(self.store.get_agent_session("nonexistent-id"))

    def test_list_sessions_excludes_archived(self):
        s1 = self.store.create_agent_session(title="Active")
        s2 = self.store.create_agent_session(title="Archived")
        self.store.update_agent_session(s2["id"], is_archived=True)
        sessions = self.store.list_agent_sessions(archived=False)
        ids = [s["id"] for s in sessions]
        self.assertIn(s1["id"], ids)
        self.assertNotIn(s2["id"], ids)

    def test_list_sessions_includes_archived(self):
        s1 = self.store.create_agent_session(title="Active")
        s2 = self.store.create_agent_session(title="Archived")
        self.store.update_agent_session(s2["id"], is_archived=True)
        sessions = self.store.list_agent_sessions(archived=True)
        ids = [s["id"] for s in sessions]
        self.assertIn(s2["id"], ids)

    def test_update_session_title(self):
        session = self.store.create_agent_session()
        updated = self.store.update_agent_session(session["id"], title="New Title")
        self.assertEqual(updated["title"], "New Title")

    def test_update_session_pin(self):
        session = self.store.create_agent_session()
        updated = self.store.update_agent_session(session["id"], is_pinned=True)
        self.assertEqual(updated["is_pinned"], 1)

    def test_delete_session_cascades_messages(self):
        session = self.store.create_agent_session()
        self.store.add_agent_message(session["id"], "user", "Hello")
        self.store.add_agent_message(session["id"], "assistant", "Hi!")
        deleted = self.store.delete_agent_session(session["id"])
        self.assertTrue(deleted)
        self.assertEqual(self.store.get_session_messages(session["id"]), [])

    def test_delete_nonexistent_session_returns_false(self):
        self.assertFalse(self.store.delete_agent_session("nonexistent"))

    # ── Message CRUD ──

    def test_add_message_returns_dict(self):
        session = self.store.create_agent_session()
        msg = self.store.add_agent_message(session["id"], "user", "Find papers on RL")
        self.assertIn("id", msg)
        self.assertEqual(msg["role"], "user")
        self.assertEqual(msg["content"], "Find papers on RL")
        self.assertEqual(msg["session_id"], session["id"])

    def test_add_message_increments_count(self):
        session = self.store.create_agent_session()
        self.store.add_agent_message(session["id"], "user", "Hello")
        self.store.add_agent_message(session["id"], "assistant", "Hi!")
        updated = self.store.get_agent_session(session["id"])
        self.assertEqual(updated["message_count"], 2)

    def test_add_message_updates_last_active(self):
        session = self.store.create_agent_session()
        original_active = session["last_active"]
        self.store.add_agent_message(session["id"], "user", "Hello")
        updated = self.store.get_agent_session(session["id"])
        self.assertGreaterEqual(updated["last_active"], original_active)

    def test_add_message_with_metadata(self):
        session = self.store.create_agent_session()
        metadata = {"tool_results": [{"tool": "search", "status": "ok"}]}
        msg = self.store.add_agent_message(
            session["id"], "assistant", "Found papers", metadata=metadata
        )
        self.assertEqual(msg["metadata_json"]["tool_results"][0]["tool"], "search")

    def test_get_session_messages_ordered(self):
        session = self.store.create_agent_session()
        self.store.add_agent_message(session["id"], "user", "First")
        self.store.add_agent_message(session["id"], "assistant", "Second")
        self.store.add_agent_message(session["id"], "user", "Third")
        messages = self.store.get_session_messages(session["id"])
        self.assertEqual(len(messages), 3)
        self.assertEqual(messages[0]["content"], "First")
        self.assertEqual(messages[2]["content"], "Third")

    def test_get_session_messages_with_limit(self):
        session = self.store.create_agent_session()
        for i in range(25):
            self.store.add_agent_message(session["id"], "user", f"Message {i}")
        messages = self.store.get_session_messages(session["id"], limit=10)
        self.assertEqual(len(messages), 10)

    def test_add_message_validates_role(self):
        session = self.store.create_agent_session()
        with self.assertRaises(ValueError):
            self.store.add_agent_message(session["id"], "invalid_role", "Hello")

    def test_add_message_to_nonexistent_session_raises(self):
        with self.assertRaises(ValueError):
            self.store.add_agent_message("nonexistent", "user", "Hello")

    # ── Session ordering ──

    def test_list_sessions_ordered_by_last_active(self):
        s1 = self.store.create_agent_session(title="Old")
        s2 = self.store.create_agent_session(title="New")
        # Add message to s1 to make it most recent
        self.store.add_agent_message(s1["id"], "user", "bump")
        sessions = self.store.list_agent_sessions()
        self.assertEqual(sessions[0]["id"], s1["id"])

    def test_pinned_sessions_come_first(self):
        s1 = self.store.create_agent_session(title="Unpinned")
        s2 = self.store.create_agent_session(title="Pinned")
        self.store.update_agent_session(s2["id"], is_pinned=True)
        sessions = self.store.list_agent_sessions()
        self.assertEqual(sessions[0]["id"], s2["id"])


class TestSearchHistory(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.store = StateStore(db_path=self.tmp.name)

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_record_search_returns_dict(self):
        entry = self.store.record_search("federated learning")
        self.assertIn("id", entry)
        self.assertEqual(entry["query"], "federated learning")
        self.assertIsNone(entry["rewritten"])
        self.assertEqual(entry["result_count"], 0)

    def test_record_search_with_rewrite(self):
        entry = self.store.record_search(
            "FL papers",
            rewritten="federated learning papers",
            result_count=42,
            sources=["arxiv", "openalex"],
        )
        self.assertEqual(entry["rewritten"], "federated learning papers")
        self.assertEqual(entry["result_count"], 42)
        self.assertEqual(entry["sources"], ["arxiv", "openalex"])

    def test_list_recent_searches(self):
        self.store.record_search("query A")
        self.store.record_search("query B")
        self.store.record_search("query A")  # duplicate
        results = self.store.list_recent_searches(limit=10)
        queries = [r["query"] for r in results]
        self.assertEqual(queries[0], "query A")
        self.assertIn("query B", queries)
        self.assertEqual(len(set(queries)), len(queries))

    def test_list_recent_searches_limit(self):
        for i in range(20):
            self.store.record_search(f"query {i}")
        results = self.store.list_recent_searches(limit=5)
        self.assertEqual(len(results), 5)

    def test_record_clicked_paper(self):
        entry = self.store.record_search("test query")
        updated = self.store.record_search_click(entry["id"], "2401.12345")
        self.assertIn("2401.12345", updated["clicked_papers"])

    def test_get_suggested_searches(self):
        for _ in range(5):
            self.store.record_search("popular query")
        self.store.record_search("rare query")
        suggestions = self.store.get_suggested_searches(limit=5)
        queries = [s["query"] for s in suggestions]
        self.assertIn("popular query", queries)


from app.services.agent_service import AgentService
from app.services.ai_providers import NoProvider


class TestSessionAwareAgentService(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.store = StateStore(db_path=self.tmp.name)
        self.service = AgentService(
            self.store, provider_factory=lambda: NoProvider()
        )

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_handle_message_creates_session_if_none(self):
        result = self.service.handle_message("hello", session_id=None)
        self.assertTrue(result["success"])
        self.assertIn("session", result)
        self.assertIsNotNone(result["session"]["id"])

    def test_handle_message_reuses_existing_session(self):
        session = self.store.create_agent_session(title="Existing")
        result = self.service.handle_message("hello", session_id=session["id"])
        self.assertEqual(result["session"]["id"], session["id"])

    def test_handle_message_persists_messages(self):
        session = self.store.create_agent_session()
        self.service.handle_message("search RL papers", session_id=session["id"])
        messages = self.store.get_session_messages(session["id"])
        roles = [m["role"] for m in messages]
        self.assertIn("user", roles)
        self.assertIn("assistant", roles)

    def test_auto_title_on_first_message(self):
        result = self.service.handle_message(
            "Find papers about federated learning",
            session_id=None,
        )
        session = self.store.get_agent_session(result["session"]["id"])
        self.assertNotEqual(session["title"], "New Session")

    def test_context_includes_history(self):
        session = self.store.create_agent_session()
        self.service.handle_message("search GNN", session_id=session["id"])
        result = self.service.handle_message(
            "save the first one", session_id=session["id"]
        )
        self.assertTrue(result["success"])

    def test_response_shape(self):
        result = self.service.handle_message("hello")
        self.assertIn("success", result)
        self.assertIn("reply", result)
        self.assertIn("messages", result)
        self.assertIn("actions", result)
        self.assertIn("state_updates", result)
        self.assertIn("tool_results", result)
        self.assertIn("session", result)
        self.assertIn("id", result["session"])
        self.assertIn("title", result["session"])
        self.assertIn("message_count", result["session"])

    def test_safety_policy_preserved(self):
        result = self.service.handle_message("delete all papers")
        self.assertTrue(result.get("requires_confirmation", False))


class TestPhase3Integration(unittest.TestCase):
    """Integration tests for the full Phase 3 feature set."""

    def test_session_message_round_trip(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        store = StateStore(db_path=tmp.name)
        service = AgentService(store, provider_factory=lambda: NoProvider())

        r1 = service.handle_message("search GNN papers")
        session_id = r1["session"]["id"]
        self.assertIsNotNone(session_id)

        r2 = service.handle_message("save the first one", session_id=session_id)
        self.assertEqual(r2["session"]["id"], session_id)

        messages = store.get_session_messages(session_id)
        self.assertGreaterEqual(len(messages), 4)

        os.unlink(tmp.name)

    def test_search_history_records_on_search(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        store = StateStore(db_path=tmp.name)

        store.record_search("attention is all you need", result_count=25)
        store.record_search("transformer architecture", result_count=30)

        recent = store.list_recent_searches()
        self.assertEqual(len(recent), 2)
        self.assertEqual(recent[0]["query"], "transformer architecture")

        os.unlink(tmp.name)

    def test_query_rewriter_no_crash_without_llm(self):
        from app.services.query_rewriter import QueryRewriter
        rewriter = QueryRewriter(provider_factory=lambda: None)
        result = rewriter.rewrite("attention mechanism in transformers")
        self.assertEqual(result.original, "attention mechanism in transformers")

    def test_preact_bundle_exists(self):
        from pathlib import Path
        dist = Path(__file__).resolve().parent.parent / "static" / "dist"
        self.assertTrue((dist / "agent-panel.js").exists(), "agent-panel.js not found")
        self.assertTrue((dist / "agent-panel.css").exists(), "agent-panel.css not found")

    def test_preact_bundle_size(self):
        import gzip
        from pathlib import Path
        js_path = Path(__file__).resolve().parent.parent / "static" / "dist" / "agent-panel.js"
        if not js_path.exists():
            self.skipTest("agent-panel.js not built")
        raw = js_path.read_bytes()
        compressed = gzip.compress(raw)
        kb = len(compressed) / 1024
        self.assertLess(kb, 50, f"agent-panel.js is {kb:.1f}KB gzip (limit: 50KB)")

    def test_base_template_loads_agent_panel(self):
        from pathlib import Path
        template = Path(__file__).resolve().parent.parent / "templates" / "base_research.html"
        html = template.read_text(encoding="utf-8")
        self.assertIn("agent-panel", html, "Template must load agent-panel")
        self.assertNotIn("agent-drawer.js", html, "Old agent-drawer.js reference must be removed")
