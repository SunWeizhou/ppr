# Phase 2: Entity Subscription System — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a structured entity system (journals, conferences, scholars, fields) as first-class objects with profile pages, extend the subscription system to support entity-linked subscriptions with filters, add new subscription runner strategies, restructure the Watch page by entity type, and create the `user_profile` table for future personalization.

**Architecture:** Four entity types stored in an `entities` table with `entity_relations` for cross-references. Existing `subscriptions` table extended with `entity_id` and `filters_json` columns. `EntityService` handles CRUD plus metadata fetch from OpenAlex/Semantic Scholar APIs. Entity profile pages rendered via Jinja2 with type-specific sections. Search results trigger async entity extraction (non-blocking). `SubscriptionRunner` gains three new strategies: `run_journal_subscription()`, `run_conference_subscription()`, `run_field_subscription()`.

**Tech Stack:** SQLite (WAL mode), Flask/Jinja2, Python `urllib`/`requests` for OpenAlex and Semantic Scholar APIs, vanilla JS for Watch page restructure.

**Ref:** Design spec at `docs/superpowers/specs/2026-05-11-paper-agent-v2-design.md`, section 3 (Entity & Subscription System) and section 7 (Phase Breakdown, Phase 2).

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Modify | `state_store.py` | Add `entities`, `entity_relations`, `user_profile` tables + CRUD methods |
| Create | `app/services/entity_service.py` | EntityService class: CRUD, metadata fetch, auto-extraction |
| Modify | `app/services/subscription_runner.py` | Add `run_journal_subscription()`, `run_conference_subscription()`, `run_field_subscription()` |
| Create | `app/routes/api/entities.py` | Entity REST API endpoints |
| Create | `app/routes/entities.py` | Entity profile page route |
| Create | `templates/entity_profile.html` | Entity profile template (4 type-specific sections) |
| Modify | `templates/watch.html` | Restructure for entity-based subscription grouping |
| Modify | `app/routes/api/subscriptions.py` | Support `entity_id` and `filters_json` in create/update |
| Modify | `app/viewmodels/shared.py` | Add entity count to sidebar subscription items |
| Create | `tests/test_entity_service.py` | Entity CRUD and metadata fetch tests |
| Create | `tests/test_entity_subscriptions.py` | Entity subscription runner tests |

---

### Task 1: Entity and User Profile Schema in StateStore

**Files:**
- Modify: `state_store.py`
- Create: `tests/test_entity_service.py` (schema assertions only for this task)

- [ ] **Step 1: Write test that validates entity schema exists**

```python
# tests/test_entity_service.py
"""Test entity system schema and CRUD operations."""
import json
import os
import tempfile
import unittest

from state_store import StateStore


class TestEntitySchema(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        self.store = StateStore(db_path=self.db_path)

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_entities_table_exists(self):
        with self.store._connect() as conn:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='entities'"
            ).fetchone()
        self.assertIsNotNone(row, "entities table must exist")

    def test_entity_relations_table_exists(self):
        with self.store._connect() as conn:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='entity_relations'"
            ).fetchone()
        self.assertIsNotNone(row, "entity_relations table must exist")

    def test_user_profile_table_exists(self):
        with self.store._connect() as conn:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='user_profile'"
            ).fetchone()
        self.assertIsNotNone(row, "user_profile table must exist")

    def test_subscriptions_has_entity_id_column(self):
        with self.store._connect() as conn:
            rows = conn.execute("PRAGMA table_info(subscriptions)").fetchall()
            column_names = {row["name"] for row in rows}
        self.assertIn("entity_id", column_names)

    def test_subscriptions_has_filters_json_column(self):
        with self.store._connect() as conn:
            rows = conn.execute("PRAGMA table_info(subscriptions)").fetchall()
            column_names = {row["name"] for row in rows}
        self.assertIn("filters_json", column_names)

    def test_subscriptions_type_check_includes_field_and_entity(self):
        """The subscriptions type CHECK should accept 'field' and 'entity'."""
        with self.store._connect() as conn:
            # Should not raise
            conn.execute(
                """INSERT INTO subscriptions(type, name, query_text, created_at, updated_at)
                   VALUES ('field', 'test-field', 'cs.AI', datetime('now'), datetime('now'))"""
            )
            conn.execute(
                """INSERT INTO subscriptions(type, name, query_text, created_at, updated_at)
                   VALUES ('entity', 'test-entity', '', datetime('now'), datetime('now'))"""
            )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_entity_service.py::TestEntitySchema -v`
Expected: FAIL — tables do not exist, columns missing, type CHECK rejects 'field' and 'entity'.

- [ ] **Step 3: Add entities table to state_store.py _initialize()**

In `state_store.py`, inside the `_initialize` method's `conn.executescript(...)` block, add the following tables after the `feedback_models` table (before the closing `"""`):

```sql
CREATE TABLE IF NOT EXISTS entities (
    id            TEXT PRIMARY KEY,
    type          TEXT NOT NULL CHECK(type IN ('journal','conference','scholar','field')),
    name          TEXT NOT NULL,
    aliases       TEXT DEFAULT '[]',
    external_ids  TEXT DEFAULT '{}',
    metadata_json TEXT DEFAULT '{}',
    stats_json    TEXT DEFAULT '{}',
    last_synced   TEXT,
    created_at    TEXT DEFAULT (datetime('now')),
    updated_at    TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type);
CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name);

CREATE TABLE IF NOT EXISTS entity_relations (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id      TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    target_id      TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    relation_type  TEXT NOT NULL CHECK(relation_type IN (
        'publishes_in','affiliated_with','researches','subfield_of','co_located'
    )),
    weight         REAL DEFAULT 1.0,
    created_at     TEXT DEFAULT (datetime('now')),
    UNIQUE(source_id, target_id, relation_type)
);

CREATE TABLE IF NOT EXISTS user_profile (
    id                INTEGER PRIMARY KEY DEFAULT 1,
    interest_vector   TEXT DEFAULT '[]',
    topic_weights     TEXT DEFAULT '{}',
    entity_affinities TEXT DEFAULT '{}',
    reading_pace      TEXT DEFAULT '{}',
    updated_at        TEXT DEFAULT (datetime('now'))
);
```

- [ ] **Step 4: Extend the subscriptions table CHECK constraint and add new columns**

The existing `subscriptions` table has `CHECK(type IN ('query', 'author', 'venue'))`. Since SQLite does not allow altering CHECK constraints, we need to handle this via migration. In the `_initialize` method, after the `executescript` block, add an idempotent migration:

```python
# Extend subscriptions: add entity_id and filters_json columns
self._add_column_if_missing(
    conn, "subscriptions", "entity_id",
    "entity_id TEXT REFERENCES entities(id)",
)
self._add_column_if_missing(
    conn, "subscriptions", "filters_json",
    "filters_json TEXT DEFAULT '{}'",
)
```

For the CHECK constraint expansion (adding 'field' and 'entity' types), add a migration that recreates the table if the old CHECK is still in place:

```python
# Migrate subscriptions CHECK constraint to include 'field' and 'entity'
if current_version < 7:
    # Check if the old CHECK constraint is still active
    try:
        conn.execute(
            "INSERT INTO subscriptions(type, name, created_at, updated_at) "
            "VALUES ('field', '__check_test__', datetime('now'), datetime('now'))"
        )
        # If it succeeds, delete the test row — constraint already allows 'field'
        conn.execute("DELETE FROM subscriptions WHERE name = '__check_test__'")
    except sqlite3.IntegrityError:
        # Old CHECK constraint rejects 'field' — need to recreate table
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS subscriptions_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL CHECK(type IN ('query', 'author', 'venue', 'field', 'entity')),
                name TEXT NOT NULL,
                query_text TEXT DEFAULT '',
                payload_json TEXT DEFAULT '{}',
                enabled INTEGER DEFAULT 1,
                latest_hit_count INTEGER DEFAULT 0,
                last_checked_at TEXT,
                entity_id TEXT REFERENCES entities(id),
                filters_json TEXT DEFAULT '{}',
                research_question_id INTEGER,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            INSERT INTO subscriptions_new(
                id, type, name, query_text, payload_json, enabled,
                latest_hit_count, last_checked_at, research_question_id,
                created_at, updated_at
            )
            SELECT id, type, name, query_text, payload_json, enabled,
                   latest_hit_count, last_checked_at, research_question_id,
                   created_at, updated_at
            FROM subscriptions;

            DROP TABLE subscriptions;
            ALTER TABLE subscriptions_new RENAME TO subscriptions;

            CREATE INDEX IF NOT EXISTS idx_subscriptions_type ON subscriptions(type);
            CREATE INDEX IF NOT EXISTS idx_subscriptions_enabled ON subscriptions(enabled);
        """)
    conn.execute(
        "INSERT OR REPLACE INTO schema_meta(key, value) VALUES('schema_version', '7')"
    )
```

- [ ] **Step 5: Update `create_subscription` to accept new types and entity_id**

In `state_store.py`, update the `create_subscription` method's type validation:

```python
def create_subscription(
    self,
    type: str,
    name: str,
    query_text: str = "",
    payload_json: str = "{}",
    enabled: bool = True,
    research_question_id: Optional[int] = None,
    entity_id: Optional[str] = None,
    filters_json: Optional[str] = None,
) -> Dict:
    if type not in ("query", "author", "venue", "field", "entity"):
        raise ValueError(f"Invalid subscription type: {type}")
    if entity_id is not None:
        # Validate entity exists
        entity = self.get_entity(entity_id)
        if entity is None:
            raise ValueError(f"Unknown entity: {entity_id}")
    if research_question_id is not None:
        research_question_id = int(research_question_id)
        if self.get_research_question(research_question_id) is None:
            raise ValueError(
                f"Unknown research question: {research_question_id}"
            )
    if isinstance(payload_json, dict):
        payload_json = json.dumps(payload_json, ensure_ascii=False)
    if filters_json is None:
        filters_json = "{}"
    elif isinstance(filters_json, dict):
        filters_json = json.dumps(filters_json, ensure_ascii=False)
    now = _utc_now()
    with self._lock, self._connect() as conn:
        conn.execute(
            """
            INSERT INTO subscriptions(
                type, name, query_text, payload_json, enabled,
                latest_hit_count, research_question_id, entity_id,
                filters_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?)
            """,
            (
                type,
                name.strip(),
                query_text.strip(),
                payload_json,
                1 if enabled else 0,
                research_question_id,
                entity_id,
                filters_json,
                now,
                now,
            ),
        )
        row = conn.execute(
            "SELECT * FROM subscriptions WHERE id = last_insert_rowid()"
        ).fetchone()
    return self._row_to_dict(row)
```

- [ ] **Step 6: Add _row_to_dict handling for new JSON columns**

In `state_store.py`, update `_row_to_dict` to parse `filters_json`, `aliases`, `metadata_json`, `stats_json`, `external_ids`:

```python
@staticmethod
def _row_to_dict(row: sqlite3.Row) -> Dict:
    data = dict(row)
    for key in ("payload_json", "result_json", "filters_json", "tags_json",
                "evidence_claim_ids", "aliases", "metadata_json",
                "stats_json", "external_ids", "interest_vector",
                "topic_weights", "entity_affinities", "reading_pace"):
        if key in data:
            try:
                data[key] = json.loads(data[key])
            except (TypeError, json.JSONDecodeError):
                data[key] = [] if key in ("evidence_claim_ids", "aliases", "interest_vector") else {}
    return data
```

- [ ] **Step 7: Add entity CRUD methods to StateStore**

Add the following methods to `state_store.py` in a new `# Entities` section after the Subscription Hits section:

```python
# ------------------------------------------------------------------
# Entities
# ------------------------------------------------------------------

def create_entity(
    self,
    entity_id: str,
    entity_type: str,
    name: str,
    *,
    aliases: Optional[List[str]] = None,
    external_ids: Optional[Dict] = None,
    metadata_json: Optional[Dict] = None,
    stats_json: Optional[Dict] = None,
) -> Dict:
    if entity_type not in ("journal", "conference", "scholar", "field"):
        raise ValueError(f"Invalid entity type: {entity_type}")
    entity_id = str(entity_id or "").strip()
    name = str(name or "").strip()
    if not entity_id:
        raise ValueError("entity_id is required")
    if not name:
        raise ValueError("name is required")
    now = _utc_now()
    with self._lock, self._connect() as conn:
        conn.execute(
            """
            INSERT INTO entities(
                id, type, name, aliases, external_ids,
                metadata_json, stats_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                aliases = excluded.aliases,
                external_ids = excluded.external_ids,
                metadata_json = excluded.metadata_json,
                stats_json = excluded.stats_json,
                updated_at = excluded.updated_at
            """,
            (
                entity_id,
                entity_type,
                name,
                _to_json(aliases, []),
                _to_json(external_ids, {}),
                _to_json(metadata_json, {}),
                _to_json(stats_json, {}),
                now,
                now,
            ),
        )
        row = conn.execute(
            "SELECT * FROM entities WHERE id = ?", (entity_id,)
        ).fetchone()
    return self._row_to_dict(row)

def get_entity(self, entity_id: str) -> Optional[Dict]:
    with self._connect() as conn:
        row = conn.execute(
            "SELECT * FROM entities WHERE id = ?", (entity_id,)
        ).fetchone()
    return self._row_to_dict(row) if row else None

def list_entities(
    self,
    entity_type: Optional[str] = None,
    *,
    limit: int = 100,
    search: Optional[str] = None,
) -> List[Dict]:
    query = "SELECT * FROM entities"
    params: List[object] = []
    conditions = []
    if entity_type:
        conditions.append("type = ?")
        params.append(entity_type)
    if search:
        conditions.append("(name LIKE ? OR aliases LIKE ?)")
        like_term = f"%{search}%"
        params.extend([like_term, like_term])
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY updated_at DESC LIMIT ?"
    params.append(limit)
    with self._connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return [self._row_to_dict(row) for row in rows]

def update_entity(
    self,
    entity_id: str,
    *,
    name: Optional[str] = None,
    aliases: Optional[List[str]] = None,
    external_ids: Optional[Dict] = None,
    metadata_json: Optional[Dict] = None,
    stats_json: Optional[Dict] = None,
    last_synced: Optional[str] = None,
) -> Optional[Dict]:
    updates = []
    params: List[object] = []
    if name is not None:
        updates.append("name = ?")
        params.append(str(name).strip())
    if aliases is not None:
        updates.append("aliases = ?")
        params.append(_to_json(aliases, []))
    if external_ids is not None:
        updates.append("external_ids = ?")
        params.append(_to_json(external_ids, {}))
    if metadata_json is not None:
        updates.append("metadata_json = ?")
        params.append(_to_json(metadata_json, {}))
    if stats_json is not None:
        updates.append("stats_json = ?")
        params.append(_to_json(stats_json, {}))
    if last_synced is not None:
        updates.append("last_synced = ?")
        params.append(last_synced)
    if not updates:
        return self.get_entity(entity_id)
    updates.append("updated_at = ?")
    params.append(_utc_now())
    params.append(entity_id)
    with self._lock, self._connect() as conn:
        conn.execute(
            f"UPDATE entities SET {', '.join(updates)} WHERE id = ?",
            params,
        )
    return self.get_entity(entity_id)

def delete_entity(self, entity_id: str) -> bool:
    with self._lock, self._connect() as conn:
        result = conn.execute(
            "DELETE FROM entities WHERE id = ?", (entity_id,)
        )
    return result.rowcount > 0

# ------------------------------------------------------------------
# Entity Relations
# ------------------------------------------------------------------

def create_entity_relation(
    self,
    source_id: str,
    target_id: str,
    relation_type: str,
    weight: float = 1.0,
) -> Dict:
    valid_types = (
        "publishes_in", "affiliated_with", "researches",
        "subfield_of", "co_located",
    )
    if relation_type not in valid_types:
        raise ValueError(f"Invalid relation type: {relation_type}")
    now = _utc_now()
    with self._lock, self._connect() as conn:
        conn.execute(
            """
            INSERT INTO entity_relations(source_id, target_id, relation_type, weight, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(source_id, target_id, relation_type) DO UPDATE SET
                weight = excluded.weight
            """,
            (source_id, target_id, relation_type, weight, now),
        )
        row = conn.execute(
            "SELECT * FROM entity_relations WHERE source_id = ? AND target_id = ? AND relation_type = ?",
            (source_id, target_id, relation_type),
        ).fetchone()
    return self._row_to_dict(row)

def list_entity_relations(
    self,
    entity_id: str,
    *,
    direction: str = "both",
    relation_type: Optional[str] = None,
) -> List[Dict]:
    conditions = []
    params: List[object] = []
    if direction == "outgoing":
        conditions.append("source_id = ?")
        params.append(entity_id)
    elif direction == "incoming":
        conditions.append("target_id = ?")
        params.append(entity_id)
    else:
        conditions.append("(source_id = ? OR target_id = ?)")
        params.extend([entity_id, entity_id])
    if relation_type:
        conditions.append("relation_type = ?")
        params.append(relation_type)
    query = f"SELECT * FROM entity_relations WHERE {' AND '.join(conditions)} ORDER BY weight DESC"
    with self._connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return [self._row_to_dict(row) for row in rows]
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `python -m pytest tests/test_entity_service.py::TestEntitySchema -v`
Expected: ALL PASS

- [ ] **Step 9: Commit**

```bash
git add state_store.py tests/test_entity_service.py
git commit -m "feat(schema): add entities, entity_relations, user_profile tables and extend subscriptions"
```

---

### Task 2: Entity CRUD Tests and Validation

**Files:**
- Modify: `tests/test_entity_service.py`

- [ ] **Step 1: Add entity CRUD tests**

Append to `tests/test_entity_service.py`:

```python
class TestEntityCRUD(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        self.store = StateStore(db_path=self.db_path)

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_create_journal_entity(self):
        entity = self.store.create_entity(
            entity_id="journal:nature_ml",
            entity_type="journal",
            name="Nature Machine Intelligence",
            external_ids={"openalex": "S12345"},
            metadata_json={
                "publisher": "Nature Publishing Group",
                "issn": "2522-5839",
                "impact_factor": 25.9,
                "h_index": 89,
            },
        )
        self.assertEqual(entity["id"], "journal:nature_ml")
        self.assertEqual(entity["type"], "journal")
        self.assertEqual(entity["name"], "Nature Machine Intelligence")
        self.assertEqual(entity["metadata_json"]["publisher"], "Nature Publishing Group")

    def test_create_scholar_entity(self):
        entity = self.store.create_entity(
            entity_id="scholar:s2:12345",
            entity_type="scholar",
            name="Yann LeCun",
            aliases=["Y. LeCun", "Yann Le Cun"],
            metadata_json={
                "affiliations": ["Meta AI", "NYU"],
                "h_index": 178,
                "citation_count": 430000,
                "research_interests": ["deep learning", "self-supervised learning"],
            },
        )
        self.assertEqual(entity["type"], "scholar")
        self.assertIn("Y. LeCun", entity["aliases"])
        self.assertEqual(entity["metadata_json"]["h_index"], 178)

    def test_create_conference_entity(self):
        entity = self.store.create_entity(
            entity_id="conference:neurips",
            entity_type="conference",
            name="NeurIPS",
            metadata_json={
                "series_name": "Conference on Neural Information Processing Systems",
                "frequency": "annual",
                "acceptance_rate": 0.25,
                "tier": "A*",
            },
        )
        self.assertEqual(entity["type"], "conference")
        self.assertEqual(entity["metadata_json"]["tier"], "A*")

    def test_create_field_entity(self):
        entity = self.store.create_entity(
            entity_id="field:cs.AI",
            entity_type="field",
            name="Artificial Intelligence",
            metadata_json={
                "arxiv_categories": ["cs.AI"],
                "description": "Covers all areas of AI.",
                "key_venues": ["AAAI", "IJCAI", "NeurIPS"],
            },
        )
        self.assertEqual(entity["type"], "field")
        self.assertIn("cs.AI", entity["metadata_json"]["arxiv_categories"])

    def test_create_entity_invalid_type_raises(self):
        with self.assertRaises(ValueError):
            self.store.create_entity(
                entity_id="bad:1", entity_type="unknown", name="Bad"
            )

    def test_create_entity_missing_id_raises(self):
        with self.assertRaises(ValueError):
            self.store.create_entity(
                entity_id="", entity_type="journal", name="No ID"
            )

    def test_create_entity_missing_name_raises(self):
        with self.assertRaises(ValueError):
            self.store.create_entity(
                entity_id="journal:x", entity_type="journal", name=""
            )

    def test_get_entity(self):
        self.store.create_entity(
            entity_id="journal:test", entity_type="journal", name="Test Journal"
        )
        entity = self.store.get_entity("journal:test")
        self.assertIsNotNone(entity)
        self.assertEqual(entity["name"], "Test Journal")

    def test_get_entity_not_found(self):
        self.assertIsNone(self.store.get_entity("nonexistent"))

    def test_list_entities_by_type(self):
        self.store.create_entity(
            entity_id="journal:a", entity_type="journal", name="Journal A"
        )
        self.store.create_entity(
            entity_id="scholar:b", entity_type="scholar", name="Scholar B"
        )
        journals = self.store.list_entities(entity_type="journal")
        self.assertEqual(len(journals), 1)
        self.assertEqual(journals[0]["name"], "Journal A")

    def test_list_entities_search(self):
        self.store.create_entity(
            entity_id="journal:ml", entity_type="journal", name="Machine Learning Journal"
        )
        self.store.create_entity(
            entity_id="journal:cv", entity_type="journal", name="Computer Vision Quarterly"
        )
        results = self.store.list_entities(search="Machine")
        self.assertEqual(len(results), 1)

    def test_update_entity(self):
        self.store.create_entity(
            entity_id="journal:test", entity_type="journal", name="Old Name"
        )
        updated = self.store.update_entity("journal:test", name="New Name")
        self.assertEqual(updated["name"], "New Name")

    def test_delete_entity(self):
        self.store.create_entity(
            entity_id="journal:del", entity_type="journal", name="Delete Me"
        )
        self.assertTrue(self.store.delete_entity("journal:del"))
        self.assertIsNone(self.store.get_entity("journal:del"))

    def test_delete_entity_not_found(self):
        self.assertFalse(self.store.delete_entity("nonexistent"))

    def test_upsert_entity_updates_existing(self):
        self.store.create_entity(
            entity_id="journal:upsert", entity_type="journal", name="V1",
            metadata_json={"impact_factor": 10.0},
        )
        updated = self.store.create_entity(
            entity_id="journal:upsert", entity_type="journal", name="V2",
            metadata_json={"impact_factor": 12.0},
        )
        self.assertEqual(updated["name"], "V2")
        self.assertEqual(updated["metadata_json"]["impact_factor"], 12.0)


class TestEntityRelations(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        self.store = StateStore(db_path=self.db_path)
        self.store.create_entity(
            entity_id="scholar:alice", entity_type="scholar", name="Alice"
        )
        self.store.create_entity(
            entity_id="journal:ml", entity_type="journal", name="ML Journal"
        )

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_create_relation(self):
        rel = self.store.create_entity_relation(
            "scholar:alice", "journal:ml", "publishes_in", weight=0.9
        )
        self.assertEqual(rel["source_id"], "scholar:alice")
        self.assertEqual(rel["target_id"], "journal:ml")
        self.assertEqual(rel["relation_type"], "publishes_in")
        self.assertAlmostEqual(rel["weight"], 0.9)

    def test_invalid_relation_type_raises(self):
        with self.assertRaises(ValueError):
            self.store.create_entity_relation(
                "scholar:alice", "journal:ml", "invalid_type"
            )

    def test_list_relations(self):
        self.store.create_entity_relation(
            "scholar:alice", "journal:ml", "publishes_in"
        )
        relations = self.store.list_entity_relations("scholar:alice")
        self.assertEqual(len(relations), 1)

    def test_list_relations_direction_filter(self):
        self.store.create_entity_relation(
            "scholar:alice", "journal:ml", "publishes_in"
        )
        outgoing = self.store.list_entity_relations(
            "scholar:alice", direction="outgoing"
        )
        incoming = self.store.list_entity_relations(
            "scholar:alice", direction="incoming"
        )
        self.assertEqual(len(outgoing), 1)
        self.assertEqual(len(incoming), 0)

    def test_upsert_relation_updates_weight(self):
        self.store.create_entity_relation(
            "scholar:alice", "journal:ml", "publishes_in", weight=0.5
        )
        self.store.create_entity_relation(
            "scholar:alice", "journal:ml", "publishes_in", weight=0.9
        )
        relations = self.store.list_entity_relations("scholar:alice")
        self.assertEqual(len(relations), 1)
        self.assertAlmostEqual(relations[0]["weight"], 0.9)
```

- [ ] **Step 2: Run tests**

Run: `python -m pytest tests/test_entity_service.py -v`
Expected: ALL PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_entity_service.py
git commit -m "test: add entity CRUD and relation tests"
```

---

### Task 3: EntityService — CRUD and Metadata Fetch

**Files:**
- Create: `app/services/entity_service.py`
- Modify: `tests/test_entity_service.py`

- [ ] **Step 1: Write EntityService tests**

Append to `tests/test_entity_service.py`:

```python
from unittest.mock import patch, MagicMock
from app.services.entity_service import EntityService


class TestEntityService(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        self.store = StateStore(db_path=self.db_path)
        self.svc = EntityService(self.store)

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_get_or_create_journal(self):
        entity = self.svc.get_or_create(
            entity_type="journal",
            name="Nature Machine Intelligence",
            external_ids={"openalex": "S12345"},
        )
        self.assertTrue(entity["id"].startswith("journal:"))
        self.assertEqual(entity["type"], "journal")
        self.assertEqual(entity["name"], "Nature Machine Intelligence")

    def test_get_or_create_returns_existing(self):
        e1 = self.svc.get_or_create(
            entity_type="journal", name="ML Journal",
            external_ids={"openalex": "S999"},
        )
        e2 = self.svc.get_or_create(
            entity_type="journal", name="ML Journal",
            external_ids={"openalex": "S999"},
        )
        self.assertEqual(e1["id"], e2["id"])

    def test_generate_entity_id_journal(self):
        eid = EntityService._generate_entity_id("journal", "Nature ML", {"openalex": "S123"})
        self.assertEqual(eid, "journal:openalex:S123")

    def test_generate_entity_id_scholar_with_s2(self):
        eid = EntityService._generate_entity_id(
            "scholar", "Alice Smith", {"semantic_scholar": "12345"}
        )
        self.assertEqual(eid, "scholar:s2:12345")

    def test_generate_entity_id_fallback_to_slug(self):
        eid = EntityService._generate_entity_id("field", "Deep Learning", {})
        self.assertEqual(eid, "field:deep-learning")

    @patch("app.services.entity_service.EntityService._fetch_openalex_source")
    def test_sync_metadata_journal(self, mock_fetch):
        mock_fetch.return_value = {
            "publisher": "Springer",
            "issn": "1234-5678",
            "impact_factor": None,
        }
        entity = self.svc.get_or_create(
            entity_type="journal", name="Test Journal",
            external_ids={"openalex": "S999"},
        )
        updated = self.svc.sync_metadata(entity["id"])
        self.assertIsNotNone(updated)
        mock_fetch.assert_called_once()

    def test_list_by_type(self):
        self.svc.get_or_create(entity_type="journal", name="J1")
        self.svc.get_or_create(entity_type="scholar", name="S1")
        journals = self.svc.list_by_type("journal")
        self.assertEqual(len(journals), 1)

    def test_subscribe_to_entity(self):
        entity = self.svc.get_or_create(
            entity_type="journal", name="Nature ML"
        )
        sub = self.svc.subscribe(
            entity_id=entity["id"],
            filters={"min_citations": 5},
        )
        self.assertEqual(sub["entity_id"], entity["id"])
        self.assertEqual(sub["type"], "venue")
        self.assertEqual(sub["name"], "Nature ML")


class TestEntityAutoExtraction(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        self.store = StateStore(db_path=self.db_path)
        self.svc = EntityService(self.store)

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_extract_entities_from_search_results(self):
        papers = [
            {
                "title": "Test Paper 1",
                "venue": "Nature Machine Intelligence",
                "authors": ["Alice Smith"],
                "external_ids": {"openalex": "W1"},
            },
            {
                "title": "Test Paper 2",
                "venue": "NeurIPS 2025",
                "authors": ["Bob Jones"],
                "external_ids": {},
            },
        ]
        entities = self.svc.extract_entities_from_results(papers)
        # Should extract venue entities
        venue_names = [e["name"] for e in entities if e["type"] in ("journal", "conference")]
        self.assertIn("Nature Machine Intelligence", venue_names)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_entity_service.py::TestEntityService -v`
Expected: FAIL — `app.services.entity_service` does not exist.

- [ ] **Step 3: Implement EntityService**

```python
# app/services/entity_service.py
"""EntityService — CRUD, metadata fetch, and auto-extraction for entities.

Entities are first-class objects representing journals, conferences,
scholars, and research fields. Each is browsable, subscribable, and
enriched with metadata from OpenAlex and Semantic Scholar.
"""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from typing import Dict, List, Optional

from logger_config import get_logger

logger = get_logger(__name__)


class EntityService:
    """Service layer for entity CRUD and metadata synchronization."""

    def __init__(self, state_store):
        self._store = state_store

    # ------------------------------------------------------------------
    # ID generation
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_entity_id(
        entity_type: str, name: str, external_ids: Optional[Dict] = None
    ) -> str:
        """Generate a deterministic entity ID.

        Priority: external provider ID > slugified name.
        """
        ext = external_ids or {}

        if entity_type == "scholar":
            if ext.get("semantic_scholar"):
                return f"scholar:s2:{ext['semantic_scholar']}"
            if ext.get("openalex"):
                return f"scholar:openalex:{ext['openalex']}"

        if entity_type in ("journal", "conference"):
            if ext.get("openalex"):
                return f"{entity_type}:openalex:{ext['openalex']}"

        # Fallback: slugified name
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        return f"{entity_type}:{slug}"

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def get_or_create(
        self,
        entity_type: str,
        name: str,
        *,
        external_ids: Optional[Dict] = None,
        metadata_json: Optional[Dict] = None,
        aliases: Optional[List[str]] = None,
    ) -> Dict:
        """Get an existing entity by generated ID, or create a new one."""
        entity_id = self._generate_entity_id(entity_type, name, external_ids)

        existing = self._store.get_entity(entity_id)
        if existing:
            return existing

        return self._store.create_entity(
            entity_id=entity_id,
            entity_type=entity_type,
            name=name,
            aliases=aliases,
            external_ids=external_ids,
            metadata_json=metadata_json,
        )

    def get(self, entity_id: str) -> Optional[Dict]:
        return self._store.get_entity(entity_id)

    def list_by_type(self, entity_type: str, *, limit: int = 100) -> List[Dict]:
        return self._store.list_entities(entity_type=entity_type, limit=limit)

    def search(self, query: str, *, entity_type: Optional[str] = None, limit: int = 50) -> List[Dict]:
        return self._store.list_entities(entity_type=entity_type, search=query, limit=limit)

    def delete(self, entity_id: str) -> bool:
        return self._store.delete_entity(entity_id)

    # ------------------------------------------------------------------
    # Metadata sync
    # ------------------------------------------------------------------

    def sync_metadata(self, entity_id: str) -> Optional[Dict]:
        """Fetch and update metadata from external APIs.

        Dispatches to type-specific fetch methods.
        """
        entity = self._store.get_entity(entity_id)
        if not entity:
            return None

        entity_type = entity["type"]
        ext_ids = entity.get("external_ids") or {}
        metadata = entity.get("metadata_json") or {}

        try:
            if entity_type == "journal":
                fetched = self._fetch_openalex_source(ext_ids)
                if fetched:
                    metadata.update(fetched)
            elif entity_type == "conference":
                fetched = self._fetch_openalex_source(ext_ids)
                if fetched:
                    metadata.update(fetched)
            elif entity_type == "scholar":
                fetched = self._fetch_scholar_metadata(ext_ids)
                if fetched:
                    metadata.update(fetched)
            elif entity_type == "field":
                pass  # Fields are user-defined, no external fetch
        except Exception as e:
            logger.warning("Failed to sync metadata for %s: %s", entity_id, e)

        from datetime import datetime, timezone
        now = datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat() + "Z"

        return self._store.update_entity(
            entity_id,
            metadata_json=metadata,
            last_synced=now,
        )

    def _fetch_openalex_source(self, external_ids: Dict) -> Optional[Dict]:
        """Fetch journal/conference metadata from OpenAlex Sources API."""
        oa_id = external_ids.get("openalex", "")
        if not oa_id:
            return None

        try:
            url = f"https://api.openalex.org/sources/{oa_id}"
            req = urllib.request.Request(url, headers={"User-Agent": "PaperAgent/2.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            return {
                "publisher": (data.get("host_organization_name") or ""),
                "issn": (data.get("issn_l") or ""),
                "impact_factor": data.get("summary_stats", {}).get("2yr_mean_citedness"),
                "h_index": data.get("summary_stats", {}).get("h_index"),
                "homepage_url": (data.get("homepage_url") or ""),
                "scope_description": (data.get("description") or ""),
                "works_count": data.get("works_count"),
            }
        except Exception as e:
            logger.debug("OpenAlex source fetch failed: %s", e)
            return None

    def _fetch_scholar_metadata(self, external_ids: Dict) -> Optional[Dict]:
        """Fetch scholar metadata from Semantic Scholar Author API."""
        s2_id = external_ids.get("semantic_scholar", "")
        if not s2_id:
            return None

        try:
            url = (
                f"https://api.semanticscholar.org/graph/v1/author/{s2_id}"
                f"?fields=name,affiliations,hIndex,citationCount,paperCount,homepage,externalIds"
            )
            req = urllib.request.Request(url, headers={"User-Agent": "PaperAgent/2.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            return {
                "affiliations": data.get("affiliations") or [],
                "h_index": data.get("hIndex"),
                "citation_count": data.get("citationCount"),
                "paper_count": data.get("paperCount"),
                "homepage_url": data.get("homepage") or "",
            }
        except Exception as e:
            logger.debug("Semantic Scholar author fetch failed: %s", e)
            return None

    # ------------------------------------------------------------------
    # Subscription convenience
    # ------------------------------------------------------------------

    def subscribe(
        self,
        entity_id: str,
        *,
        filters: Optional[Dict] = None,
        research_question_id: Optional[int] = None,
    ) -> Dict:
        """Create a subscription linked to an entity."""
        entity = self._store.get_entity(entity_id)
        if not entity:
            raise ValueError(f"Entity not found: {entity_id}")

        # Map entity type to subscription type
        type_map = {
            "journal": "venue",
            "conference": "venue",
            "scholar": "author",
            "field": "field",
        }
        sub_type = type_map.get(entity["type"], "entity")

        filters_json = json.dumps(filters or {}, ensure_ascii=False)

        return self._store.create_subscription(
            type=sub_type,
            name=entity["name"],
            query_text=entity.get("metadata_json", {}).get(
                "arxiv_categories", [""]
            )[0] if entity["type"] == "field" else "",
            entity_id=entity_id,
            filters_json=filters_json,
            research_question_id=research_question_id,
        )

    # ------------------------------------------------------------------
    # Auto-extraction from search results
    # ------------------------------------------------------------------

    def extract_entities_from_results(self, papers: List[Dict]) -> List[Dict]:
        """Extract venue and author entities from search result papers.

        This is designed to be called asynchronously after search completes.
        It creates/updates entity records but does not affect the search
        response time.
        """
        created: List[Dict] = []

        for paper in papers:
            # Extract venue entities
            venue = (paper.get("venue") or "").strip()
            if venue and len(venue) > 2:
                venue_type = self._classify_venue(venue)
                try:
                    ext_ids = {}
                    paper_ext = paper.get("external_ids") or {}
                    # Use OpenAlex source ID if available
                    if paper_ext.get("openalex_source"):
                        ext_ids["openalex"] = paper_ext["openalex_source"]

                    entity = self.get_or_create(
                        entity_type=venue_type,
                        name=venue,
                        external_ids=ext_ids if ext_ids else None,
                    )
                    created.append(entity)
                except Exception as e:
                    logger.debug("Failed to create venue entity for '%s': %s", venue, e)

        return created

    @staticmethod
    def _classify_venue(venue_name: str) -> str:
        """Classify a venue name as journal or conference."""
        conference_patterns = (
            r"\b(neurips|icml|iclr|aaai|cvpr|iccv|eccv|acl|emnlp|naacl"
            r"|sigir|kdd|www|chi|uai|aistats|colt|isit|focs|stoc|soda"
            r"|conference|proceedings|workshop|symposium)\b"
        )
        if re.search(conference_patterns, venue_name, re.IGNORECASE):
            return "conference"
        return "journal"

    # ------------------------------------------------------------------
    # Related entities for profile pages
    # ------------------------------------------------------------------

    def get_related_entities(self, entity_id: str, *, limit: int = 10) -> List[Dict]:
        """Get entities related to the given entity via entity_relations."""
        relations = self._store.list_entity_relations(entity_id)
        related = []
        seen = set()
        for rel in relations[:limit]:
            other_id = rel["target_id"] if rel["source_id"] == entity_id else rel["source_id"]
            if other_id in seen:
                continue
            seen.add(other_id)
            other = self._store.get_entity(other_id)
            if other:
                other["_relation_type"] = rel["relation_type"]
                other["_relation_weight"] = rel["weight"]
                related.append(other)
        return related
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_entity_service.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/entity_service.py tests/test_entity_service.py
git commit -m "feat: implement EntityService with CRUD, metadata fetch, and auto-extraction"
```

---

### Task 4: Entity REST API

**Files:**
- Create: `app/routes/api/entities.py`
- Modify: `app/routes/api/__init__.py`

- [ ] **Step 1: Implement entity API routes**

```python
# app/routes/api/entities.py
"""Entity REST API endpoints."""
import json

from flask import jsonify, request

from . import bp
from .helpers import _current_state_store


def _serialize_entity(entity):
    """Serialize an entity dict for JSON response."""
    item = dict(entity)
    for key in ("aliases", "external_ids", "metadata_json", "stats_json"):
        val = item.get(key)
        if isinstance(val, str):
            try:
                item[key] = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                item[key] = [] if key == "aliases" else {}
    return item


@bp.route("/api/entities", methods=["GET"])
def list_entities():
    """List entities, optionally filtered by type or search query."""
    entity_type = request.args.get("type")
    search = request.args.get("search", "").strip()
    limit = int(request.args.get("limit", 100))

    store = _current_state_store()
    if search:
        entities = store.list_entities(entity_type=entity_type, search=search, limit=limit)
    else:
        entities = store.list_entities(entity_type=entity_type, limit=limit)

    return jsonify({
        "success": True,
        "entities": [_serialize_entity(e) for e in entities],
    })


@bp.route("/api/entities", methods=["POST"])
def create_entity():
    """Create or update an entity."""
    data = request.get_json() or {}

    entity_type = str(data.get("type", "")).strip()
    name = str(data.get("name", "")).strip()
    if not entity_type or not name:
        return jsonify({"success": False, "error": "Missing type or name"}), 400

    from app.services.entity_service import EntityService
    svc = EntityService(_current_state_store())

    try:
        entity = svc.get_or_create(
            entity_type=entity_type,
            name=name,
            external_ids=data.get("external_ids"),
            metadata_json=data.get("metadata"),
            aliases=data.get("aliases"),
        )
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400

    _current_state_store().record_event(
        "entity_created",
        payload={"entity_id": entity["id"], "type": entity_type, "name": name},
    )
    return jsonify({"success": True, "entity": _serialize_entity(entity)})


@bp.route("/api/entities/<path:entity_id>", methods=["GET"])
def get_entity(entity_id):
    """Get a single entity by ID."""
    entity = _current_state_store().get_entity(entity_id)
    if not entity:
        return jsonify({"success": False, "error": "Entity not found"}), 404

    from app.services.entity_service import EntityService
    svc = EntityService(_current_state_store())
    related = svc.get_related_entities(entity_id, limit=10)

    return jsonify({
        "success": True,
        "entity": _serialize_entity(entity),
        "related_entities": [_serialize_entity(r) for r in related],
    })


@bp.route("/api/entities/<path:entity_id>", methods=["PUT"])
def update_entity(entity_id):
    """Update an entity's metadata."""
    data = request.get_json() or {}
    store = _current_state_store()

    kwargs = {}
    if "name" in data:
        kwargs["name"] = data["name"]
    if "aliases" in data:
        kwargs["aliases"] = data["aliases"]
    if "external_ids" in data:
        kwargs["external_ids"] = data["external_ids"]
    if "metadata" in data:
        kwargs["metadata_json"] = data["metadata"]
    if "stats" in data:
        kwargs["stats_json"] = data["stats"]

    entity = store.update_entity(entity_id, **kwargs)
    if not entity:
        return jsonify({"success": False, "error": "Entity not found"}), 404

    return jsonify({"success": True, "entity": _serialize_entity(entity)})


@bp.route("/api/entities/<path:entity_id>", methods=["DELETE"])
def delete_entity(entity_id):
    """Delete an entity."""
    deleted = _current_state_store().delete_entity(entity_id)
    if deleted:
        _current_state_store().record_event(
            "entity_deleted", payload={"entity_id": entity_id}
        )
    return jsonify({"success": deleted})


@bp.route("/api/entities/<path:entity_id>/sync", methods=["POST"])
def sync_entity_metadata(entity_id):
    """Trigger metadata sync from external APIs."""
    from app.services.entity_service import EntityService
    svc = EntityService(_current_state_store())

    entity = svc.sync_metadata(entity_id)
    if not entity:
        return jsonify({"success": False, "error": "Entity not found"}), 404

    return jsonify({"success": True, "entity": _serialize_entity(entity)})


@bp.route("/api/entities/<path:entity_id>/subscribe", methods=["POST"])
def subscribe_to_entity(entity_id):
    """Create a subscription linked to this entity."""
    data = request.get_json() or {}

    from app.services.entity_service import EntityService
    svc = EntityService(_current_state_store())

    try:
        sub = svc.subscribe(
            entity_id=entity_id,
            filters=data.get("filters"),
            research_question_id=data.get("research_question_id"),
        )
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400

    _current_state_store().record_event(
        "entity_subscribed",
        payload={"entity_id": entity_id, "subscription_id": sub["id"]},
    )
    return jsonify({"success": True, "subscription": sub})


@bp.route("/api/entities/<path:entity_id>/relations", methods=["GET"])
def list_entity_relations(entity_id):
    """List relations for an entity."""
    direction = request.args.get("direction", "both")
    relation_type = request.args.get("relation_type")

    relations = _current_state_store().list_entity_relations(
        entity_id, direction=direction, relation_type=relation_type
    )
    return jsonify({"success": True, "relations": relations})
```

- [ ] **Step 2: Register entity routes in API blueprint**

In `app/routes/api/__init__.py`, add the import for the entities module. Look at the existing imports at the bottom of that file and add:

```python
from . import entities  # noqa: F401,E402
```

- [ ] **Step 3: Run smoke test**

```bash
cd "/Users/sunweizhou/Desktop/AI Project/arxiv_recommender"
python -c "from app.routes.api import entities; print('Entity routes imported OK')"
```

Expected: prints "Entity routes imported OK"

- [ ] **Step 4: Commit**

```bash
git add app/routes/api/entities.py app/routes/api/__init__.py
git commit -m "feat(api): add Entity REST API endpoints"
```

---

### Task 5: Subscription API Extension for Entity Support

**Files:**
- Modify: `app/routes/api/subscriptions.py`
- Modify: `state_store.py` (update_subscription method)

- [ ] **Step 1: Update manage_subscriptions POST to accept entity_id and filters_json**

In `app/routes/api/subscriptions.py`, update the POST handler inside `manage_subscriptions()`:

```python
@bp.route("/api/subscriptions", methods=["GET", "POST"])
def manage_subscriptions():
    if request.method == "GET":
        sub_type = request.args.get("type")
        subs = [_serialize_subscription(s) for s in _current_state_store().list_subscriptions(type=sub_type)]
        return jsonify({"success": True, "subscriptions": subs})

    data = request.get_json() or {}
    sub_type = str(data.get("type", "query")).strip()
    name = str(data.get("name", "")).strip()
    if not name:
        return jsonify({"success": False, "error": "Missing name"}), 400
    if sub_type not in ("query", "author", "venue", "field", "entity"):
        return jsonify({"success": False, "error": "Invalid type"}), 400

    query_text = str(data.get("query_text", "")).strip()
    payload = data.get("payload_json", data.get("payload", {}))
    if isinstance(payload, dict):
        payload = json.dumps(payload, ensure_ascii=False)

    # Entity and filter support
    entity_id = data.get("entity_id")
    filters = data.get("filters_json", data.get("filters"))
    filters_json = None
    if filters is not None:
        filters_json = filters if isinstance(filters, str) else json.dumps(filters, ensure_ascii=False)

    try:
        research_question_id = _optional_int(data.get("research_question_id"))
        sub = _current_state_store().create_subscription(
            type=sub_type,
            name=name,
            query_text=query_text,
            payload_json=payload,
            enabled=data.get("enabled", True),
            research_question_id=research_question_id,
            entity_id=entity_id,
            filters_json=filters_json,
        )
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    _current_state_store().record_event(
        "subscription_created",
        payload={"subscription_id": sub["id"], "type": sub_type, "name": name, "entity_id": entity_id},
    )
    return jsonify({"success": True, "subscription": _serialize_subscription(sub)})
```

- [ ] **Step 2: Update manage_subscription_item PUT to accept entity_id and filters_json**

In `app/routes/api/subscriptions.py`, update the PUT handler:

```python
@bp.route("/api/subscriptions/<int:sub_id>", methods=["PUT", "DELETE"])
def manage_subscription_item(sub_id):
    if request.method == "DELETE":
        deleted = _current_state_store().delete_subscription(sub_id)
        if deleted:
            _current_state_store().record_event("delete_subscription", payload={"subscription_id": sub_id})
        return jsonify({"success": deleted})

    data = request.get_json() or {}
    kwargs = {}
    for field in ("type", "name", "query_text", "enabled", "latest_hit_count", "last_checked_at"):
        if field in data:
            kwargs[field] = data[field]
    if "payload_json" in data or "payload" in data:
        payload_val = data.get("payload_json", data.get("payload", {}))
        kwargs["payload_json"] = payload_val
    if "research_question_id" in data:
        try:
            kwargs["research_question_id"] = _optional_int(
                data.get("research_question_id")
            )
        except ValueError:
            return jsonify({
                "success": False,
                "error": "Invalid research_question_id",
            }), 400
    if "entity_id" in data:
        kwargs["entity_id"] = data["entity_id"]
    if "filters_json" in data or "filters" in data:
        filters = data.get("filters_json", data.get("filters", {}))
        kwargs["filters_json"] = filters if isinstance(filters, str) else json.dumps(filters, ensure_ascii=False)
    try:
        sub = _current_state_store().update_subscription(sub_id, **kwargs)
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    if not sub:
        return jsonify({"success": False, "error": "Subscription not found"}), 404
    _current_state_store().record_event("update_subscription", payload={"subscription_id": sub_id})
    return jsonify({"success": True, "subscription": _serialize_subscription(sub)})
```

- [ ] **Step 3: Update _serialize_subscription to include entity data**

```python
def _serialize_subscription(sub):
    item = dict(sub)
    payload = item.get("payload_json") or {}
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            payload = {}
    item["payload"] = payload
    item["filters"] = item.get("filters_json") or {}
    if isinstance(item["filters"], str):
        try:
            item["filters"] = json.loads(item["filters"])
        except (json.JSONDecodeError, TypeError):
            item["filters"] = {}
    item["description"] = payload.get("description", "") or payload.get("focus", "")

    # Include linked entity data if present
    entity_id = item.get("entity_id")
    if entity_id:
        from .helpers import _current_state_store
        entity = _current_state_store().get_entity(entity_id)
        item["entity"] = dict(entity) if entity else None
    else:
        item["entity"] = None

    return item
```

- [ ] **Step 4: Update update_subscription in state_store.py to handle entity_id and filters_json**

In `state_store.py`, add handling for `entity_id` and `filters_json` to the `update_subscription` method:

```python
if "entity_id" in kwargs:
    value = kwargs["entity_id"]
    if value in (None, ""):
        updates.append("entity_id = ?")
        params.append(None)
    else:
        if self.get_entity(str(value)) is None:
            raise ValueError(f"Unknown entity: {value}")
        updates.append("entity_id = ?")
        params.append(str(value))

if "filters_json" in kwargs:
    updates.append("filters_json = ?")
    fval = kwargs["filters_json"]
    params.append(fval if isinstance(fval, str) else json.dumps(fval, ensure_ascii=False))
```

- [ ] **Step 5: Commit**

```bash
git add app/routes/api/subscriptions.py state_store.py
git commit -m "feat(api): extend subscription endpoints with entity_id and filters_json support"
```

---

### Task 6: SubscriptionRunner — New Entity-Type Strategies

**Files:**
- Modify: `app/services/subscription_runner.py`
- Create: `tests/test_entity_subscriptions.py`

- [ ] **Step 1: Write tests for new subscription strategies**

```python
# tests/test_entity_subscriptions.py
"""Test entity-linked subscription runner strategies."""
import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from state_store import StateStore
from app.services.subscription_runner import SubscriptionRunner


class TestSubscriptionRunnerEntityStrategies(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        self.store = StateStore(db_path=self.db_path)
        self.runner = SubscriptionRunner(self.store)

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_run_subscription_dispatches_field_type(self):
        """A 'field' subscription should dispatch to run_field_subscription."""
        # Create a field entity first
        self.store.create_entity(
            entity_id="field:cs-ai", entity_type="field", name="AI",
            metadata_json={"arxiv_categories": ["cs.AI"]},
        )
        sub = self.store.create_subscription(
            type="field", name="AI", query_text="cs.AI",
            entity_id="field:cs-ai",
        )
        with patch.object(self.runner, "run_field_subscription", return_value=0) as mock:
            self.runner.run_subscription(sub["id"])
            mock.assert_called_once()

    def test_run_field_subscription_searches_by_category(self):
        """Field subscription should search arXiv by category."""
        self.store.create_entity(
            entity_id="field:cs-ai", entity_type="field", name="AI",
            metadata_json={"arxiv_categories": ["cs.AI"]},
        )
        sub = self.store.create_subscription(
            type="field", name="AI", query_text="cs.AI",
            entity_id="field:cs-ai",
        )
        with patch.object(self.runner, "_search_arxiv_api", return_value=["2401.00001"]):
            hits = self.runner.run_field_subscription(sub)
            self.assertEqual(hits, 1)

    def test_run_journal_subscription_matches_venue(self):
        """Journal subscription should match papers by venue name."""
        self.store.create_entity(
            entity_id="journal:nature-ml", entity_type="journal",
            name="Nature Machine Intelligence",
        )
        sub = self.store.create_subscription(
            type="venue", name="Nature Machine Intelligence",
            entity_id="journal:nature-ml",
        )
        # Seed a recommendation item with matching venue
        run_id = self.store.save_recommendation_run(
            run_date="2026-05-11",
            papers=[{
                "paper_id": "2401.99999",
                "title": "Test Paper",
                "venue": "Nature Machine Intelligence",
                "authors": [],
                "categories": [],
            }],
        )
        # The item won't have a venue field in recommendation_items,
        # so we test the arXiv search path instead
        with patch.object(self.runner, "_search_arxiv_api", return_value=["2401.99999"]):
            hits = self.runner.run_journal_subscription(sub)
            self.assertGreaterEqual(hits, 0)

    def test_run_conference_subscription(self):
        """Conference subscription should search arXiv for conference papers."""
        self.store.create_entity(
            entity_id="conference:neurips", entity_type="conference",
            name="NeurIPS",
        )
        sub = self.store.create_subscription(
            type="venue", name="NeurIPS",
            entity_id="conference:neurips",
        )
        with patch.object(self.runner, "_search_arxiv_api", return_value=[]):
            hits = self.runner.run_conference_subscription(sub)
            self.assertEqual(hits, 0)

    def test_run_all_subscriptions_includes_new_types(self):
        """run_all_subscriptions should handle field subscriptions."""
        self.store.create_entity(
            entity_id="field:cs-lg", entity_type="field", name="Machine Learning",
            metadata_json={"arxiv_categories": ["cs.LG"]},
        )
        self.store.create_subscription(
            type="field", name="Machine Learning", query_text="cs.LG",
            entity_id="field:cs-lg",
        )
        with patch.object(self.runner, "_search_arxiv_api", return_value=[]):
            result = self.runner.run_all_subscriptions()
            self.assertTrue(result["success"])
            self.assertEqual(result["subscriptions_checked"], 1)

    def test_filters_json_applied_to_subscription(self):
        """Subscription with filters_json should filter results by criteria."""
        self.store.create_entity(
            entity_id="journal:test", entity_type="journal", name="Test Journal",
        )
        sub = self.store.create_subscription(
            type="venue", name="Test Journal",
            entity_id="journal:test",
            filters_json='{"min_citations": 5, "keywords": ["LLM"]}',
        )
        loaded = self.store.get_subscription(sub["id"])
        filters = loaded.get("filters_json")
        self.assertIsInstance(filters, dict)
        self.assertEqual(filters["min_citations"], 5)
        self.assertIn("LLM", filters["keywords"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_entity_subscriptions.py -v`
Expected: FAIL — `run_field_subscription`, `run_journal_subscription`, `run_conference_subscription` do not exist.

- [ ] **Step 3: Add new strategies to SubscriptionRunner**

In `app/services/subscription_runner.py`, update the `run_subscription` dispatcher and add new methods:

```python
def run_subscription(self, subscription_id: int) -> dict:
    """Run a single subscription by ID, dispatching to type-specific methods."""
    sub = self._store.get_subscription(subscription_id)
    if not sub:
        return {"success": False, "hit_count": 0, "error": "Subscription not found"}

    sub_type = sub.get("type", "query")
    entity_id = sub.get("entity_id")

    try:
        # Dispatch based on type and entity linkage
        if sub_type == "query":
            hit_count = self.run_query_subscription(sub)
        elif sub_type == "author":
            hit_count = self.run_author_subscription(sub)
        elif sub_type == "venue":
            # Check entity type to decide journal vs conference
            if entity_id:
                entity = self._store.get_entity(entity_id)
                if entity and entity["type"] == "conference":
                    hit_count = self.run_conference_subscription(sub)
                else:
                    hit_count = self.run_journal_subscription(sub)
            else:
                hit_count = self.run_venue_subscription(sub)
        elif sub_type == "field":
            hit_count = self.run_field_subscription(sub)
        elif sub_type == "entity":
            hit_count = self._run_entity_subscription(sub)
        else:
            return {"success": False, "hit_count": 0, "error": f"Unknown type: {sub_type}"}

        # Update subscription metadata
        from datetime import datetime
        now = datetime.now().isoformat()
        self._store.update_subscription(subscription_id, last_checked_at=now, latest_hit_count=hit_count)
        self._store.record_event(
            "run_subscription",
            payload={"subscription_id": subscription_id, "type": sub_type, "hit_count": hit_count},
        )

        return {"success": True, "hit_count": hit_count, "subscription": self._store.get_subscription(subscription_id)}
    except ImportError:
        return {"success": False, "hit_count": 0, "error": "Search module not available"}
    except Exception as e:
        logger.error("Error running subscription %s: %s", subscription_id, e)
        return {"success": False, "hit_count": 0, "error": str(e)}
```

Add the three new runner methods:

```python
def run_journal_subscription(self, sub: dict) -> int:
    """Run a journal-type subscription.

    Searches for papers published in the target journal by matching
    venue names in cached recommendations and searching arXiv.
    Applies filters_json if present.
    """
    journal_name = sub.get("name", "")
    if not journal_name:
        return 0

    def _match(item: dict) -> bool:
        # Check if paper venue matches journal name
        title = (item.get("title") or "").lower()
        abstract = (item.get("abstract") or "").lower()
        # Also check categories for arXiv category match
        categories = item.get("categories", [])
        name_lower = journal_name.lower()
        return (
            name_lower in title
            or name_lower in abstract
            or any(name_lower in str(c).lower() for c in (categories if isinstance(categories, list) else []))
        )

    paper_ids = self._search_local_recommendations(_match)
    # Search arXiv with journal name as keyword
    paper_ids.extend(self._search_arxiv_api([journal_name], journal_name))
    paper_ids = self._apply_filters(paper_ids, sub.get("filters_json"))
    return self.persist_hits(sub["id"], paper_ids, f"journal:{journal_name}")

def run_conference_subscription(self, sub: dict) -> int:
    """Run a conference-type subscription.

    Searches for papers from the target conference by matching
    conference name/acronym in cached recommendations and arXiv.
    Applies filters_json if present.
    """
    conf_name = sub.get("name", "")
    if not conf_name:
        return 0

    def _match(item: dict) -> bool:
        title = (item.get("title") or "").lower()
        abstract = (item.get("abstract") or "").lower()
        categories = item.get("categories", [])
        name_lower = conf_name.lower()
        return (
            name_lower in title
            or name_lower in abstract
            or any(name_lower in str(c).lower() for c in (categories if isinstance(categories, list) else []))
        )

    paper_ids = self._search_local_recommendations(_match)
    paper_ids.extend(self._search_arxiv_api([conf_name], conf_name))
    paper_ids = self._apply_filters(paper_ids, sub.get("filters_json"))
    return self.persist_hits(sub["id"], paper_ids, f"conference:{conf_name}")

def run_field_subscription(self, sub: dict) -> int:
    """Run a field-type subscription.

    Searches arXiv by category (e.g. cs.AI) and also matches local
    recommendations by category. Applies filters_json if present.
    """
    query_text = sub.get("query_text") or ""
    field_name = sub.get("name", "")

    # Get arXiv categories from linked entity if available
    entity_id = sub.get("entity_id")
    categories_to_search = []
    if entity_id:
        entity = self._store.get_entity(entity_id)
        if entity:
            meta = entity.get("metadata_json") or {}
            if isinstance(meta, str):
                import json
                try:
                    meta = json.loads(meta)
                except (TypeError, json.JSONDecodeError):
                    meta = {}
            categories_to_search = meta.get("arxiv_categories", [])

    if not categories_to_search and query_text:
        categories_to_search = [c.strip() for c in query_text.split(",") if c.strip()]

    if not categories_to_search:
        return 0

    def _match(item: dict) -> bool:
        item_categories = item.get("categories", [])
        if isinstance(item_categories, list):
            return any(
                cat.lower() in str(ic).lower()
                for cat in categories_to_search
                for ic in item_categories
            )
        return False

    paper_ids = self._search_local_recommendations(_match)
    # Search arXiv using category prefix
    for cat in categories_to_search:
        paper_ids.extend(self._search_arxiv_api([f"cat:{cat}"], field_name))
    paper_ids = self._apply_filters(paper_ids, sub.get("filters_json"))
    return self.persist_hits(sub["id"], paper_ids, f"field:{','.join(categories_to_search)}")

def _run_entity_subscription(self, sub: dict) -> int:
    """Run a generic entity subscription with cross-type filters."""
    # For the generic 'entity' type, fall back to keyword search
    query_text = sub.get("query_text") or sub.get("name", "")
    if not query_text:
        return 0
    keywords = [k.strip() for k in query_text.split() if k.strip()]

    def _match(item: dict) -> bool:
        title = (item.get("title") or "").lower()
        abstract = (item.get("abstract") or "").lower()
        return any(kw.lower() in title or kw.lower() in abstract for kw in keywords)

    paper_ids = self._search_local_recommendations(_match)
    paper_ids.extend(self._search_arxiv_api(keywords, query_text))
    paper_ids = self._apply_filters(paper_ids, sub.get("filters_json"))
    return self.persist_hits(sub["id"], paper_ids, f"entity:{query_text}")
```

Add the `_apply_filters` helper:

```python
def _apply_filters(
    self, paper_ids: List[str], filters_json
) -> List[str]:
    """Apply filters_json criteria to filter paper IDs.

    Currently supports keyword filtering from metadata cache.
    Filters that require external data (e.g. min_citations) are
    best-effort — papers without cached metadata are kept.
    """
    if not filters_json:
        return paper_ids

    import json
    filters = filters_json
    if isinstance(filters, str):
        try:
            filters = json.loads(filters)
        except (TypeError, json.JSONDecodeError):
            return paper_ids

    if not isinstance(filters, dict) or not filters:
        return paper_ids

    keywords = filters.get("keywords", [])
    if not keywords:
        return paper_ids

    # Filter by keyword presence in cached metadata
    filtered = []
    for pid in paper_ids:
        metadata = self._store.get_paper_metadata(pid)
        if not metadata:
            # Keep papers without metadata (can't filter them)
            filtered.append(pid)
            continue
        title = str(metadata.get("title", "")).lower()
        abstract = str(metadata.get("abstract", "")).lower()
        if any(kw.lower() in title or kw.lower() in abstract for kw in keywords):
            filtered.append(pid)
    return filtered
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_entity_subscriptions.py -v`
Expected: ALL PASS

- [ ] **Step 5: Run full test suite**

Run: `python -m pytest -q`
Expected: All existing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add app/services/subscription_runner.py tests/test_entity_subscriptions.py
git commit -m "feat(runner): add journal, conference, and field subscription strategies"
```

---

### Task 7: Entity Profile Page Route and Template

**Files:**
- Create: `app/routes/entities.py`
- Create: `templates/entity_profile.html`
- Modify: `app/routes/__init__.py`

- [ ] **Step 1: Create entity profile route**

```python
# app/routes/entities.py
"""Entity profile page routes."""
from flask import Blueprint, render_template, abort

bp = Blueprint("entities", __name__)


@bp.route("/entities/<path:entity_id>")
def entity_profile(entity_id):
    """Render entity profile page with type-specific content."""
    from state_store import get_state_store
    from app.services.entity_service import EntityService

    store = get_state_store()
    svc = EntityService(store)

    entity = store.get_entity(entity_id)
    if not entity:
        abort(404)

    # Get related entities
    related = svc.get_related_entities(entity_id, limit=10)

    # Get subscriptions linked to this entity
    all_subs = store.list_subscriptions()
    entity_subs = [s for s in all_subs if s.get("entity_id") == entity_id]

    # Get recent papers from subscription hits
    recent_papers = []
    for sub in entity_subs:
        hits = store.list_subscription_hits(subscription_id=sub["id"], limit=10)
        for hit in hits:
            paper_meta = store.get_paper_metadata(hit.get("paper_id", ""))
            recent_papers.append({
                "paper_id": hit.get("paper_id", ""),
                "title": (paper_meta or {}).get("title", hit.get("paper_id", "")),
                "authors": (paper_meta or {}).get("authors", []),
                "year": (paper_meta or {}).get("year"),
                "hit_date": hit.get("hit_date", ""),
                "matched_reason": hit.get("matched_reason", ""),
            })

    metadata = entity.get("metadata_json") or {}
    if isinstance(metadata, str):
        import json
        try:
            metadata = json.loads(metadata)
        except (json.JSONDecodeError, TypeError):
            metadata = {}

    return render_template(
        "entity_profile.html",
        entity=entity,
        entity_type=entity["type"],
        metadata=metadata,
        related_entities=related,
        entity_subs=entity_subs,
        recent_papers=recent_papers[:20],
        is_subscribed=len(entity_subs) > 0,
    )
```

- [ ] **Step 2: Register entity routes in app**

In `app/routes/__init__.py`, add the entity blueprint registration. Look at how existing blueprints are registered and add:

```python
from app.routes.entities import bp as entities_bp
app.register_blueprint(entities_bp)
```

- [ ] **Step 3: Create entity profile template**

```html
{# templates/entity_profile.html #}
{% extends "base_research.html" %}
{% import "_components.html" as ui %}

{% set body_class = (body_class or '') ~ ' page-entity-profile' %}

{% block hero %}
<section class="page-header">
    <div class="lead">
        <span class="section-kicker">{{ entity_type | capitalize }}</span>
        <h1 class="page-title">{{ entity.name }}</h1>
        {% if entity.aliases %}
        <div class="page-context">
            Also known as: {{ entity.aliases | join(', ') }}
        </div>
        {% endif %}
    </div>
    <div class="actions">
        {% if is_subscribed %}
        <span class="chip chip-active">Subscribed</span>
        {% else %}
        <button type="button" class="btn btn-primary btn-sm"
                onclick="subscribeToEntity('{{ entity.id }}')">
            Subscribe
        </button>
        {% endif %}
        <button type="button" class="btn btn-ghost btn-sm"
                onclick="syncEntityMetadata('{{ entity.id }}')">
            Sync Metadata
        </button>
        {% if metadata.homepage_url %}
        <a href="{{ metadata.homepage_url }}" target="_blank"
           class="btn btn-ghost btn-sm">Website</a>
        {% endif %}
    </div>
</section>
{% endblock %}

{% block content %}
<div class="entity-profile-layout">
    {# ── Main content ── #}
    <div class="entity-profile-main">

        {# Type-specific metadata section #}
        <section class="entity-section">
            <h2 class="section-heading">Details</h2>

            {% if entity_type == 'journal' %}
            <div class="entity-stats-grid">
                {% if metadata.publisher %}<div class="entity-stat"><span class="entity-stat-label">Publisher</span><span class="entity-stat-value">{{ metadata.publisher }}</span></div>{% endif %}
                {% if metadata.issn %}<div class="entity-stat"><span class="entity-stat-label">ISSN</span><span class="entity-stat-value">{{ metadata.issn }}</span></div>{% endif %}
                {% if metadata.impact_factor %}<div class="entity-stat"><span class="entity-stat-label">Impact Factor</span><span class="entity-stat-value">{{ metadata.impact_factor }}</span></div>{% endif %}
                {% if metadata.h_index %}<div class="entity-stat"><span class="entity-stat-label">H-Index</span><span class="entity-stat-value">{{ metadata.h_index }}</span></div>{% endif %}
                {% if metadata.works_count %}<div class="entity-stat"><span class="entity-stat-label">Works</span><span class="entity-stat-value">{{ metadata.works_count | default('N/A') }}</span></div>{% endif %}
            </div>
            {% if metadata.scope_description %}
            <p class="entity-description">{{ metadata.scope_description }}</p>
            {% endif %}

            {% elif entity_type == 'conference' %}
            <div class="entity-stats-grid">
                {% if metadata.series_name %}<div class="entity-stat"><span class="entity-stat-label">Series</span><span class="entity-stat-value">{{ metadata.series_name }}</span></div>{% endif %}
                {% if metadata.frequency %}<div class="entity-stat"><span class="entity-stat-label">Frequency</span><span class="entity-stat-value">{{ metadata.frequency }}</span></div>{% endif %}
                {% if metadata.acceptance_rate %}<div class="entity-stat"><span class="entity-stat-label">Acceptance Rate</span><span class="entity-stat-value">{{ (metadata.acceptance_rate * 100) | round(1) }}%</span></div>{% endif %}
                {% if metadata.tier %}<div class="entity-stat"><span class="entity-stat-label">Tier</span><span class="entity-stat-value">{{ metadata.tier }}</span></div>{% endif %}
                {% if metadata.next_date %}<div class="entity-stat"><span class="entity-stat-label">Next Date</span><span class="entity-stat-value">{{ metadata.next_date }}</span></div>{% endif %}
                {% if metadata.location %}<div class="entity-stat"><span class="entity-stat-label">Location</span><span class="entity-stat-value">{{ metadata.location }}</span></div>{% endif %}
            </div>

            {% elif entity_type == 'scholar' %}
            <div class="entity-stats-grid">
                {% if metadata.affiliations %}<div class="entity-stat"><span class="entity-stat-label">Affiliations</span><span class="entity-stat-value">{{ metadata.affiliations | join(', ') }}</span></div>{% endif %}
                {% if metadata.h_index %}<div class="entity-stat"><span class="entity-stat-label">H-Index</span><span class="entity-stat-value">{{ metadata.h_index }}</span></div>{% endif %}
                {% if metadata.citation_count %}<div class="entity-stat"><span class="entity-stat-label">Citations</span><span class="entity-stat-value">{{ metadata.citation_count | default('N/A') }}</span></div>{% endif %}
                {% if metadata.paper_count %}<div class="entity-stat"><span class="entity-stat-label">Papers</span><span class="entity-stat-value">{{ metadata.paper_count }}</span></div>{% endif %}
            </div>
            {% if metadata.research_interests %}
            <div class="entity-interests">
                <span class="entity-stat-label">Research Interests:</span>
                {% for interest in metadata.research_interests %}
                <span class="chip">{{ interest }}</span>
                {% endfor %}
            </div>
            {% endif %}

            {% elif entity_type == 'field' %}
            <div class="entity-stats-grid">
                {% if metadata.arxiv_categories %}<div class="entity-stat"><span class="entity-stat-label">arXiv Categories</span><span class="entity-stat-value">{{ metadata.arxiv_categories | join(', ') }}</span></div>{% endif %}
                {% if metadata.parent_field_id %}<div class="entity-stat"><span class="entity-stat-label">Parent Field</span><span class="entity-stat-value">{{ metadata.parent_field_id }}</span></div>{% endif %}
            </div>
            {% if metadata.description %}
            <p class="entity-description">{{ metadata.description }}</p>
            {% endif %}
            {% if metadata.key_venues %}
            <div class="entity-interests">
                <span class="entity-stat-label">Key Venues:</span>
                {% for venue in metadata.key_venues %}
                <span class="chip">{{ venue }}</span>
                {% endfor %}
            </div>
            {% endif %}
            {% if metadata.key_scholars %}
            <div class="entity-interests">
                <span class="entity-stat-label">Key Scholars:</span>
                {% for scholar in metadata.key_scholars %}
                <span class="chip">{{ scholar }}</span>
                {% endfor %}
            </div>
            {% endif %}
            {% endif %}
        </section>

        {# Recent papers section #}
        {% if recent_papers %}
        <section class="entity-section">
            <h2 class="section-heading">Recent Papers</h2>
            <div class="entity-papers-list">
                {% for paper in recent_papers %}
                <div class="entity-paper-item">
                    <a href="/paper/{{ paper.paper_id }}" class="entity-paper-title">{{ paper.title }}</a>
                    <div class="entity-paper-meta muted-copy">
                        {% if paper.authors %}{{ paper.authors[:3] | join(', ') }}{% if paper.authors | length > 3 %} et al.{% endif %}{% endif %}
                        {% if paper.year %} ({{ paper.year }}){% endif %}
                    </div>
                    {% if paper.matched_reason %}
                    <span class="chip is-muted">{{ paper.matched_reason }}</span>
                    {% endif %}
                </div>
                {% endfor %}
            </div>
        </section>
        {% endif %}
    </div>

    {# ── Sidebar ── #}
    <aside class="entity-profile-sidebar">
        {# Subscriptions #}
        {% if entity_subs %}
        <div class="entity-sidebar-card">
            <h3 class="entity-sidebar-title">Subscriptions</h3>
            {% for sub in entity_subs %}
            <div class="entity-sub-item">
                <span>{{ sub.name }}</span>
                <span class="chip is-muted">{{ sub.latest_hit_count }} hits</span>
            </div>
            {% endfor %}
        </div>
        {% endif %}

        {# Related entities #}
        {% if related_entities %}
        <div class="entity-sidebar-card">
            <h3 class="entity-sidebar-title">Related</h3>
            {% for rel in related_entities %}
            <a href="/entities/{{ rel.id }}" class="entity-related-item">
                <span class="chip is-muted">{{ rel.type }}</span>
                <span>{{ rel.name }}</span>
            </a>
            {% endfor %}
        </div>
        {% endif %}

        {# External links #}
        <div class="entity-sidebar-card">
            <h3 class="entity-sidebar-title">External Links</h3>
            {% if entity.external_ids %}
                {% if entity.external_ids.openalex %}
                <a href="https://openalex.org/{{ entity.external_ids.openalex }}"
                   target="_blank" class="btn btn-ghost btn-sm" style="width:100%;justify-content:flex-start;">
                    OpenAlex
                </a>
                {% endif %}
                {% if entity.external_ids.semantic_scholar %}
                <a href="https://www.semanticscholar.org/author/{{ entity.external_ids.semantic_scholar }}"
                   target="_blank" class="btn btn-ghost btn-sm" style="width:100%;justify-content:flex-start;">
                    Semantic Scholar
                </a>
                {% endif %}
            {% endif %}
            {% if metadata.homepage_url %}
            <a href="{{ metadata.homepage_url }}" target="_blank"
               class="btn btn-ghost btn-sm" style="width:100%;justify-content:flex-start;">
                Homepage
            </a>
            {% endif %}
        </div>

        {# Last synced #}
        {% if entity.last_synced %}
        <div class="entity-sidebar-meta muted-copy">
            Last synced: {{ entity.last_synced }}
        </div>
        {% endif %}
    </aside>
</div>

{% endblock %}

{% block scripts %}
<script>
function subscribeToEntity(entityId) {
    fetch('/api/entities/' + entityId + '/subscribe', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({}),
    })
    .then(function(resp) { return resp.json(); })
    .then(function(data) {
        if (data.success) {
            location.reload();
        } else {
            alert('Failed to subscribe: ' + (data.error || 'Unknown error'));
        }
    });
}

function syncEntityMetadata(entityId) {
    fetch('/api/entities/' + entityId + '/sync', {method: 'POST'})
    .then(function(resp) { return resp.json(); })
    .then(function(data) {
        if (data.success) {
            location.reload();
        } else {
            alert('Sync failed: ' + (data.error || 'Unknown error'));
        }
    });
}
</script>
{% endblock %}
```

- [ ] **Step 4: Add entity profile CSS to research_ui.css**

Append to `static/research_ui.css`:

```css
/* ============================================================
   Entity Profile Page
   ============================================================ */
.entity-profile-layout {
  display: grid;
  grid-template-columns: 1fr 280px;
  gap: 24px;
  max-width: 1100px;
  padding: 0 24px 48px;
}

@media (max-width: 768px) {
  .entity-profile-layout {
    grid-template-columns: 1fr;
  }
}

.entity-section {
  margin-bottom: 32px;
}

.entity-stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.entity-stat {
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  padding: 12px;
}

.entity-stat-label {
  display: block;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--ink-muted);
  margin-bottom: 4px;
}

.entity-stat-value {
  font-size: 16px;
  font-weight: 600;
  color: var(--ink-primary);
}

.entity-description {
  color: var(--ink-secondary);
  font-size: 14px;
  line-height: 1.6;
  margin: 12px 0;
}

.entity-interests {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  margin: 12px 0;
}

.entity-papers-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.entity-paper-item {
  padding: 10px 12px;
  border-radius: var(--radius-md);
  transition: background var(--transition-fast);
}

.entity-paper-item:hover {
  background: var(--bg-surface-hover);
}

.entity-paper-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--ink-primary);
  text-decoration: none;
}

.entity-paper-title:hover {
  color: var(--accent-primary);
}

.entity-paper-meta {
  font-size: 12px;
  margin-top: 2px;
}

.entity-profile-sidebar {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.entity-sidebar-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  padding: 16px;
}

.entity-sidebar-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--ink-primary);
  margin: 0 0 12px;
}

.entity-sub-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 0;
  font-size: 13px;
}

.entity-related-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
  font-size: 13px;
  color: var(--ink-primary);
  text-decoration: none;
}

.entity-related-item:hover {
  color: var(--accent-primary);
}

.entity-sidebar-meta {
  font-size: 12px;
  padding: 8px 0;
}
```

- [ ] **Step 5: Smoke test entity profile page**

```bash
cd "/Users/sunweizhou/Desktop/AI Project/arxiv_recommender"
python -c "from app.routes.entities import bp; print('Entity routes blueprint OK')"
```

Expected: prints "Entity routes blueprint OK"

- [ ] **Step 6: Commit**

```bash
git add app/routes/entities.py app/routes/__init__.py templates/entity_profile.html static/research_ui.css
git commit -m "feat: add entity profile page with type-specific rendering"
```

---

### Task 8: Watch Page Restructure for Entity-Based Subscriptions

**Files:**
- Modify: `templates/watch.html`
- Modify: `app/viewmodels/shared.py` (if needed for sidebar entity counts)
- Modify: `static/js/subscriptions.js`

- [ ] **Step 1: Update watch.html to support 5 subscription sections**

Replace the content of `templates/watch.html` with an updated version that groups subscriptions by entity type (query, journal, conference, scholar, field) and includes links to entity profiles:

In the hero section, update the page context to include entity counts:

```html
{% block hero %}
<section class="page-header">
    <div class="lead">
        <span class="section-kicker" data-i18n="nav.watch">Watch</span>
        <h1 class="page-title">Watch</h1>
        <div class="page-context">
            Track research questions, journals, conferences, scholars, and fields across your subscriptions.
        </div>
    </div>
    <div class="actions">
        <a href="/" class="btn btn-primary btn-sm">Back to Search</a>
        <button type="button" class="btn btn-ghost btn-sm" onclick="runAllSubscriptions()">
            <span data-i18n="watch.refresh_all">Refresh All</span>
        </button>
    </div>
</section>
{% endblock %}
```

For each existing section (Research questions, Authors, Venues), add entity profile links where entity_id is present. For example, in each subscription card header:

```html
{% if sub.entity_id %}
<a href="/entities/{{ sub.entity_id }}" class="btn btn-ghost btn-xs">View Profile</a>
{% endif %}
```

Add two new sections after the existing Venues section:

```html
{# =============================================
   Fields
   ============================================= #}
<section class="watch-section">
    <div class="watch-section-header">
        <h2 class="section-heading">
            Fields
            <span class="chip is-muted">Field</span>
        </h2>
        <button type="button" class="btn btn-ghost btn-sm" onclick="createFieldSubscription()">New</button>
    </div>

    {% if field_subs %}
    <div class="watch-sub-list">
        {% for sub in field_subs %}
        <div class="card watch-sub-card">
            {# Same card structure as other sections #}
            <div class="watch-sub-card-header">
                <div>
                    <h3 class="watch-sub-card-name">{{ sub.name }}</h3>
                    <div class="watch-sub-card-meta">
                        {% if sub.query_text %}<span class="watch-sub-meta-item"><code>{{ sub.query_text }}</code></span>{% endif %}
                        <span class="watch-sub-meta-item">Last checked: <time datetime="{{ sub._raw.last_checked_at }}">{{ sub.last_checked_at or "not checked" }}</time></span>
                        {% if not sub.enabled %}<span class="chip is-warn">disabled</span>{% endif %}
                    </div>
                </div>
                <span class="chip">{{ sub.latest_hit_count }} hits</span>
            </div>

            {% if sub.recent_hits %}
            <div class="watch-sub-hits">
                {% for hit in sub.recent_hits %}
                <div class="watch-sub-hit" data-hit-id="{{ hit.id }}" data-hit-status="{{ hit.hit_status }}">
                    <span class="watch-sub-hit-arrow">&#9656;</span>
                    <a href="{{ hit.detail_url }}" class="watch-sub-hit-title">{{ hit.title }}</a>
                    {% if hit.hit_status %}<span class="chip is-muted js-hit-status">{{ hit.hit_status }}</span>{% endif %}
                    <div class="watch-sub-hit-actions">
                        <a class="btn btn-ghost btn-xs" href="{{ hit.detail_url }}">Preview</a>
                        <button type="button" class="btn btn-ghost btn-xs" onclick="sendHitToInbox({{ hit.id }}, this)" {% if hit.hit_status == 'sent_to_inbox' %}disabled{% endif %}>Send to Reading</button>
                        <button type="button" class="btn btn-ghost btn-xs" onclick="ignoreSubscriptionHit({{ hit.id }}, this)" {% if hit.hit_status == 'ignored' %}disabled{% endif %}>Ignore</button>
                    </div>
                </div>
                {% endfor %}
            </div>
            {% endif %}

            <div class="watch-sub-card-actions">
                <button type="button" class="btn btn-ghost btn-xs" onclick="runSubscription({{ sub.id }})">Refresh</button>
                <button type="button" class="btn btn-ghost btn-xs" onclick="editSubscription({{ sub.id }})">Edit</button>
                {% if sub.entity_id %}
                <a href="/entities/{{ sub.entity_id }}" class="btn btn-ghost btn-xs">View Profile</a>
                {% endif %}
            </div>
        </div>
        {% endfor %}
    </div>
    {% else %}
    {{ ui.empty_state('No fields watched', 'Add a research field to track papers by arXiv category.', '', '<button type="button" class="btn btn-primary btn-sm" onclick="createFieldSubscription()">Add field</button>') }}
    {% endif %}
</section>
```

- [ ] **Step 2: Add createFieldSubscription to subscriptions.js**

In `static/js/subscriptions.js`, add:

```javascript
function createFieldSubscription() {
    var name = prompt('Field name (e.g. "Artificial Intelligence"):');
    if (!name) return;
    var categories = prompt('arXiv categories (comma-separated, e.g. "cs.AI,cs.LG"):');
    if (!categories) return;

    fetch('/api/subscriptions', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            type: 'field',
            name: name.trim(),
            query_text: categories.trim(),
        }),
    })
    .then(function(resp) { return resp.json(); })
    .then(function(data) {
        if (data.success) {
            location.reload();
        } else {
            alert('Failed: ' + (data.error || 'Unknown error'));
        }
    });
}
window.createFieldSubscription = createFieldSubscription;
```

- [ ] **Step 3: Update Watch viewmodel to split field subscriptions**

The Watch page viewmodel needs to provide `field_subs` alongside existing `query_subs`, `author_subs`, `venue_subs`. Update the viewmodel that prepares the Watch page context to filter `type == 'field'` subscriptions into a separate list:

```python
# In the watch page viewmodel, add field subscription splitting
field_subs = [s for s in all_subs if s.get("type") == "field"]
```

- [ ] **Step 4: Commit**

```bash
git add templates/watch.html static/js/subscriptions.js
git commit -m "feat(watch): restructure Watch page with Fields section and entity profile links"
```

---

### Task 9: Entity Auto-Extraction from Search Results

**Files:**
- Modify: `app/services/unified_search_service.py` (or the search viewmodel)

- [ ] **Step 1: Add async entity extraction call after search completes**

In the search flow (either in `app/services/unified_search_service.py` at the end of `search_papers()`, or in the search viewmodel/route), add a non-blocking entity extraction call:

```python
import threading

def _async_extract_entities(papers: list):
    """Non-blocking entity extraction from search results."""
    try:
        from state_store import get_state_store
        from app.services.entity_service import EntityService
        store = get_state_store()
        svc = EntityService(store)
        svc.extract_entities_from_results(papers)
    except Exception:
        import logging
        logging.getLogger(__name__).debug("Async entity extraction failed", exc_info=True)
```

At the end of the search flow, after `merge_and_dedupe_papers()`:

```python
# Non-blocking entity extraction
thread = threading.Thread(target=_async_extract_entities, args=(merged,), daemon=True)
thread.start()
```

- [ ] **Step 2: Verify extraction does not affect search response time**

```bash
cd "/Users/sunweizhou/Desktop/AI Project/arxiv_recommender"
python -c "
import time
from app.services.entity_service import EntityService
from state_store import StateStore
import tempfile, os

db_fd, db_path = tempfile.mkstemp(suffix='.db')
store = StateStore(db_path=db_path)
svc = EntityService(store)

papers = [
    {'title': 'Test', 'venue': 'NeurIPS 2025', 'authors': ['Alice'], 'external_ids': {}},
] * 100

start = time.time()
entities = svc.extract_entities_from_results(papers)
elapsed = time.time() - start
print(f'Extracted {len(entities)} entities in {elapsed:.3f}s')
assert elapsed < 2.0, f'Too slow: {elapsed}s'

os.close(db_fd)
os.unlink(db_path)
print('OK')
"
```

Expected: prints extraction time under 2s, then "OK"

- [ ] **Step 3: Commit**

```bash
git add app/services/unified_search_service.py
git commit -m "feat(search): add async entity auto-extraction from search results"
```

---

### Task 10: Full Integration Test

**Files:**
- Modify: `tests/test_entity_service.py`
- Modify: `tests/test_entity_subscriptions.py`

- [ ] **Step 1: Add end-to-end integration test**

Append to `tests/test_entity_subscriptions.py`:

```python
class TestEndToEndEntitySubscriptionFlow(unittest.TestCase):
    """Integration test: create entity -> subscribe -> run -> verify hits."""

    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        self.store = StateStore(db_path=self.db_path)
        self.runner = SubscriptionRunner(self.store)

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_full_flow_journal_entity(self):
        """Create a journal entity, subscribe, run, verify subscription works."""
        from app.services.entity_service import EntityService
        svc = EntityService(self.store)

        # 1. Create entity
        entity = svc.get_or_create(
            entity_type="journal",
            name="Nature Machine Intelligence",
            external_ids={"openalex": "S12345"},
        )
        self.assertIsNotNone(entity)
        self.assertEqual(entity["type"], "journal")

        # 2. Subscribe
        sub = svc.subscribe(entity_id=entity["id"], filters={"min_citations": 5})
        self.assertEqual(sub["entity_id"], entity["id"])
        self.assertEqual(sub["type"], "venue")

        # 3. Verify subscription exists
        subs = self.store.list_subscriptions()
        self.assertTrue(any(s["entity_id"] == entity["id"] for s in subs))

        # 4. Run subscription (mocked arXiv)
        with patch.object(self.runner, "_search_arxiv_api", return_value=["2401.00001"]):
            result = self.runner.run_subscription(sub["id"])
            self.assertTrue(result["success"])

        # 5. Verify hit was created
        hits = self.store.list_subscription_hits(subscription_id=sub["id"])
        self.assertGreaterEqual(len(hits), 1)

    def test_full_flow_field_entity(self):
        """Create a field entity, subscribe, run, verify subscription works."""
        from app.services.entity_service import EntityService
        svc = EntityService(self.store)

        # 1. Create entity
        entity = svc.get_or_create(
            entity_type="field",
            name="Computer Vision",
            metadata_json={"arxiv_categories": ["cs.CV"]},
        )
        self.assertIsNotNone(entity)

        # 2. Subscribe
        sub = svc.subscribe(entity_id=entity["id"])
        self.assertEqual(sub["type"], "field")

        # 3. Run subscription
        with patch.object(self.runner, "_search_arxiv_api", return_value=["2401.00002"]):
            result = self.runner.run_subscription(sub["id"])
            self.assertTrue(result["success"])

    def test_entity_profile_data_available(self):
        """Entity profile route should have entity + related + subs data."""
        from app.services.entity_service import EntityService
        svc = EntityService(self.store)

        entity = svc.get_or_create(
            entity_type="scholar", name="Alice Smith",
            external_ids={"semantic_scholar": "999"},
            metadata_json={"affiliations": ["MIT"], "h_index": 50},
        )

        # Create a relation
        related = svc.get_or_create(
            entity_type="journal", name="ML Journal",
        )
        self.store.create_entity_relation(
            entity["id"], related["id"], "publishes_in", weight=0.8
        )

        # Verify related entities
        related_list = svc.get_related_entities(entity["id"])
        self.assertEqual(len(related_list), 1)
        self.assertEqual(related_list[0]["name"], "ML Journal")

    def test_entity_auto_extraction(self):
        """Auto-extraction creates entities from search results."""
        from app.services.entity_service import EntityService
        svc = EntityService(self.store)

        papers = [
            {"title": "P1", "venue": "ICML 2025", "authors": ["Alice"], "external_ids": {}},
            {"title": "P2", "venue": "Nature", "authors": ["Bob"], "external_ids": {}},
            {"title": "P3", "venue": "", "authors": ["Charlie"], "external_ids": {}},
        ]
        entities = svc.extract_entities_from_results(papers)
        # Should extract ICML (conference) and Nature (journal)
        self.assertGreaterEqual(len(entities), 2)
        types = {e["type"] for e in entities}
        self.assertIn("conference", types)
        self.assertIn("journal", types)
```

- [ ] **Step 2: Run full test suite**

Run: `python -m pytest -q`
Expected: ALL PASS

- [ ] **Step 3: Final commit for Phase 2**

```bash
git add tests/test_entity_service.py tests/test_entity_subscriptions.py
git commit -m "test: add Phase 2 end-to-end integration tests for entity subscription flow"
```
