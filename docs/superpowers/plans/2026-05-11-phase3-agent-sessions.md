# Phase 3: Agent Session System — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the stateless single-message Agent with a persistent session-based system that supports multi-turn conversations, multi-step execution, and session management. Build a Preact-based agent panel (replacing React agent-drawer) with Notion AI-style floating button and side panel. Add search history tracking and optional LLM-powered query rewriting.

**Architecture:** Three new SQLite tables (`agent_sessions`, `agent_messages`, `search_history`) in `state_store.py`. `AgentService` rewritten to be session-aware with context building from message history. Preact replaces React for the agent panel (~3KB vs ~45KB gzip), communicating via REST API and `window.AppState`/CustomEvent bridge. `QueryRewriter` class provides optional LLM-powered query enhancement with graceful no-LLM fallback.

**Tech Stack:** Preact 10.x + `marked` for Markdown, Vite build to single JS+CSS artifact, Python REST API (Flask), SQLite WAL mode. No new Python dependencies.

**Ref:** Design spec at `docs/superpowers/specs/2026-05-11-paper-agent-v2-design.md`, sections 4 (Search Enhancement) and 5 (Agent Session System).

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Modify | `state_store.py` | Add `agent_sessions`, `agent_messages`, `search_history` tables + CRUD methods |
| Rewrite | `app/services/agent_service.py` | Session-aware AgentService with multi-step execution, context building, auto-title |
| Create | `app/services/query_rewriter.py` | `QueryRewriter` class with LLM and rule-based fallback |
| Rewrite | `app/routes/api/agent.py` | Full session CRUD + message endpoint REST API |
| Modify | `package.json` | Replace React with Preact, replace react-markdown with marked |
| Modify | `vite.config.ts` | Update build config for Preact agent-panel output |
| Modify | `tsconfig.json` | Update for Preact JSX pragma and new source paths |
| Create | `frontend/agent-panel/index.tsx` | Preact app entry point |
| Create | `frontend/agent-panel/components/SessionList.tsx` | Session list with create, pin, archive, delete |
| Create | `frontend/agent-panel/components/MessageFlow.tsx` | Message thread with Markdown, action chips, typing indicator |
| Create | `frontend/agent-panel/components/AgentInput.tsx` | Composer input with Enter send, Shift+Enter newline |
| Create | `frontend/agent-panel/styles/agent-panel.css` | Agent panel styles using design tokens |
| Create | `frontend/agent-panel/api.ts` | API client for agent session/message endpoints |
| Create | `frontend/agent-panel/types.ts` | TypeScript type definitions |
| Modify | `templates/base_research.html` | Load Preact agent panel, remove old React drawer |
| Modify | `templates/search_research.html` | Add search history dropdown UI |
| Create | `tests/test_agent_sessions.py` | Session + message table CRUD tests |
| Create | `tests/test_query_rewriter.py` | Query rewriting tests with and without LLM |

---

### Task 1: Agent Sessions & Messages Tables in StateStore

**Files:**
- Modify: `state_store.py`
- Create: `tests/test_agent_sessions.py`

- [ ] **Step 1: Write tests for session and message CRUD**

```python
# tests/test_agent_sessions.py
"""Test agent session and message management in StateStore."""
import os
import tempfile
import unittest

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_agent_sessions.py -v`
Expected: FAIL -- `create_agent_session` and related methods do not exist.

- [ ] **Step 3: Add agent_sessions and agent_messages tables to StateStore._initialize**

In `state_store.py`, add within the `_initialize` method's `executescript` block, after the `feedback_models` table:

```python
                CREATE TABLE IF NOT EXISTS agent_sessions (
                    id            TEXT PRIMARY KEY,
                    title         TEXT DEFAULT 'New Session',
                    summary       TEXT DEFAULT '',
                    is_pinned     INTEGER DEFAULT 0,
                    is_archived   INTEGER DEFAULT 0,
                    message_count INTEGER DEFAULT 0,
                    last_active   TEXT DEFAULT (datetime('now')),
                    created_at    TEXT DEFAULT (datetime('now')),
                    updated_at    TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS agent_messages (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id    TEXT NOT NULL REFERENCES agent_sessions(id) ON DELETE CASCADE,
                    role          TEXT NOT NULL CHECK(role IN ('user','assistant','system','tool')),
                    content       TEXT NOT NULL,
                    metadata_json TEXT DEFAULT '{}',
                    created_at    TEXT DEFAULT (datetime('now'))
                );

                CREATE INDEX IF NOT EXISTS idx_agent_messages_session
                    ON agent_messages(session_id, created_at);
```

- [ ] **Step 4: Add CRUD methods to StateStore**

Add the following methods to the `StateStore` class in `state_store.py`, after the Feedback Models section:

```python
    # ------------------------------------------------------------------
    # Agent Sessions
    # ------------------------------------------------------------------

    def create_agent_session(self, title: str = "New Session") -> Dict:
        """Create a new agent conversation session."""
        now = _utc_now()
        session_id = uuid.uuid4().hex
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO agent_sessions(
                    id, title, summary, is_pinned, is_archived,
                    message_count, last_active, created_at, updated_at
                ) VALUES (?, ?, '', 0, 0, 0, ?, ?, ?)
                """,
                (session_id, title.strip(), now, now, now),
            )
            row = conn.execute(
                "SELECT * FROM agent_sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
        return self._row_to_dict(row)

    def get_agent_session(self, session_id: str) -> Optional[Dict]:
        """Get an agent session by ID."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM agent_sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def list_agent_sessions(
        self,
        archived: Optional[bool] = None,
        limit: int = 50,
    ) -> List[Dict]:
        """List agent sessions, optionally filtered by archive status.

        Results are ordered: pinned first, then by last_active descending.
        """
        query = "SELECT * FROM agent_sessions"
        params: List[object] = []
        if archived is not None:
            query += " WHERE is_archived = ?"
            params.append(1 if archived else 0)
        query += " ORDER BY is_pinned DESC, last_active DESC LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def update_agent_session(
        self,
        session_id: str,
        *,
        title: Optional[str] = None,
        summary: Optional[str] = None,
        is_pinned: Optional[bool] = None,
        is_archived: Optional[bool] = None,
    ) -> Optional[Dict]:
        """Update an agent session's mutable fields."""
        updates = []
        params: List[object] = []

        if title is not None:
            updates.append("title = ?")
            params.append(title.strip())
        if summary is not None:
            updates.append("summary = ?")
            params.append(summary.strip())
        if is_pinned is not None:
            updates.append("is_pinned = ?")
            params.append(1 if is_pinned else 0)
        if is_archived is not None:
            updates.append("is_archived = ?")
            params.append(1 if is_archived else 0)

        if not updates:
            return self.get_agent_session(session_id)

        updates.append("updated_at = ?")
        params.append(_utc_now())
        params.append(session_id)

        with self._lock, self._connect() as conn:
            conn.execute(
                f"UPDATE agent_sessions SET {', '.join(updates)} WHERE id = ?",
                params,
            )
        return self.get_agent_session(session_id)

    def delete_agent_session(self, session_id: str) -> bool:
        """Delete an agent session and cascade-delete its messages."""
        with self._lock, self._connect() as conn:
            conn.execute(
                "DELETE FROM agent_messages WHERE session_id = ?",
                (session_id,),
            )
            result = conn.execute(
                "DELETE FROM agent_sessions WHERE id = ?",
                (session_id,),
            )
        return result.rowcount > 0

    # ------------------------------------------------------------------
    # Agent Messages
    # ------------------------------------------------------------------

    def add_agent_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict] = None,
    ) -> Dict:
        """Add a message to an agent session.

        Updates the session's message_count and last_active timestamp.
        Raises ValueError for invalid role or nonexistent session.
        """
        if role not in ("user", "assistant", "system", "tool"):
            raise ValueError(f"Invalid message role: {role}")

        now = _utc_now()
        with self._lock, self._connect() as conn:
            # Verify session exists
            session = conn.execute(
                "SELECT id FROM agent_sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
            if session is None:
                raise ValueError(f"Agent session not found: {session_id}")

            conn.execute(
                """
                INSERT INTO agent_messages(
                    session_id, role, content, metadata_json, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    role,
                    content,
                    _to_json(metadata, {}),
                    now,
                ),
            )
            row = conn.execute(
                "SELECT * FROM agent_messages WHERE id = last_insert_rowid()"
            ).fetchone()

            # Update session counters
            conn.execute(
                """
                UPDATE agent_sessions
                SET message_count = (
                    SELECT COUNT(*) FROM agent_messages WHERE session_id = ?
                ),
                last_active = ?,
                updated_at = ?
                WHERE id = ?
                """,
                (session_id, now, now, session_id),
            )
        return self._row_to_dict(row)

    def get_session_messages(
        self,
        session_id: str,
        limit: int = 50,
    ) -> List[Dict]:
        """Get messages for a session, ordered by creation time ascending.

        When limit is provided, returns the most recent N messages
        (still in ascending order for display).
        """
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM (
                    SELECT * FROM agent_messages
                    WHERE session_id = ?
                    ORDER BY created_at DESC, id DESC
                    LIMIT ?
                ) sub ORDER BY created_at ASC, id ASC
                """,
                (session_id, limit),
            ).fetchall()
        return [self._row_to_dict(row) for row in rows]
```

- [ ] **Step 5: Update `_row_to_dict` to handle `metadata_json`**

In `state_store.py`, update the `_row_to_dict` static method to also parse `metadata_json`:

```python
    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> Dict:
        data = dict(row)
        for key in ("payload_json", "result_json", "filters_json", "tags_json", "evidence_claim_ids", "metadata_json"):
            if key in data:
                try:
                    data[key] = json.loads(data[key])
                except (TypeError, json.JSONDecodeError):
                    data[key] = [] if key in ("evidence_claim_ids", "tags_json") else {}
        return data
```

- [ ] **Step 6: Run tests**

Run: `python -m pytest tests/test_agent_sessions.py -v`
Expected: ALL PASS

- [ ] **Step 7: Run full test suite for regressions**

Run: `python -m pytest -q`
Expected: All existing tests still pass.

- [ ] **Step 8: Commit**

```bash
git add state_store.py tests/test_agent_sessions.py
git commit -m "feat(db): add agent_sessions and agent_messages tables with CRUD methods"
```

---

### Task 2: Search History Table in StateStore

**Files:**
- Modify: `state_store.py`
- Modify: `tests/test_agent_sessions.py`

- [ ] **Step 1: Add search history tests**

Append to `tests/test_agent_sessions.py`:

```python
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
        # Should deduplicate, most recent first
        queries = [r["query"] for r in results]
        self.assertEqual(queries[0], "query A")
        self.assertIn("query B", queries)
        # Deduped: each unique query appears once
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
        # popular query should rank higher
        queries = [s["query"] for s in suggestions]
        self.assertIn("popular query", queries)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_agent_sessions.py::TestSearchHistory -v`
Expected: FAIL -- methods do not exist yet.

- [ ] **Step 3: Add search_history table to StateStore._initialize**

In `state_store.py`, add within the `_initialize` method's `executescript` block, after the `agent_messages` index:

```python
                CREATE TABLE IF NOT EXISTS search_history (
                    id             INTEGER PRIMARY KEY AUTOINCREMENT,
                    query          TEXT NOT NULL,
                    rewritten      TEXT,
                    result_count   INTEGER DEFAULT 0,
                    sources        TEXT DEFAULT '[]',
                    clicked_papers TEXT DEFAULT '[]',
                    created_at     TEXT DEFAULT (datetime('now'))
                );

                CREATE INDEX IF NOT EXISTS idx_search_history_query
                    ON search_history(query);
                CREATE INDEX IF NOT EXISTS idx_search_history_created
                    ON search_history(created_at);
```

- [ ] **Step 4: Add search history CRUD methods to StateStore**

Add to `state_store.py` after the Agent Messages section:

```python
    # ------------------------------------------------------------------
    # Search History
    # ------------------------------------------------------------------

    def record_search(
        self,
        query: str,
        *,
        rewritten: Optional[str] = None,
        result_count: int = 0,
        sources: Optional[List[str]] = None,
    ) -> Dict:
        """Record a search query in history."""
        now = _utc_now()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO search_history(
                    query, rewritten, result_count, sources, clicked_papers, created_at
                ) VALUES (?, ?, ?, ?, '[]', ?)
                """,
                (
                    query.strip(),
                    rewritten,
                    result_count,
                    _to_json(sources, []),
                    now,
                ),
            )
            row = conn.execute(
                "SELECT * FROM search_history WHERE id = last_insert_rowid()"
            ).fetchone()
        return self._search_history_to_dict(row)

    def list_recent_searches(self, limit: int = 10) -> List[Dict]:
        """List recent searches, deduplicated by query text, most recent first."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT sh.* FROM search_history sh
                INNER JOIN (
                    SELECT query, MAX(id) AS max_id
                    FROM search_history
                    GROUP BY lower(query)
                ) latest ON sh.id = latest.max_id
                ORDER BY sh.created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._search_history_to_dict(row) for row in rows]

    def record_search_click(self, search_id: int, paper_id: str) -> Dict:
        """Record that the user clicked a paper from a search result."""
        paper_id = _canonical_paper_id(paper_id)
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM search_history WHERE id = ?",
                (search_id,),
            ).fetchone()
            if not row:
                raise ValueError(f"Search history entry not found: {search_id}")
            try:
                clicked = json.loads(row["clicked_papers"] or "[]")
            except (TypeError, json.JSONDecodeError):
                clicked = []
            if paper_id not in clicked:
                clicked.append(paper_id)
            conn.execute(
                "UPDATE search_history SET clicked_papers = ? WHERE id = ?",
                (json.dumps(clicked, ensure_ascii=False), search_id),
            )
            updated = conn.execute(
                "SELECT * FROM search_history WHERE id = ?",
                (search_id,),
            ).fetchone()
        return self._search_history_to_dict(updated)

    def get_suggested_searches(self, limit: int = 5) -> List[Dict]:
        """Return high-frequency search queries as suggestions.

        Aggregates by query text, ranked by frequency (count of searches).
        """
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT query, COUNT(*) AS freq,
                       MAX(created_at) AS latest,
                       MAX(result_count) AS best_result_count
                FROM search_history
                GROUP BY lower(query)
                HAVING freq >= 2
                ORDER BY freq DESC, latest DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {"query": row["query"], "frequency": row["freq"], "result_count": row["best_result_count"]}
            for row in rows
        ]

    @staticmethod
    def _search_history_to_dict(row: sqlite3.Row) -> Dict:
        data = dict(row)
        for key in ("sources", "clicked_papers"):
            if key in data:
                try:
                    data[key] = json.loads(data[key])
                except (TypeError, json.JSONDecodeError):
                    data[key] = []
        return data
```

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_agent_sessions.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add state_store.py tests/test_agent_sessions.py
git commit -m "feat(db): add search_history table with record, list, click, and suggestions"
```

---

### Task 3: QueryRewriter Service

**Files:**
- Create: `app/services/query_rewriter.py`
- Create: `tests/test_query_rewriter.py`

- [ ] **Step 1: Write QueryRewriter tests**

```python
# tests/test_query_rewriter.py
"""Test QueryRewriter with and without LLM provider."""
import unittest
from unittest.mock import MagicMock, patch
from dataclasses import asdict

from app.services.query_rewriter import QueryRewriter, RewriteResult


class TestRewriteResult(unittest.TestCase):
    def test_no_rewrite_when_no_llm(self):
        """Without LLM, rewriter returns original query unchanged."""
        rewriter = QueryRewriter(provider_factory=lambda: None)
        result = rewriter.rewrite("RL papers")
        self.assertEqual(result.original, "RL papers")
        self.assertEqual(result.rewritten, "RL papers")
        self.assertFalse(result.was_rewritten)
        self.assertEqual(result.expanded_terms, [])

    def test_abbreviation_expansion_rule_based(self):
        """Rule-based rewriter expands common abbreviations."""
        rewriter = QueryRewriter(provider_factory=lambda: None)
        result = rewriter.rewrite("GNN")
        # Rule-based should expand GNN
        self.assertIn("graph neural network", result.rewritten.lower())
        self.assertTrue(result.was_rewritten)

    def test_short_query_not_rewritten(self):
        """Very short queries that are already precise should not be rewritten."""
        rewriter = QueryRewriter(provider_factory=lambda: None)
        result = rewriter.rewrite("attention mechanism")
        # Common full terms should pass through
        self.assertEqual(result.original, "attention mechanism")

    def test_llm_rewrite_used_when_available(self):
        """When LLM is available, uses it for rewriting."""
        mock_provider = MagicMock()
        mock_provider.chat.return_value = (
            '{"rewritten": "reinforcement learning reward shaping", '
            '"explanation": "Expanded RL to reinforcement learning and added related term", '
            '"expanded_terms": ["reinforcement learning", "reward shaping"]}'
        )
        rewriter = QueryRewriter(provider_factory=lambda: mock_provider)
        result = rewriter.rewrite("RL reward")
        self.assertEqual(result.rewritten, "reinforcement learning reward shaping")
        self.assertTrue(result.was_rewritten)
        self.assertIn("reinforcement learning", result.expanded_terms)

    def test_llm_failure_falls_back_to_rule(self):
        """If LLM raises, fall back to rule-based rewrite."""
        mock_provider = MagicMock()
        mock_provider.chat.side_effect = Exception("API error")
        rewriter = QueryRewriter(provider_factory=lambda: mock_provider)
        result = rewriter.rewrite("GNN")
        # Should still do rule-based expansion
        self.assertIn("graph neural network", result.rewritten.lower())

    def test_result_serializable(self):
        """RewriteResult should be easily serializable."""
        result = RewriteResult(
            original="test",
            rewritten="test query",
            was_rewritten=True,
            explanation="Added query",
            expanded_terms=["query"],
        )
        d = asdict(result)
        self.assertEqual(d["original"], "test")
        self.assertTrue(d["was_rewritten"])


class TestAbbreviationExpansion(unittest.TestCase):
    def test_common_ml_abbreviations(self):
        rewriter = QueryRewriter(provider_factory=lambda: None)

        cases = {
            "RL": "reinforcement learning",
            "NLP": "natural language processing",
            "CV": "computer vision",
            "GAN": "generative adversarial network",
            "LLM": "large language model",
            "CNN": "convolutional neural network",
            "RNN": "recurrent neural network",
            "VAE": "variational autoencoder",
        }
        for abbr, expansion in cases.items():
            result = rewriter.rewrite(abbr)
            self.assertIn(
                expansion,
                result.rewritten.lower(),
                f"Expected '{expansion}' in rewrite of '{abbr}', got '{result.rewritten}'",
            )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_query_rewriter.py -v`
Expected: FAIL -- module does not exist.

- [ ] **Step 3: Implement QueryRewriter**

```python
# app/services/query_rewriter.py
"""Optional LLM-powered query rewriting with rule-based fallback.

No LLM = no rewrite (local-first principle). The rule-based path
handles common abbreviation expansion only.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Callable, Optional

from app.services.ai_providers import NoProvider


@dataclass(frozen=True)
class RewriteResult:
    original: str
    rewritten: str
    was_rewritten: bool = False
    explanation: str = ""
    expanded_terms: list[str] = field(default_factory=list)


# Common ML/AI abbreviations for rule-based expansion
ABBREVIATIONS: dict[str, str] = {
    "RL": "reinforcement learning",
    "NLP": "natural language processing",
    "CV": "computer vision",
    "GAN": "generative adversarial network",
    "GANs": "generative adversarial networks",
    "GNN": "graph neural network",
    "GNNs": "graph neural networks",
    "LLM": "large language model",
    "LLMs": "large language models",
    "CNN": "convolutional neural network",
    "CNNs": "convolutional neural networks",
    "RNN": "recurrent neural network",
    "RNNs": "recurrent neural networks",
    "VAE": "variational autoencoder",
    "VAEs": "variational autoencoders",
    "BERT": "bidirectional encoder representations from transformers",
    "GPT": "generative pre-trained transformer",
    "RAG": "retrieval augmented generation",
    "RLHF": "reinforcement learning from human feedback",
    "DRL": "deep reinforcement learning",
    "DL": "deep learning",
    "ML": "machine learning",
    "FL": "federated learning",
    "MoE": "mixture of experts",
    "LoRA": "low-rank adaptation",
    "SFT": "supervised fine-tuning",
    "PEFT": "parameter-efficient fine-tuning",
    "ICL": "in-context learning",
    "CoT": "chain of thought",
    "ToT": "tree of thought",
    "KG": "knowledge graph",
    "KGs": "knowledge graphs",
}


class QueryRewriter:
    """Rewrite search queries for better academic search results.

    Uses LLM when available, falls back to rule-based abbreviation expansion.
    """

    def __init__(
        self,
        *,
        provider_factory: Optional[Callable] = None,
    ):
        self._provider_factory = provider_factory

    def rewrite(self, raw_query: str, context: Optional[dict] = None) -> RewriteResult:
        """Rewrite a search query.

        Returns RewriteResult with original, rewritten, and metadata.
        If no rewrite is needed, rewritten == original and was_rewritten is False.
        """
        raw_query = str(raw_query or "").strip()
        if not raw_query:
            return RewriteResult(original=raw_query, rewritten=raw_query)

        # Try LLM rewrite first
        llm_result = self._llm_rewrite(raw_query, context or {})
        if llm_result is not None:
            return llm_result

        # Fall back to rule-based
        return self._rule_based_rewrite(raw_query)

    def _llm_rewrite(self, query: str, context: dict) -> Optional[RewriteResult]:
        """Attempt LLM-powered rewrite. Returns None if no LLM available."""
        if self._provider_factory is None:
            return None
        try:
            provider = self._provider_factory()
            if provider is None or isinstance(provider, NoProvider):
                return None
            if not hasattr(provider, "chat"):
                return None

            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a search query rewriter for an academic paper search system. "
                        "Given a user's search query, rewrite it to improve search results. "
                        "Strategies: expand abbreviations, add synonyms, convert natural "
                        "language to academic keywords. Return JSON with keys: "
                        "rewritten (the improved query string), "
                        "explanation (brief reason for changes), "
                        "expanded_terms (list of terms you added or expanded). "
                        "If the query is already good, return it unchanged with "
                        "explanation 'No rewrite needed' and empty expanded_terms."
                    ),
                },
                {"role": "user", "content": query},
            ]

            content = provider.chat(messages, page_context=context)
            return self._parse_llm_response(query, content)

        except Exception:
            return None

    @staticmethod
    def _parse_llm_response(original: str, content: str) -> Optional[RewriteResult]:
        """Parse LLM response JSON into RewriteResult."""
        try:
            text = str(content or "").strip()
            # Try direct parse
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                # Extract JSON from markdown code blocks or mixed text
                start = text.find("{")
                end = text.rfind("}")
                if start == -1 or end <= start:
                    return None
                parsed = json.loads(text[start : end + 1])

            rewritten = str(parsed.get("rewritten") or original).strip()
            explanation = str(parsed.get("explanation") or "").strip()
            expanded = parsed.get("expanded_terms") or []
            if not isinstance(expanded, list):
                expanded = []
            expanded = [str(t) for t in expanded if t]

            was_rewritten = rewritten.lower() != original.lower()
            return RewriteResult(
                original=original,
                rewritten=rewritten,
                was_rewritten=was_rewritten,
                explanation=explanation,
                expanded_terms=expanded,
            )
        except (json.JSONDecodeError, KeyError, TypeError):
            return None

    @staticmethod
    def _rule_based_rewrite(query: str) -> RewriteResult:
        """Rule-based abbreviation expansion.

        Expands known ML/AI abbreviations found as whole words in the query.
        """
        tokens = query.split()
        expanded_terms: list[str] = []
        new_tokens: list[str] = []

        for token in tokens:
            clean = token.strip(".,;:!?()[]{}\"'")
            if clean in ABBREVIATIONS:
                expansion = ABBREVIATIONS[clean]
                # Keep format: "GNN" -> "graph neural network OR GNN"
                new_tokens.append(f"{expansion} OR {clean}")
                expanded_terms.append(expansion)
            else:
                new_tokens.append(token)

        rewritten = " ".join(new_tokens)
        was_rewritten = rewritten != query

        return RewriteResult(
            original=query,
            rewritten=rewritten,
            was_rewritten=was_rewritten,
            explanation="Abbreviation expansion" if was_rewritten else "",
            expanded_terms=expanded_terms,
        )
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_query_rewriter.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/query_rewriter.py tests/test_query_rewriter.py
git commit -m "feat(search): add QueryRewriter with LLM and rule-based abbreviation expansion"
```

---

### Task 4: Session-Aware AgentService Rewrite

**Files:**
- Rewrite: `app/services/agent_service.py`

- [ ] **Step 1: Add AgentService tests to test_agent_sessions.py**

Append to `tests/test_agent_sessions.py`:

```python
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
        # Should have at least user + assistant messages
        roles = [m["role"] for m in messages]
        self.assertIn("user", roles)
        self.assertIn("assistant", roles)

    def test_auto_title_on_first_message(self):
        result = self.service.handle_message(
            "Find papers about federated learning",
            session_id=None,
        )
        session = self.store.get_agent_session(result["session"]["id"])
        # Auto-title should be set (not "New Session")
        self.assertNotEqual(session["title"], "New Session")

    def test_context_includes_history(self):
        session = self.store.create_agent_session()
        self.service.handle_message("search GNN", session_id=session["id"])
        # Second message should have history context
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
        # Session must have id, title, message_count
        self.assertIn("id", result["session"])
        self.assertIn("title", result["session"])
        self.assertIn("message_count", result["session"])

    def test_safety_policy_preserved(self):
        result = self.service.handle_message("delete all papers")
        self.assertTrue(result.get("requires_confirmation", False))
```

- [ ] **Step 2: Run tests to verify failures**

Run: `python -m pytest tests/test_agent_sessions.py::TestSessionAwareAgentService -v`
Expected: FAIL -- current `handle_message` has no `session_id` parameter.

- [ ] **Step 3: Rewrite AgentService**

Replace `app/services/agent_service.py` with:

```python
"""Paper Agent service layer — session-aware with multi-step execution.

The Agent plans from the current page context + conversation history,
then executes local tools through StateStore/services. Provider-backed
planning is an optional enhancement; deterministic fallback remains
the offline path.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import quote

from app.services.ai_providers import NoProvider, ProviderError, build_ai_provider_from_env


DESTRUCTIVE_TERMS = ("delete", "remove all", "overwrite api key", "bulk archive", "clear all")

VALID_INTENTS = frozenset({
    "answer", "search", "save", "skim", "deep_read", "watch",
    "collection", "planner", "analysis", "summarize", "recommendations",
})


@dataclass(frozen=True)
class AgentPlan:
    intent: str
    query: str = ""
    status: str = ""
    steps: list[dict] = field(default_factory=list)


class AgentSafetyPolicy:
    """Centralized confirmation policy for Agent-executed actions."""

    @staticmethod
    def requires_confirmation(message: str, plan: AgentPlan) -> bool:
        text = str(message or "").lower()
        if any(term in text for term in DESTRUCTIVE_TERMS):
            return True
        return plan.intent in {"delete", "bulk_archive", "overwrite_api_key"}


class AgentService:
    def __init__(self, state_store, *, provider_factory=build_ai_provider_from_env):
        self.state_store = state_store
        self.provider_factory = provider_factory
        self.safety = AgentSafetyPolicy()

    def handle_message(
        self,
        message: str,
        session_id: Optional[str] = None,
        page_context: Optional[dict] = None,
    ) -> dict:
        """Handle a user message within a session context.

        If session_id is None, creates a new session automatically.
        Persists both user and assistant messages to the session.
        Returns response dict including session metadata.
        """
        page_context = page_context or {}
        message = str(message or "").strip()

        # Resolve or create session
        session = self._resolve_session(session_id)
        session_id = session["id"]

        # Load conversation history for context
        history = self.state_store.get_session_messages(session_id, limit=20)
        is_first_message = len(history) == 0

        # Plan and execute
        tool_results: list[dict] = []
        actions: list[dict] = []
        state_updates: dict = {}

        plan = self._plan(message, page_context, tool_results, history)

        if self.safety.requires_confirmation(message, plan):
            reply = "That action needs confirmation before I run it."
            self._persist_turn(session_id, message, reply, {"confirmation": "required"})
            return self._response(
                reply,
                session=self._fresh_session(session_id),
                actions=[{"type": "confirmation", "status": "required"}],
                requires_confirmation=True,
                tool_results=tool_results,
            )

        # Execute the plan
        result = self._execute(plan, message, page_context, tool_results, actions, state_updates)

        # Persist messages
        metadata = {
            "tool_results": tool_results,
            "actions": actions,
            "state_updates": state_updates,
        }
        self._persist_turn(session_id, message, result, metadata)

        # Auto-title on first message
        if is_first_message:
            self._auto_title(session_id, message)

        return self._response(
            result,
            session=self._fresh_session(session_id),
            actions=actions,
            state_updates=state_updates,
            tool_results=tool_results,
        )

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def _resolve_session(self, session_id: Optional[str]) -> dict:
        """Get existing session or create a new one."""
        if session_id:
            session = self.state_store.get_agent_session(session_id)
            if session:
                return session
        return self.state_store.create_agent_session()

    def _fresh_session(self, session_id: str) -> dict:
        """Reload session to get updated counts."""
        session = self.state_store.get_agent_session(session_id)
        if not session:
            return {"id": session_id, "title": "Unknown", "message_count": 0}
        return {
            "id": session["id"],
            "title": session["title"],
            "message_count": session["message_count"],
            "last_active": session.get("last_active", ""),
        }

    def _persist_turn(self, session_id: str, user_msg: str, reply: str, metadata: dict) -> None:
        """Save user message and assistant reply to the session."""
        self.state_store.add_agent_message(session_id, "user", user_msg)
        self.state_store.add_agent_message(session_id, "assistant", reply, metadata=metadata)

    def _auto_title(self, session_id: str, first_message: str) -> None:
        """Generate a session title from the first message.

        Uses LLM when available, falls back to truncation.
        """
        # Truncation fallback
        title = first_message[:50].strip()
        if len(first_message) > 50:
            # Cut at last word boundary
            space = title.rfind(" ")
            if space > 20:
                title = title[:space]
            title += "..."

        # Try LLM title generation
        try:
            provider = self.provider_factory()
            if not isinstance(provider, NoProvider) and hasattr(provider, "chat"):
                llm_title = provider.chat(
                    [
                        {
                            "role": "system",
                            "content": (
                                "Generate a concise title (max 40 characters) for a research "
                                "assistant conversation. Return ONLY the title text, no quotes, "
                                "no explanation. The title should summarize the user's intent."
                            ),
                        },
                        {"role": "user", "content": first_message},
                    ],
                    page_context={},
                )
                llm_title = str(llm_title or "").strip().strip('"').strip("'")
                if 3 <= len(llm_title) <= 60:
                    title = llm_title
        except Exception:
            pass  # Keep truncation fallback

        self.state_store.update_agent_session(session_id, title=title)

    # ------------------------------------------------------------------
    # Planning
    # ------------------------------------------------------------------

    def _plan(
        self,
        message: str,
        page_context: dict,
        tool_results: list[dict],
        history: list[dict],
    ) -> AgentPlan:
        fallback = self._fallback_plan(message, page_context)
        if fallback.intent != "answer":
            return fallback
        provider_plan = self._provider_plan(message, page_context, tool_results, history)
        if provider_plan:
            return provider_plan
        return fallback

    def _provider_plan(
        self,
        message: str,
        page_context: dict,
        tool_results: list[dict],
        history: list[dict],
    ) -> AgentPlan | None:
        try:
            provider = self.provider_factory()
            if isinstance(provider, NoProvider) or not hasattr(provider, "chat"):
                return None

            # Build context-aware messages for planning
            messages = [
                {
                    "role": "system",
                    "content": (
                        "Classify a Paper Agent user request. Return JSON only with keys "
                        "intent and query. Valid intents: answer, search, save, skim, "
                        "deep_read, watch, collection, planner, analysis, summarize, "
                        "recommendations. Do not execute tools."
                    ),
                },
                {"role": "system", "content": json.dumps(page_context, ensure_ascii=False, sort_keys=True)},
            ]

            # Add recent history for context
            for msg in history[-6:]:
                role = msg.get("role", "user")
                if role in ("user", "assistant"):
                    messages.append({"role": role, "content": msg.get("content", "")})

            messages.append({"role": "user", "content": message})

            content = provider.chat(messages, page_context=page_context)
            parsed = self._extract_json(content)
            intent = str(parsed.get("intent") or "").strip().lower()
            if intent in VALID_INTENTS:
                tool_results.append({
                    "tool": "plan_intent",
                    "status": "succeeded",
                    "model": getattr(provider, "model_name", "provider"),
                })
                return AgentPlan(intent=intent, query=str(parsed.get("query") or "").strip())
        except (json.JSONDecodeError, KeyError, TypeError):
            return None
        except Exception as exc:
            tool_results.append({"tool": "plan_intent", "status": "degraded", "error": str(exc)})
        return None

    @staticmethod
    def _extract_json(content: str) -> dict:
        text = str(content or "").strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end > start:
                return json.loads(text[start : end + 1])
            raise

    @staticmethod
    def _fallback_plan(message: str, page_context: dict) -> AgentPlan:
        text = str(message or "").lower()
        if "recommend" in text or "推荐" in text:
            return AgentPlan("recommendations")
        if "collection" in text or "collect this" in text:
            return AgentPlan("collection")
        if any(word in text for word in ("summarize", "summary", "what is this paper", "总结")):
            return AgentPlan("summarize")
        if any(word in text for word in ("analysis", "analyze", "analyse", "分析")):
            return AgentPlan("analysis")
        if any(word in text for word in ("save", "saved", "keep", "收藏", "保存")):
            return AgentPlan("save")
        if any(word in text for word in ("deep read", "deepread", "精读")):
            return AgentPlan("deep_read")
        if any(word in text for word in ("skim", "later", "稍后")):
            return AgentPlan("skim")
        if any(word in text for word in ("watch", "subscribe", "monitor", "追踪", "监控")):
            return AgentPlan("watch", query=str(page_context.get("query") or message).strip())
        if any(word in text for word in ("planner", "plan")):
            return AgentPlan("planner")
        if any(word in text for word in ("search", "find", "look for", "检索", "搜索", "查找")):
            query = message
            for token in ("search", "find", "look for", "检索", "搜索", "查找"):
                query = query.replace(token, " ")
            return AgentPlan("search", query=" ".join(query.split()))
        return AgentPlan("answer")

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def _execute(
        self,
        plan: AgentPlan,
        message: str,
        page_context: dict,
        tool_results: list[dict],
        actions: list[dict],
        state_updates: dict,
    ) -> str:
        """Execute a plan and return the reply text."""
        selected_paper_id = str(page_context.get("selected_paper_id") or "").strip()
        selected_title = str(
            page_context.get("selected_paper_title") or selected_paper_id or "this paper"
        )

        if plan.intent in {"save", "deep_read", "skim"} and selected_paper_id:
            return self._exec_queue(plan, selected_paper_id, selected_title, message, actions, tool_results)

        if plan.intent == "collection" and selected_paper_id:
            return self._create_collection(message, page_context, selected_paper_id, selected_title, actions, tool_results)

        if plan.intent == "watch":
            return self._exec_watch(plan, page_context, message, actions, tool_results)

        if plan.intent == "search":
            return self._exec_search(plan, page_context, actions, tool_results, state_updates)

        if plan.intent == "recommendations":
            state_updates["navigate"] = "/recommendations"
            actions.append({"type": "navigate", "target": "recommendations"})
            tool_results.append({"tool": "open_recommendations", "status": "scheduled"})
            return "Opening the **Recommendations** workspace."

        if plan.intent == "planner":
            return (
                "Planner execution is available from a research question workspace. "
                "Create or select a question first."
            )

        if plan.intent == "analysis" and selected_paper_id:
            actions.append({"type": "analysis", "paper_id": selected_paper_id, "status": "available_on_detail"})
            state_updates["navigate"] = f"/papers/{quote(selected_paper_id)}"
            tool_results.append({"tool": "generate_paper_analysis", "status": "scheduled", "paper_id": selected_paper_id})
            return f"I can generate analysis for **{selected_title}** on the detail page."

        if plan.intent == "summarize" and selected_paper_id:
            return self._summarize_selected_paper(selected_paper_id, selected_title, actions, tool_results)

        return self._answer_chat(message, page_context, tool_results)

    def _exec_queue(self, plan, paper_id, title, message, actions, tool_results) -> str:
        status = {"save": "Saved", "deep_read": "Deep Read", "skim": "Skim Later"}[plan.intent]
        self.state_store.upsert_queue_item(
            paper_id, status,
            source="paper_agent",
            decision_context=f"Paper Agent request: {message}",
        )
        actions.append({"type": "queue", "paper_id": paper_id, "status": status})
        tool_results.append({
            "tool": "mark_reading_decision", "status": "succeeded",
            "paper_id": paper_id, "decision": status,
        })
        return f"Marked **{title}** as **{status}**."

    def _exec_watch(self, plan, page_context, message, actions, tool_results) -> str:
        query = plan.query or str(page_context.get("query") or message).strip()
        sub = self.state_store.create_subscription(
            "query",
            query[:48] or "Paper Agent watch",
            query,
            payload_json={"source": "paper_agent", "description": "Created by Paper Agent"},
        )
        actions.append({"type": "watch", "subscription_id": sub["id"], "query": query})
        tool_results.append({"tool": "create_watch", "status": "succeeded", "subscription_id": sub["id"], "query": query})
        return f"Watching **{query}**."

    def _exec_search(self, plan, page_context, actions, tool_results, state_updates) -> str:
        query = plan.query or str(page_context.get("query") or "").strip()
        actions.append({"type": "search", "query": query})
        tool_results.append({"tool": "search_papers", "status": "scheduled", "query": query})
        state_updates["navigate"] = f"/?q={quote(query)}" if query else "/"
        return f"Searching for **{query}**." if query else "Tell me what to search for."

    # ------------------------------------------------------------------
    # Tool implementations
    # ------------------------------------------------------------------

    def _create_collection(self, message, page_context, selected_paper_id, selected_title, actions, tool_results):
        query = str(page_context.get("query") or "").strip()
        base_name = query[:48] if query else selected_title[:48]
        name = base_name or "Paper Agent collection"
        collection = None
        for suffix in ("", " collection", f" {selected_paper_id[-6:]}"):
            try:
                collection = self.state_store.create_collection(
                    (name + suffix).strip()[:72],
                    description=f"Created by Paper Agent from {selected_title}.",
                    query_text=query,
                )
                break
            except Exception:
                collection = None
        if collection is None:
            tool_results.append({"tool": "create_collection", "status": "failed", "error": "duplicate_collection"})
            return "I could not create a collection because a matching collection already exists."
        self.state_store.add_paper_to_collection(
            collection["id"], selected_paper_id,
            note=f"Added by Paper Agent from request: {message}",
        )
        actions.append({"type": "collection", "collection_id": collection["id"], "paper_id": selected_paper_id})
        tool_results.append({
            "tool": "create_collection", "status": "succeeded",
            "collection_id": collection["id"], "paper_id": selected_paper_id,
        })
        return f'Created collection **{collection["name"]}** and added **{selected_title}**.'

    def _summarize_selected_paper(self, selected_paper_id, selected_title, actions, tool_results):
        metadata = {}
        getter = getattr(self.state_store, "get_paper_metadata", None)
        if callable(getter):
            metadata = getter(selected_paper_id) or {}
        abstract = str(metadata.get("abstract") or metadata.get("summary") or "").strip()
        if abstract:
            summary = abstract[:900] + ("..." if len(abstract) > 900 else "")
            reply = f"### {selected_title}\n\n{summary}"
        else:
            reply = f"I do not have an abstract for **{selected_title}** yet."
        actions.append({"type": "summary", "paper_id": selected_paper_id})
        tool_results.append({"tool": "summarize_selected_paper", "status": "succeeded", "paper_id": selected_paper_id})
        return reply

    def _answer_chat(self, message: str, page_context: dict, tool_results: list[dict]) -> str:
        try:
            provider = self.provider_factory()
            if not isinstance(provider, NoProvider) and hasattr(provider, "chat"):
                reply = provider.chat(
                    self._chat_messages(message, page_context),
                    page_context=page_context,
                )
                if reply:
                    tool_results.append({
                        "tool": "chat", "status": "succeeded",
                        "model": getattr(provider, "model_name", "provider"),
                    })
                    return reply
        except (ProviderError, Exception) as exc:
            tool_results.append({"tool": "chat", "status": "degraded", "error": str(exc)})
        return self._fallback_chat_reply(message, page_context)

    @staticmethod
    def _chat_messages(message: str, page_context: dict) -> list[dict]:
        route = str(page_context.get("route") or "/")
        query = str(page_context.get("query") or "").strip()
        selected_title = str(page_context.get("selected_paper_title") or "").strip()
        context_lines = [f"Current route: {route}"]
        if query:
            context_lines.append(f"Current search query: {query}")
        if selected_title:
            context_lines.append(f"Selected paper: {selected_title}")
        return [
            {
                "role": "system",
                "content": (
                    "You are Paper Agent, a concise research assistant inside a local-first "
                    "paper discovery workspace. Use Markdown when it improves readability. "
                    "Help with literature search strategy, paper triage, and current page context."
                ),
            },
            {"role": "system", "content": "\n".join(context_lines)},
            {"role": "user", "content": message},
        ]

    @staticmethod
    def _fallback_chat_reply(message: str, page_context: dict) -> str:
        text = message.lower()
        route = str(page_context.get("route") or "/")
        query = str(page_context.get("query") or "").strip()
        if any(token in text for token in ("你好", "hello", "hi", "hey")):
            return (
                "你好，我是 **Paper Agent**。\n\n"
                "你可以让我：\n"
                "- search papers\n"
                "- save the selected paper\n"
                "- mark it for skim or deep read\n"
                "- create a watch\n"
                "- create a collection\n"
                "- summarize the selected paper"
            )
        if "怎么" in text or "what can" in text or "help" in text:
            location = "Search" if route == "/" else route.strip("/").title() or "Search"
            return (
                f"Paper Agent can help from the current **{location}** page.\n\n"
                "Try: `search federated learning`, `save this paper`, "
                "`deep read this paper`, `create watch for this query`, or "
                "`summarize this paper`."
            )
        if query:
            return (
                f"Paper Agent is looking at **{query}**. I can refine the query, "
                "save promising papers, create a watch, or summarize the selected paper."
            )
        return (
            "Paper Agent can chat about your research workflow and execute local actions: "
            "search papers, save papers, mark reading decisions, create watches, create "
            "collections, and summarize selected papers."
        )

    @staticmethod
    def _response(
        reply: str,
        *,
        session: Optional[dict] = None,
        actions: Optional[list[dict]] = None,
        state_updates: Optional[dict] = None,
        tool_results: Optional[list[dict]] = None,
        requires_confirmation: bool = False,
    ) -> dict:
        return {
            "success": True,
            "reply": reply,
            "messages": [{"role": "assistant", "content": reply}],
            "actions": actions or [],
            "state_updates": state_updates or {},
            "requires_confirmation": requires_confirmation,
            "confirmation_token": "required" if requires_confirmation else "",
            "tool_results": tool_results or [],
            "session": session or {},
        }
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_agent_sessions.py -v`
Expected: ALL PASS

- [ ] **Step 5: Run full test suite for regressions**

Run: `python -m pytest -q`
Expected: All pass. If existing agent tests fail due to the new `session_id` parameter, they should still work since `session_id` defaults to `None`.

- [ ] **Step 6: Commit**

```bash
git add app/services/agent_service.py tests/test_agent_sessions.py
git commit -m "feat(agent): rewrite AgentService with session-aware multi-turn context and auto-title"
```

---

### Task 5: Agent REST API — Sessions CRUD + Messages

**Files:**
- Rewrite: `app/routes/api/agent.py`

- [ ] **Step 1: Add API tests to test_agent_sessions.py**

Append to `tests/test_agent_sessions.py`:

```python
import json as json_mod
from unittest.mock import patch


class TestAgentAPI(unittest.TestCase):
    """Test Agent REST API endpoints using Flask test client."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        # Patch the state store path
        self.store = StateStore(db_path=self.tmp.name)
        self._patcher = patch(
            "app.routes.api.helpers._current_state_store",
            return_value=self.store,
        )
        self._patcher.start()
        from web_server import create_app
        self.app = create_app()
        self.client = self.app.test_client()

    def tearDown(self):
        self._patcher.stop()
        os.unlink(self.tmp.name)

    def test_create_session(self):
        resp = self.client.post(
            "/api/agent/sessions",
            json={"title": "Test Session"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["session"]["title"], "Test Session")

    def test_list_sessions(self):
        self.store.create_agent_session(title="Session A")
        self.store.create_agent_session(title="Session B")
        resp = self.client.get("/api/agent/sessions")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(len(data["sessions"]), 2)

    def test_get_session_with_messages(self):
        session = self.store.create_agent_session(title="Detail Test")
        self.store.add_agent_message(session["id"], "user", "Hello")
        self.store.add_agent_message(session["id"], "assistant", "Hi!")
        resp = self.client.get(f"/api/agent/sessions/{session['id']}")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(len(data["messages"]), 2)

    def test_get_nonexistent_session_404(self):
        resp = self.client.get("/api/agent/sessions/nonexistent")
        self.assertEqual(resp.status_code, 404)

    def test_update_session(self):
        session = self.store.create_agent_session()
        resp = self.client.put(
            f"/api/agent/sessions/{session['id']}",
            json={"title": "Updated", "is_pinned": True},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["session"]["title"], "Updated")

    def test_delete_session(self):
        session = self.store.create_agent_session()
        resp = self.client.delete(f"/api/agent/sessions/{session['id']}")
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(self.store.get_agent_session(session["id"]))

    def test_send_message(self):
        session = self.store.create_agent_session()
        resp = self.client.post(
            f"/api/agent/sessions/{session['id']}/messages",
            json={"message": "hello", "page_context": {}},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertIn("reply", data)
        self.assertIn("session", data)

    def test_send_message_creates_session_when_no_id(self):
        resp = self.client.post(
            "/api/agent/sessions/new/messages",
            json={"message": "search GNN papers"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("session", data)
        self.assertIsNotNone(data["session"]["id"])
```

- [ ] **Step 2: Run tests to verify failures**

Run: `python -m pytest tests/test_agent_sessions.py::TestAgentAPI -v`
Expected: FAIL -- new API endpoints don't exist.

- [ ] **Step 3: Rewrite agent API routes**

Replace `app/routes/api/agent.py` with:

```python
"""Paper Agent assistant API — session-based conversation endpoints."""

from __future__ import annotations

from flask import jsonify, request

from . import bp
from .helpers import _current_state_store
from app.services.agent_service import AgentService
from app.services.ai_providers import build_ai_provider_from_env


def _agent_service():
    return AgentService(
        _current_state_store(),
        provider_factory=build_ai_provider_from_env,
    )


# ------------------------------------------------------------------
# Session CRUD
# ------------------------------------------------------------------

@bp.post("/api/agent/sessions")
def create_agent_session():
    """Create a new agent session."""
    data = request.get_json() or {}
    title = str(data.get("title", "New Session") or "New Session").strip()
    store = _current_state_store()
    session = store.create_agent_session(title=title)
    return jsonify({"success": True, "session": session})


@bp.get("/api/agent/sessions")
def list_agent_sessions():
    """List agent sessions. Query params: archived (0|1), limit (int)."""
    store = _current_state_store()
    archived_param = request.args.get("archived")
    archived = None
    if archived_param is not None:
        archived = archived_param in ("1", "true", "True")
    limit = int(request.args.get("limit", 20))
    sessions = store.list_agent_sessions(archived=archived, limit=limit)
    return jsonify({"success": True, "sessions": sessions})


@bp.get("/api/agent/sessions/<session_id>")
def get_agent_session(session_id: str):
    """Get a session with its message history."""
    store = _current_state_store()
    session = store.get_agent_session(session_id)
    if not session:
        return jsonify({"success": False, "error": "Session not found"}), 404
    limit = int(request.args.get("limit", 50))
    messages = store.get_session_messages(session_id, limit=limit)
    return jsonify({"success": True, "session": session, "messages": messages})


@bp.put("/api/agent/sessions/<session_id>")
def update_agent_session(session_id: str):
    """Update session title, pin, or archive status."""
    store = _current_state_store()
    data = request.get_json() or {}

    kwargs = {}
    if "title" in data:
        kwargs["title"] = str(data["title"] or "").strip()
    if "is_pinned" in data:
        kwargs["is_pinned"] = bool(data["is_pinned"])
    if "is_archived" in data:
        kwargs["is_archived"] = bool(data["is_archived"])
    if "summary" in data:
        kwargs["summary"] = str(data["summary"] or "").strip()

    session = store.update_agent_session(session_id, **kwargs)
    if not session:
        return jsonify({"success": False, "error": "Session not found"}), 404
    return jsonify({"success": True, "session": session})


@bp.delete("/api/agent/sessions/<session_id>")
def delete_agent_session(session_id: str):
    """Delete a session and its messages."""
    store = _current_state_store()
    deleted = store.delete_agent_session(session_id)
    if not deleted:
        return jsonify({"success": False, "error": "Session not found"}), 404
    return jsonify({"success": True})


# ------------------------------------------------------------------
# Messages
# ------------------------------------------------------------------

@bp.post("/api/agent/sessions/<session_id>/messages")
def send_agent_message(session_id: str):
    """Send a message in a session. Use session_id='new' to auto-create."""
    data = request.get_json() or {}
    message = str(data.get("message", "") or "").strip()
    page_context = data.get("page_context") or {}

    effective_session_id = None if session_id in ("new", "auto") else session_id

    service = _agent_service()
    result = service.handle_message(
        message,
        session_id=effective_session_id,
        page_context=page_context,
    )
    return jsonify(result)


# ------------------------------------------------------------------
# Legacy compatibility endpoint
# ------------------------------------------------------------------

@bp.post("/api/agent/messages")
def agent_message_legacy():
    """Legacy single-message endpoint. Creates a transient session."""
    data = request.get_json() or {}
    service = _agent_service()
    return jsonify(service.handle_message(
        str(data.get("message", "") or "").strip(),
        page_context=data.get("page_context") or {},
    ))
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_agent_sessions.py::TestAgentAPI -v`
Expected: ALL PASS (some tests may be skipped if `create_app` is not importable -- adjust import path as needed).

- [ ] **Step 5: Run full test suite**

Run: `python -m pytest -q`
Expected: All existing agent tests still pass via the legacy `/api/agent/messages` endpoint.

- [ ] **Step 6: Commit**

```bash
git add app/routes/api/agent.py tests/test_agent_sessions.py
git commit -m "feat(api): add agent session CRUD + message endpoints with legacy compatibility"
```

---

### Task 6: Preact Agent Panel — Package Setup + Build Config

**Files:**
- Modify: `package.json`
- Modify: `vite.config.ts`
- Modify: `tsconfig.json`
- Create: `frontend/agent-panel/types.ts`
- Create: `frontend/agent-panel/api.ts`

- [ ] **Step 1: Update package.json for Preact**

Replace `package.json`:

```json
{
  "name": "paper-agent",
  "version": "2.0.0",
  "private": true,
  "type": "module",
  "scripts": {
    "build": "vite build",
    "build:watch": "vite build --watch",
    "lint": "tsc --noEmit"
  },
  "dependencies": {
    "preact": "^10.25.4",
    "marked": "^15.0.6"
  },
  "devDependencies": {
    "@preact/preset-vite": "^2.9.4",
    "typescript": "^5.9.3",
    "vite": "^7.2.6"
  }
}
```

- [ ] **Step 2: Update vite.config.ts for Preact**

Replace `vite.config.ts`:

```typescript
import { defineConfig } from "vite";
import preact from "@preact/preset-vite";

export default defineConfig({
  plugins: [preact()],
  build: {
    outDir: "static/dist",
    emptyOutDir: true,
    sourcemap: false,
    rollupOptions: {
      input: "frontend/agent-panel/index.tsx",
      output: {
        entryFileNames: "agent-panel.js",
        chunkFileNames: "agent-panel-[hash].js",
        assetFileNames: (assetInfo) => {
          if (assetInfo.name && assetInfo.name.endsWith(".css")) {
            return "agent-panel.css";
          }
          return "agent-panel-[name][extname]";
        },
      },
    },
    target: "es2020",
    minify: "esbuild",
  },
});
```

- [ ] **Step 3: Update tsconfig.json for Preact**

Replace `tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "useDefineForClassFields": true,
    "lib": ["DOM", "DOM.Iterable", "ES2022"],
    "allowJs": false,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "allowSyntheticDefaultImports": true,
    "strict": true,
    "forceConsistentCasingInFileNames": true,
    "module": "ESNext",
    "moduleResolution": "Node",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "jsxImportSource": "preact"
  },
  "include": ["frontend/agent-panel/**/*.ts", "frontend/agent-panel/**/*.tsx"]
}
```

- [ ] **Step 4: Create type definitions**

```typescript
// frontend/agent-panel/types.ts

export type MessageRole = "user" | "assistant" | "system" | "tool";

export interface AgentMessage {
  id: number;
  session_id: string;
  role: MessageRole;
  content: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface AgentSession {
  id: string;
  title: string;
  summary: string;
  is_pinned: number;
  is_archived: number;
  message_count: number;
  last_active: string;
  created_at: string;
  updated_at: string;
}

export interface ToolResult {
  tool?: string;
  status?: string;
  error?: string;
  [key: string]: unknown;
}

export interface AgentAction {
  type?: string;
  paper_id?: string;
  status?: string;
  query?: string;
  [key: string]: unknown;
}

export interface AgentResponse {
  success: boolean;
  reply?: string;
  messages?: Array<{ role: MessageRole; content: string }>;
  actions?: AgentAction[];
  tool_results?: ToolResult[];
  state_updates?: { navigate?: string };
  requires_confirmation?: boolean;
  session?: {
    id: string;
    title: string;
    message_count: number;
    last_active?: string;
  };
}

export interface PageContext {
  route: string;
  query: string;
  selected_paper_id: string;
  selected_paper_title: string;
  visible_result_ids: string[];
}
```

- [ ] **Step 5: Create API client**

```typescript
// frontend/agent-panel/api.ts
import type { AgentSession, AgentMessage, AgentResponse } from "./types";

const BASE = "/api/agent";

async function request<T>(url: string, init: RequestInit = {}): Promise<T> {
  const resp = await fetch(url, init);
  const payload = await resp.json().catch(() => ({}));
  if (!resp.ok || payload.success === false) {
    throw new Error(payload.error || `Request failed (${resp.status})`);
  }
  return payload;
}

export async function createSession(title?: string): Promise<AgentSession> {
  const data = await request<{ success: boolean; session: AgentSession }>(
    `${BASE}/sessions`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: title || "New Session" }),
    }
  );
  return data.session;
}

export async function listSessions(
  archived = false,
  limit = 20
): Promise<AgentSession[]> {
  const params = new URLSearchParams({
    archived: archived ? "1" : "0",
    limit: String(limit),
  });
  const data = await request<{ sessions: AgentSession[] }>(
    `${BASE}/sessions?${params}`
  );
  return data.sessions;
}

export async function getSession(
  sessionId: string
): Promise<{ session: AgentSession; messages: AgentMessage[] }> {
  return request(`${BASE}/sessions/${sessionId}`);
}

export async function updateSession(
  sessionId: string,
  updates: Partial<Pick<AgentSession, "title" | "is_pinned" | "is_archived">>
): Promise<AgentSession> {
  const data = await request<{ session: AgentSession }>(
    `${BASE}/sessions/${sessionId}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(updates),
    }
  );
  return data.session;
}

export async function deleteSession(sessionId: string): Promise<void> {
  await request(`${BASE}/sessions/${sessionId}`, { method: "DELETE" });
}

export async function sendMessage(
  sessionId: string | null,
  message: string,
  pageContext: Record<string, unknown> = {}
): Promise<AgentResponse> {
  const effectiveId = sessionId || "new";
  return request<AgentResponse>(
    `${BASE}/sessions/${effectiveId}/messages`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, page_context: pageContext }),
    }
  );
}
```

- [ ] **Step 6: Commit**

```bash
git add package.json vite.config.ts tsconfig.json frontend/agent-panel/types.ts frontend/agent-panel/api.ts
git commit -m "feat(frontend): set up Preact agent panel with build config, types, and API client"
```

---

### Task 7: Preact Agent Panel — Components + Entry Point

**Files:**
- Create: `frontend/agent-panel/index.tsx`
- Create: `frontend/agent-panel/components/SessionList.tsx`
- Create: `frontend/agent-panel/components/MessageFlow.tsx`
- Create: `frontend/agent-panel/components/AgentInput.tsx`
- Create: `frontend/agent-panel/styles/agent-panel.css`

- [ ] **Step 1: Create AgentInput component**

```tsx
// frontend/agent-panel/components/AgentInput.tsx
import { useRef } from "preact/hooks";

interface Props {
  onSend: (message: string) => void;
  disabled: boolean;
}

export function AgentInput({ onSend, disabled }: Props) {
  const inputRef = useRef<HTMLTextAreaElement>(null);

  function handleKeyDown(e: KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  function submit() {
    const el = inputRef.current;
    if (!el) return;
    const value = el.value.trim();
    if (!value || disabled) return;
    onSend(value);
    el.value = "";
    el.style.height = "auto";
  }

  function handleInput() {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 120) + "px";
  }

  return (
    <form class="ap-composer" onSubmit={(e) => { e.preventDefault(); submit(); }}>
      <textarea
        ref={inputRef}
        class="ap-composer-input"
        placeholder="Ask Paper Agent..."
        rows={1}
        disabled={disabled}
        onKeyDown={handleKeyDown}
        onInput={handleInput}
      />
      <button
        type="submit"
        class="ap-composer-send"
        disabled={disabled}
        aria-label="Send message"
      >
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <path d="M2 8h12M10 4l4 4-4 4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </button>
    </form>
  );
}
```

- [ ] **Step 2: Create MessageFlow component**

```tsx
// frontend/agent-panel/components/MessageFlow.tsx
import { useEffect, useRef } from "preact/hooks";
import { marked } from "marked";
import type { AgentMessage, ToolResult } from "../types";

interface Props {
  messages: AgentMessage[];
  busy: boolean;
}

// Configure marked for safe output
marked.setOptions({
  breaks: true,
  gfm: true,
});

function renderMarkdown(content: string): string {
  try {
    return marked.parse(content) as string;
  } catch {
    return content;
  }
}

function formatToolChip(meta: Record<string, unknown>): string[] {
  const results = (meta.tool_results || []) as ToolResult[];
  return results
    .filter((r) => r.tool && r.status)
    .map((r) => {
      const label = String(r.tool || "tool").replace(/_/g, " ");
      return `${label}: ${r.status}`;
    });
}

export function MessageFlow({ messages, busy }: Props) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, busy]);

  return (
    <div class="ap-thread">
      {messages.map((msg) => (
        <div key={msg.id} class={`ap-msg ap-msg--${msg.role}`}>
          {msg.role === "assistant" ? (
            <div
              class="ap-msg-content"
              dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.content) }}
            />
          ) : msg.role === "tool" ? (
            <div class="ap-msg-content ap-msg-tool">{msg.content}</div>
          ) : (
            <div class="ap-msg-content">{msg.content}</div>
          )}
          {msg.role === "assistant" && msg.metadata_json && (
            <div class="ap-msg-chips">
              {formatToolChip(msg.metadata_json).map((chip, i) => (
                <span key={i} class="ap-chip">{chip}</span>
              ))}
            </div>
          )}
        </div>
      ))}
      {busy && (
        <div class="ap-msg ap-msg--assistant">
          <div class="ap-msg-content ap-typing">
            <span class="ap-dot" /><span class="ap-dot" /><span class="ap-dot" />
          </div>
        </div>
      )}
      <div ref={endRef} />
    </div>
  );
}
```

- [ ] **Step 3: Create SessionList component**

```tsx
// frontend/agent-panel/components/SessionList.tsx
import type { AgentSession } from "../types";

interface Props {
  sessions: AgentSession[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onCreate: () => void;
  onPin: (id: string, pinned: boolean) => void;
  onArchive: (id: string) => void;
  onDelete: (id: string) => void;
}

function timeAgo(iso: string): string {
  if (!iso) return "";
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export function SessionList({
  sessions, activeId, onSelect, onCreate, onPin, onArchive, onDelete,
}: Props) {
  return (
    <div class="ap-sessions">
      <div class="ap-sessions-header">
        <span class="ap-sessions-title">Sessions</span>
        <button class="ap-sessions-new" onClick={onCreate} aria-label="New session">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M7 1v12M1 7h12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
        </button>
      </div>
      <div class="ap-sessions-list">
        {sessions.map((s) => (
          <div
            key={s.id}
            class={`ap-session-row ${s.id === activeId ? "is-active" : ""}`}
            onClick={() => onSelect(s.id)}
          >
            <div class="ap-session-info">
              {s.is_pinned ? <span class="ap-pin-icon" title="Pinned">*</span> : null}
              <span class="ap-session-title">{s.title}</span>
            </div>
            <div class="ap-session-meta">
              <span class="ap-session-count">{s.message_count} msgs</span>
              <span class="ap-session-time">{timeAgo(s.last_active)}</span>
            </div>
            <div class="ap-session-actions" onClick={(e) => e.stopPropagation()}>
              <button
                class="ap-session-btn"
                onClick={() => onPin(s.id, !s.is_pinned)}
                title={s.is_pinned ? "Unpin" : "Pin"}
              >
                {s.is_pinned ? "Unpin" : "Pin"}
              </button>
              <button
                class="ap-session-btn"
                onClick={() => onArchive(s.id)}
                title="Archive"
              >
                Archive
              </button>
              <button
                class="ap-session-btn ap-session-btn--danger"
                onClick={() => onDelete(s.id)}
                title="Delete"
              >
                Delete
              </button>
            </div>
          </div>
        ))}
        {sessions.length === 0 && (
          <div class="ap-sessions-empty">No sessions yet. Click + to start.</div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Create main entry point**

```tsx
// frontend/agent-panel/index.tsx
import { render } from "preact";
import { useState, useEffect, useCallback } from "preact/hooks";
import { SessionList } from "./components/SessionList";
import { MessageFlow } from "./components/MessageFlow";
import { AgentInput } from "./components/AgentInput";
import * as api from "./api";
import type { AgentSession, AgentMessage, PageContext } from "./types";
import "./styles/agent-panel.css";

declare global {
  interface Window {
    togglePaperAgent?: (open?: boolean) => void;
    paperAgentPageContext?: () => PageContext;
  }
}

function collectPageContext(): PageContext {
  const selected =
    document.querySelector<HTMLElement>(".paper-result-row.is-selected") ||
    document.querySelector<HTMLElement>("[data-paper-id]");
  const queryInput =
    (document.getElementById("paperAgentSearchInput") as HTMLInputElement | null) ||
    (document.getElementById("queryText") as HTMLInputElement | null) ||
    (document.getElementById("workspacePrompt") as HTMLInputElement | null);
  const visible = Array.from(document.querySelectorAll<HTMLElement>("[data-paper-id]"))
    .map((node) => node.dataset.paperId || "")
    .filter(Boolean)
    .slice(0, 25);
  return {
    route: window.location.pathname,
    query: queryInput ? queryInput.value : "",
    selected_paper_id: selected ? selected.dataset.paperId || "" : "",
    selected_paper_title: selected ? selected.dataset.paperTitle || "" : "",
    visible_result_ids: visible,
  };
}

function AgentPanel() {
  const [open, setOpen] = useState(false);
  const [sessionsExpanded, setSessionsExpanded] = useState(false);
  const [sessions, setSessions] = useState<AgentSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<AgentMessage[]>([]);
  const [busy, setBusy] = useState(false);
  const [panelWidth, setPanelWidth] = useState(360);

  // Expose global toggle
  useEffect(() => {
    window.togglePaperAgent = (nextOpen = true) => setOpen(Boolean(nextOpen));
    window.paperAgentPageContext = collectPageContext;

    function handleEsc(e: KeyboardEvent) {
      if (e.key === "Escape" && open) setOpen(false);
    }
    document.addEventListener("keydown", handleEsc);
    return () => document.removeEventListener("keydown", handleEsc);
  }, [open]);

  // Toggle body class
  useEffect(() => {
    document.body.classList.toggle("agent-panel-open", open);
  }, [open]);

  // Load sessions on open
  useEffect(() => {
    if (open) loadSessions();
  }, [open]);

  async function loadSessions() {
    try {
      const list = await api.listSessions(false, 20);
      setSessions(list);
    } catch {
      /* silent */
    }
  }

  async function loadSession(sessionId: string) {
    try {
      const { session, messages: msgs } = await api.getSession(sessionId);
      setActiveSessionId(session.id);
      setMessages(msgs);
      setSessionsExpanded(false);
    } catch {
      /* silent */
    }
  }

  async function createNewSession() {
    try {
      const session = await api.createSession();
      setActiveSessionId(session.id);
      setMessages([]);
      setSessionsExpanded(false);
      await loadSessions();
    } catch {
      /* silent */
    }
  }

  async function handlePin(id: string, pinned: boolean) {
    await api.updateSession(id, { is_pinned: pinned ? 1 : 0 } as any);
    await loadSessions();
  }

  async function handleArchive(id: string) {
    await api.updateSession(id, { is_archived: 1 } as any);
    if (activeSessionId === id) {
      setActiveSessionId(null);
      setMessages([]);
    }
    await loadSessions();
  }

  async function handleDelete(id: string) {
    await api.deleteSession(id);
    if (activeSessionId === id) {
      setActiveSessionId(null);
      setMessages([]);
    }
    await loadSessions();
  }

  const handleSend = useCallback(async (text: string) => {
    if (busy) return;
    setBusy(true);

    // Optimistic user message
    const tempMsg: AgentMessage = {
      id: Date.now(),
      session_id: activeSessionId || "",
      role: "user",
      content: text,
      metadata_json: {},
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempMsg]);

    try {
      const result = await api.sendMessage(
        activeSessionId,
        text,
        collectPageContext()
      );

      // Update session ID if newly created
      if (result.session?.id && !activeSessionId) {
        setActiveSessionId(result.session.id);
      }

      // Add assistant reply
      if (result.reply) {
        const assistantMsg: AgentMessage = {
          id: Date.now() + 1,
          session_id: result.session?.id || "",
          role: "assistant",
          content: result.reply,
          metadata_json: {
            tool_results: result.tool_results || [],
            actions: result.actions || [],
          },
          created_at: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, assistantMsg]);
      }

      // Handle navigation
      if (result.state_updates?.navigate) {
        window.location.href = result.state_updates.navigate;
      }

      // Dispatch queue updates
      for (const action of result.actions || []) {
        if (action.type === "queue" && action.paper_id) {
          document.dispatchEvent(
            new CustomEvent("paper-agent-queue-update", {
              detail: { paperId: action.paper_id, status: action.status },
            })
          );
        }
      }

      await loadSessions();
    } catch (err) {
      const errorMsg: AgentMessage = {
        id: Date.now() + 2,
        session_id: activeSessionId || "",
        role: "system",
        content: `Error: ${err instanceof Error ? err.message : String(err)}`,
        metadata_json: {},
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setBusy(false);
    }
  }, [activeSessionId, busy]);

  // Resize handler
  function handleResizeStart(e: MouseEvent) {
    e.preventDefault();
    const startX = e.clientX;
    const startWidth = panelWidth;

    function onMove(ev: MouseEvent) {
      const delta = startX - ev.clientX;
      setPanelWidth(Math.max(280, Math.min(600, startWidth + delta)));
    }
    function onUp() {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
    }
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  }

  return (
    <>
      {/* Floating launcher button */}
      {!open && (
        <button
          class="ap-launcher"
          onClick={() => setOpen(true)}
          aria-label="Open Paper Agent"
        >
          <svg width="20" height="20" viewBox="0 0 32 32" fill="none">
            <path d="M9 5.5h9.25L24 11.25V26.5H9z" stroke="currentColor" stroke-width="2.2" stroke-linejoin="round"/>
            <path d="M18.25 5.5v6h5.75" stroke="currentColor" stroke-width="2.2" stroke-linejoin="round"/>
            <circle cx="22.5" cy="22.5" r="2.6" fill="currentColor"/>
          </svg>
        </button>
      )}

      {/* Side panel */}
      {open && (
        <aside
          class="ap-panel"
          style={{ width: `${panelWidth}px` }}
          aria-label="Paper Agent panel"
        >
          {/* Resize handle */}
          <div class="ap-resize-handle" onMouseDown={handleResizeStart} />

          {/* Header */}
          <div class="ap-header">
            <div class="ap-header-left">
              <button
                class="ap-header-btn"
                onClick={() => setSessionsExpanded(!sessionsExpanded)}
                title="Sessions"
              >
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <path d="M2 4h12M2 8h12M2 12h12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                </svg>
              </button>
              <strong class="ap-header-title">Paper Agent</strong>
            </div>
            <button
              class="ap-header-btn"
              onClick={() => setOpen(false)}
              aria-label="Close panel"
            >
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
              </svg>
            </button>
          </div>

          {/* Session list (collapsible) */}
          {sessionsExpanded && (
            <SessionList
              sessions={sessions}
              activeId={activeSessionId}
              onSelect={loadSession}
              onCreate={createNewSession}
              onPin={handlePin}
              onArchive={handleArchive}
              onDelete={handleDelete}
            />
          )}

          {/* Message flow */}
          <MessageFlow messages={messages} busy={busy} />

          {/* Input */}
          <AgentInput onSend={handleSend} disabled={busy} />
        </aside>
      )}
    </>
  );
}

// Mount
const root = document.getElementById("paper-agent-root");
if (root) {
  render(<AgentPanel />, root);
}
```

- [ ] **Step 5: Create agent panel CSS**

```css
/* frontend/agent-panel/styles/agent-panel.css */

/* ── Launcher Button ── */
.ap-launcher {
  position: fixed;
  bottom: 24px;
  right: 24px;
  z-index: 900;
  width: 48px;
  height: 48px;
  border-radius: 50%;
  border: none;
  background: var(--accent-primary, #d97757);
  color: var(--ink-on-accent, #fff);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--shadow-lg, 0 8px 24px rgba(0,0,0,0.12));
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}

.ap-launcher:hover {
  transform: scale(1.08);
  box-shadow: 0 10px 30px rgba(0,0,0,0.18);
}

/* ── Side Panel ── */
.ap-panel {
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  z-index: 950;
  background: var(--agent-panel-bg, var(--bg-surface, #fff));
  border-left: 1px solid var(--border-default, #e8e8e5);
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-lg, 0 8px 24px rgba(0,0,0,0.12));
  animation: ap-slide-in 0.2s ease;
}

@keyframes ap-slide-in {
  from { transform: translateX(100%); }
  to { transform: translateX(0); }
}

body.agent-panel-open .main-content {
  margin-right: var(--agent-panel-width, 360px);
  transition: margin-right 0.2s ease;
}

/* ── Resize Handle ── */
.ap-resize-handle {
  position: absolute;
  left: -3px;
  top: 0;
  bottom: 0;
  width: 6px;
  cursor: col-resize;
  z-index: 10;
}

.ap-resize-handle:hover {
  background: var(--accent-primary, #d97757);
  opacity: 0.3;
}

/* ── Header ── */
.ap-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-default, #e8e8e5);
  flex-shrink: 0;
}

.ap-header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.ap-header-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--ink-primary, #1a1a1a);
}

.ap-header-btn {
  background: none;
  border: none;
  color: var(--ink-secondary, #6b6b6b);
  cursor: pointer;
  padding: 4px;
  border-radius: var(--radius-sm, 4px);
  display: flex;
  align-items: center;
  justify-content: center;
}

.ap-header-btn:hover {
  background: var(--bg-surface-hover, #f5f5f3);
  color: var(--ink-primary, #1a1a1a);
}

/* ── Session List ── */
.ap-sessions {
  border-bottom: 1px solid var(--border-default, #e8e8e5);
  max-height: 240px;
  overflow-y: auto;
  flex-shrink: 0;
}

.ap-sessions-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
}

.ap-sessions-title {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--ink-muted, #999);
}

.ap-sessions-new {
  background: none;
  border: none;
  color: var(--ink-secondary, #6b6b6b);
  cursor: pointer;
  padding: 2px;
  border-radius: var(--radius-sm, 4px);
  display: flex;
}

.ap-sessions-new:hover {
  background: var(--bg-surface-hover, #f5f5f3);
  color: var(--accent-primary, #d97757);
}

.ap-sessions-list {
  padding: 0 8px 8px;
}

.ap-session-row {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 6px 8px;
  border-radius: var(--radius-md, 8px);
  cursor: pointer;
  transition: background 0.1s ease;
}

.ap-session-row:hover {
  background: var(--bg-surface-hover, #f5f5f3);
}

.ap-session-row.is-active {
  background: var(--accent-soft, #f0c8b4);
}

.ap-session-info {
  display: flex;
  align-items: center;
  gap: 4px;
}

.ap-pin-icon {
  color: var(--accent-primary, #d97757);
  font-size: 12px;
}

.ap-session-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--ink-primary, #1a1a1a);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ap-session-meta {
  display: flex;
  gap: 8px;
  font-size: 11px;
  color: var(--ink-muted, #999);
}

.ap-session-actions {
  display: none;
  gap: 4px;
  margin-top: 4px;
}

.ap-session-row:hover .ap-session-actions {
  display: flex;
}

.ap-session-btn {
  background: none;
  border: none;
  font-size: 11px;
  color: var(--ink-secondary, #6b6b6b);
  cursor: pointer;
  padding: 2px 6px;
  border-radius: var(--radius-sm, 4px);
}

.ap-session-btn:hover {
  background: var(--bg-surface-active, #e8e8e5);
}

.ap-session-btn--danger:hover {
  color: var(--color-error, #ea4335);
}

.ap-sessions-empty {
  padding: 16px;
  text-align: center;
  font-size: 12px;
  color: var(--ink-muted, #999);
}

/* ── Message Thread ── */
.ap-thread {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.ap-msg {
  max-width: 92%;
  animation: ap-fade-in 0.15s ease;
}

@keyframes ap-fade-in {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}

.ap-msg--user {
  align-self: flex-end;
}

.ap-msg--user .ap-msg-content {
  background: var(--accent-primary, #d97757);
  color: var(--ink-on-accent, #fff);
  border-radius: 12px 12px 2px 12px;
  padding: 8px 14px;
  font-size: 13px;
  line-height: 1.5;
}

.ap-msg--assistant .ap-msg-content,
.ap-msg--system .ap-msg-content {
  background: var(--bg-surface-hover, #f5f5f3);
  color: var(--ink-primary, #1a1a1a);
  border-radius: 12px 12px 12px 2px;
  padding: 10px 14px;
  font-size: 13px;
  line-height: 1.6;
}

.ap-msg--system .ap-msg-content {
  font-size: 12px;
  color: var(--ink-secondary, #6b6b6b);
  font-style: italic;
}

.ap-msg-content p { margin: 0 0 0.5rem; }
.ap-msg-content p:last-child { margin-bottom: 0; }
.ap-msg-content ul, .ap-msg-content ol { margin: 0.4rem 0 0.4rem 1.2rem; padding: 0; }
.ap-msg-content code {
  background: rgba(0,0,0,0.06);
  padding: 0.1rem 0.3rem;
  border-radius: 4px;
  font-size: 0.9em;
  font-family: var(--font-mono, monospace);
}
.ap-msg-content pre {
  background: rgba(0,0,0,0.06);
  padding: 0.6rem;
  border-radius: 8px;
  overflow-x: auto;
}
.ap-msg-content a {
  color: var(--accent-link, #007aff);
  text-decoration: underline;
  text-underline-offset: 2px;
}

.ap-msg-tool {
  font-size: 11px;
  color: var(--ink-muted, #999);
  background: transparent;
  border: 1px solid var(--border-default, #e8e8e5);
  border-radius: 8px;
  padding: 4px 10px;
}

.ap-msg-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 6px;
}

.ap-chip {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 12px;
  background: var(--bg-surface-active, #e8e8e5);
  color: var(--ink-secondary, #6b6b6b);
  white-space: nowrap;
}

/* Typing indicator */
.ap-typing {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 12px 14px;
}

.ap-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--ink-muted, #999);
  animation: ap-bounce 1.4s infinite ease-in-out both;
}

.ap-dot:nth-child(1) { animation-delay: -0.32s; }
.ap-dot:nth-child(2) { animation-delay: -0.16s; }

@keyframes ap-bounce {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}

/* ── Composer ── */
.ap-composer {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid var(--border-default, #e8e8e5);
  flex-shrink: 0;
}

.ap-composer-input {
  flex: 1;
  border: 1px solid var(--border-default, #e8e8e5);
  border-radius: var(--radius-md, 8px);
  padding: 8px 12px;
  font-size: 13px;
  font-family: var(--font-sans, sans-serif);
  resize: none;
  line-height: 1.4;
  background: var(--bg-input, #fff);
  color: var(--ink-primary, #1a1a1a);
  outline: none;
  transition: border-color 0.15s ease;
  max-height: 120px;
}

.ap-composer-input:focus {
  border-color: var(--border-focus, #007aff);
}

.ap-composer-input::placeholder {
  color: var(--ink-muted, #999);
}

.ap-composer-send {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-md, 8px);
  border: none;
  background: var(--accent-primary, #d97757);
  color: var(--ink-on-accent, #fff);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: opacity 0.1s ease;
}

.ap-composer-send:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.ap-composer-send:not(:disabled):hover {
  filter: brightness(1.1);
}

/* ── Mobile ── */
@media (max-width: 768px) {
  .ap-panel {
    width: 100% !important;
    border-left: none;
  }
  .ap-resize-handle { display: none; }
}

/* ── Dark mode adjustments ── */
[data-theme="dark"] .ap-msg--user .ap-msg-content {
  background: var(--accent-primary, #d97757);
}

[data-theme="dark"] .ap-msg-content code {
  background: rgba(255,255,255,0.08);
}

[data-theme="dark"] .ap-msg-content pre {
  background: rgba(255,255,255,0.06);
}
```

- [ ] **Step 6: Build and verify**

```bash
cd "/Users/sunweizhou/Desktop/AI Project/arxiv_recommender"
npm install
npm run build
# Verify output
ls -la static/dist/agent-panel.js static/dist/agent-panel.css
```

Expected: Both files exist, `agent-panel.js` < 50KB gzip.

- [ ] **Step 7: Commit**

```bash
git add frontend/agent-panel/ static/dist/
git commit -m "feat(ui): build Preact agent panel with session list, message flow, and floating launcher"
```

---

### Task 8: Template Integration — Load Preact Panel, Remove React Drawer

**Files:**
- Modify: `templates/base_research.html`

- [ ] **Step 1: Replace React agent-drawer references with Preact agent-panel**

In `templates/base_research.html`, find the CSS link:

```html
<link rel="stylesheet" href="{{ url_for('static', filename='dist/agent-drawer.css', v=static_version) }}">
```

Replace with:

```html
<link rel="stylesheet" href="{{ url_for('static', filename='dist/agent-panel.css', v=static_version) }}">
```

- [ ] **Step 2: Update the agent mount point**

In the `<body>` section, find:

```html
<div id="paper-agent-root"></div>
```

If it doesn't exist, add it just before `</body>`. Ensure it is present.

- [ ] **Step 3: Replace the React script reference**

Find the script that loads `agent-drawer.js`:

```html
<script src="{{ url_for('static', filename='dist/agent-drawer.js', v=static_version) }}" defer></script>
```

Replace with:

```html
<script src="{{ url_for('static', filename='dist/agent-panel.js', v=static_version) }}" type="module"></script>
```

- [ ] **Step 4: Remove old React agent drawer CSS/JS references**

Search `templates/base_research.html` for any remaining references to `agent-drawer` and remove them. Also check for any inline `<script>` blocks that reference `window.togglePaperAgent` or `sendPaperAgentMessage` from the old drawer -- these should still work since the new Preact panel exposes the same global functions.

- [ ] **Step 5: Smoke test**

```bash
cd "/Users/sunweizhou/Desktop/AI Project/arxiv_recommender"
python web_server.py &
sleep 2
curl -s http://localhost:5555/ | grep -c "agent-panel"
kill %1
```

Expected: > 0 matches

- [ ] **Step 6: Commit**

```bash
git add templates/base_research.html
git commit -m "refactor(templates): replace React agent-drawer with Preact agent-panel"
```

---

### Task 9: Search History Dropdown UI

**Files:**
- Modify: `templates/search_research.html`
- Modify: `app/routes/api/agent.py` (add search history endpoints)

- [ ] **Step 1: Add search history API endpoints**

Append to `app/routes/api/agent.py`:

```python
# ------------------------------------------------------------------
# Search History
# ------------------------------------------------------------------

@bp.get("/api/search/history")
def search_history():
    """List recent searches for the dropdown."""
    store = _current_state_store()
    limit = int(request.args.get("limit", 10))
    recent = store.list_recent_searches(limit=limit)
    return jsonify({"success": True, "searches": recent})


@bp.post("/api/search/history")
def record_search():
    """Record a search execution."""
    data = request.get_json() or {}
    store = _current_state_store()
    entry = store.record_search(
        str(data.get("query", "") or "").strip(),
        rewritten=data.get("rewritten"),
        result_count=int(data.get("result_count", 0)),
        sources=data.get("sources"),
    )
    return jsonify({"success": True, "entry": entry})


@bp.get("/api/search/suggestions")
def search_suggestions():
    """Get suggested searches based on history frequency."""
    store = _current_state_store()
    limit = int(request.args.get("limit", 5))
    suggestions = store.get_suggested_searches(limit=limit)
    return jsonify({"success": True, "suggestions": suggestions})
```

- [ ] **Step 2: Add search history dropdown HTML**

In `templates/search_research.html`, after the search input element, add:

```html
<div class="search-history-dropdown" id="searchHistoryDropdown" hidden>
  <div class="search-history-header">
    <span>Recent Searches</span>
  </div>
  <div class="search-history-items" id="searchHistoryItems">
    <!-- Populated by JS -->
  </div>
  <div class="search-history-suggestions" id="searchSuggestions" hidden>
    <span class="search-history-header">Suggested</span>
    <div id="searchSuggestionItems"></div>
  </div>
</div>
```

- [ ] **Step 3: Add search history JS**

Add to `static/js/core.js`:

```javascript
// Search history dropdown
(function () {
  var dropdown = document.getElementById('searchHistoryDropdown');
  var searchInput = document.getElementById('paperAgentSearchInput') ||
                    document.getElementById('queryText') ||
                    document.getElementById('workspacePrompt');
  if (!dropdown || !searchInput) return;

  var debounceTimer = null;

  searchInput.addEventListener('focus', function () {
    if (!searchInput.value.trim()) {
      loadSearchHistory();
    }
  });

  searchInput.addEventListener('input', function () {
    clearTimeout(debounceTimer);
    if (!searchInput.value.trim()) {
      debounceTimer = setTimeout(loadSearchHistory, 200);
    } else {
      dropdown.hidden = true;
    }
  });

  document.addEventListener('click', function (e) {
    if (!dropdown.contains(e.target) && e.target !== searchInput) {
      dropdown.hidden = true;
    }
  });

  function loadSearchHistory() {
    fetch('/api/search/history?limit=10')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data.success) return;
        var items = document.getElementById('searchHistoryItems');
        if (!items) return;
        items.innerHTML = '';
        (data.searches || []).forEach(function (s) {
          var div = document.createElement('div');
          div.className = 'search-history-item';
          div.textContent = s.query;
          if (s.rewritten) {
            var sub = document.createElement('span');
            sub.className = 'search-history-rewrite';
            sub.textContent = ' → ' + s.rewritten;
            div.appendChild(sub);
          }
          div.addEventListener('click', function () {
            searchInput.value = s.query;
            dropdown.hidden = true;
            searchInput.form && searchInput.form.dispatchEvent(new Event('submit'));
          });
          items.appendChild(div);
        });
        dropdown.hidden = (data.searches || []).length === 0;
      })
      .catch(function () { /* silent */ });

    // Also load suggestions
    fetch('/api/search/suggestions?limit=5')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var container = document.getElementById('searchSuggestions');
        var items = document.getElementById('searchSuggestionItems');
        if (!container || !items || !data.success) return;
        var suggestions = data.suggestions || [];
        if (suggestions.length === 0) { container.hidden = true; return; }
        items.innerHTML = '';
        suggestions.forEach(function (s) {
          var chip = document.createElement('span');
          chip.className = 'chip';
          chip.textContent = s.query;
          chip.addEventListener('click', function () {
            searchInput.value = s.query;
            dropdown.hidden = true;
            searchInput.form && searchInput.form.dispatchEvent(new Event('submit'));
          });
          items.appendChild(chip);
        });
        container.hidden = false;
      })
      .catch(function () { /* silent */ });
  }
})();
```

- [ ] **Step 4: Add dropdown CSS**

Append to `static/research_ui.css`:

```css
/* Search History Dropdown */
.search-history-dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  z-index: 200;
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  max-height: 320px;
  overflow-y: auto;
  margin-top: 4px;
}

.search-history-header {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--ink-muted);
  padding: 8px 12px 4px;
}

.search-history-item {
  padding: 8px 12px;
  font-size: 13px;
  color: var(--ink-primary);
  cursor: pointer;
  transition: background 0.1s ease;
}

.search-history-item:hover {
  background: var(--bg-surface-hover);
}

.search-history-rewrite {
  font-size: 11px;
  color: var(--ink-muted);
}

.search-history-suggestions {
  border-top: 1px solid var(--border-default);
  padding: 8px 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
```

- [ ] **Step 5: Commit**

```bash
git add app/routes/api/agent.py templates/search_research.html static/js/core.js static/research_ui.css
git commit -m "feat(search): add search history dropdown with recent searches and suggestions"
```

---

### Task 10: Wire QueryRewriter into Search Flow

**Files:**
- Modify: `app/services/unified_search_service.py`
- Modify: `app/routes/api/agent.py`

- [ ] **Step 1: Add rewrite endpoint to agent API**

Append to `app/routes/api/agent.py`:

```python
from app.services.query_rewriter import QueryRewriter


@bp.post("/api/search/rewrite")
def rewrite_query():
    """Rewrite a search query using QueryRewriter."""
    data = request.get_json() or {}
    query = str(data.get("query", "") or "").strip()
    if not query:
        return jsonify({"success": False, "error": "No query provided"}), 400

    rewriter = QueryRewriter(provider_factory=build_ai_provider_from_env)
    result = rewriter.rewrite(query, context=data.get("context") or {})
    return jsonify({
        "success": True,
        "original": result.original,
        "rewritten": result.rewritten,
        "was_rewritten": result.was_rewritten,
        "explanation": result.explanation,
        "expanded_terms": result.expanded_terms,
    })
```

- [ ] **Step 2: Add rewrite hint UI to search page**

In `templates/search_research.html`, below the search bar, add a container for the rewrite hint:

```html
<div class="query-rewrite-hint" id="queryRewriteHint" hidden>
  <span class="query-rewrite-label">Searched as:</span>
  <span class="query-rewrite-text" id="queryRewriteText"></span>
  <button class="query-rewrite-explain" id="queryRewriteExplain" title="Why?">?</button>
  <button class="query-rewrite-revert" id="queryRewriteRevert" title="Use original">Revert</button>
</div>
```

- [ ] **Step 3: Add rewrite CSS**

Append to `static/research_ui.css`:

```css
/* Query Rewrite Hint */
.query-rewrite-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 0;
  font-size: 12px;
  color: var(--ink-secondary);
}

.query-rewrite-label {
  color: var(--ink-muted);
}

.query-rewrite-text {
  color: var(--accent-primary);
  font-weight: 500;
}

.query-rewrite-explain,
.query-rewrite-revert {
  background: none;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-sm);
  padding: 1px 6px;
  font-size: 11px;
  cursor: pointer;
  color: var(--ink-secondary);
}

.query-rewrite-explain:hover,
.query-rewrite-revert:hover {
  background: var(--bg-surface-hover);
  color: var(--ink-primary);
}
```

- [ ] **Step 4: Commit**

```bash
git add app/routes/api/agent.py app/services/unified_search_service.py templates/search_research.html static/research_ui.css
git commit -m "feat(search): wire QueryRewriter into search flow with rewrite hint UI"
```

---

### Task 11: Integration Testing + Cleanup

**Files:**
- Modify: `tests/test_agent_sessions.py`
- Remove: `frontend/agent/` (old React source, no longer used)

- [ ] **Step 1: Add end-to-end integration assertions**

Append to `tests/test_agent_sessions.py`:

```python
class TestPhase3Integration(unittest.TestCase):
    """Integration tests for the full Phase 3 feature set."""

    def test_session_message_round_trip(self):
        """Create session -> send message -> verify persistence."""
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        store = StateStore(db_path=tmp.name)
        service = AgentService(store, provider_factory=lambda: NoProvider())

        # First message creates session
        r1 = service.handle_message("search GNN papers")
        session_id = r1["session"]["id"]
        self.assertIsNotNone(session_id)

        # Second message uses same session
        r2 = service.handle_message("save the first one", session_id=session_id)
        self.assertEqual(r2["session"]["id"], session_id)

        # Verify messages persisted
        messages = store.get_session_messages(session_id)
        self.assertGreaterEqual(len(messages), 4)  # 2 user + 2 assistant

        os.unlink(tmp.name)

    def test_search_history_records_on_search(self):
        """Search history should capture queries."""
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
        """QueryRewriter must not crash when no LLM is configured."""
        from app.services.query_rewriter import QueryRewriter
        rewriter = QueryRewriter(provider_factory=lambda: None)
        result = rewriter.rewrite("attention mechanism in transformers")
        self.assertEqual(result.original, "attention mechanism in transformers")

    def test_preact_bundle_exists(self):
        """Preact agent-panel build artifacts must exist."""
        from pathlib import Path
        dist = Path(__file__).resolve().parent.parent / "static" / "dist"
        self.assertTrue((dist / "agent-panel.js").exists(), "agent-panel.js not found")
        self.assertTrue((dist / "agent-panel.css").exists(), "agent-panel.css not found")

    def test_preact_bundle_size(self):
        """Preact agent-panel JS must be under 50KB gzip."""
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
        """base_research.html must reference agent-panel, not agent-drawer."""
        from pathlib import Path
        template = Path(__file__).resolve().parent.parent / "templates" / "base_research.html"
        html = template.read_text(encoding="utf-8")
        self.assertIn("agent-panel", html, "Template must load agent-panel")
        self.assertNotIn("agent-drawer.js", html, "Old agent-drawer.js reference must be removed")
```

- [ ] **Step 2: Run full test suite**

Run: `python -m pytest -v`
Expected: ALL PASS

- [ ] **Step 3: Remove old React agent source**

```bash
rm -rf frontend/agent/
```

The old `frontend/agent/main.tsx` and `frontend/agent/agent.css` are no longer needed since the Preact panel replaces them entirely.

- [ ] **Step 4: Clean up old dist artifacts**

```bash
rm -f static/dist/agent-drawer.js static/dist/agent-drawer.css
```

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "test: add Phase 3 integration tests, remove old React agent drawer"
```

---

### Task 12: Verification Checklist

Run through each acceptance criterion from the design spec:

- [ ] **Create session, multi-turn conversation, switch sessions, restore history**

```bash
# Verify via API
curl -s http://localhost:5555/api/agent/sessions -X POST -H 'Content-Type: application/json' -d '{"title": "Test"}' | python -m json.tool
# Should return session with id
```

- [ ] **Agent chains multiple actions in single response**

The multi-step execution plan is implemented in `AgentService._execute()` which can produce actions + tool_results + state_updates in a single response.

- [ ] **Panel open/close smooth, mobile usable**

Visual verification: open the app, click the floating button, verify panel slides in at 360px, press Escape to close. On mobile viewport (< 768px), panel should fill width.

- [ ] **All features degrade gracefully without LLM provider**

```bash
# Run without API keys set
unset OPENAI_API_KEY ANTHROPIC_API_KEY
python -c "
from state_store import StateStore
from app.services.agent_service import AgentService
from app.services.ai_providers import NoProvider

store = StateStore(':memory:')
svc = AgentService(store, provider_factory=lambda: NoProvider())
r = svc.handle_message('search federated learning')
print('Success:', r['success'])
print('Reply:', r['reply'][:80])
print('Session:', r['session']['id'][:12] + '...')
"
```

Expected: works without crash, uses fallback planning.

- [ ] **Run full test suite one final time**

```bash
python -m pytest -q
```

Expected: ALL PASS
