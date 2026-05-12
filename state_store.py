"""SQLite-backed state store for durable app state.

This module externalizes mutable state from the Flask routes so the app can
grow in small, auditable slices instead of scattering more JSON files.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)

from app_paths import STATE_DB_PATH, ensure_runtime_dirs

JOB_STATUS_VALUES = ("queued", "running", "succeeded", "degraded", "failed")
QUEUE_STATUS_VALUES = ("Inbox", "Skim Later", "Deep Read", "Saved", "Archived")


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat() + "Z"


def _utc_bounds_for_local_date(date_str: str) -> tuple[str, str]:
    """Return UTC timestamp bounds for a YYYY-MM-DD date in system local time."""
    day = datetime.strptime(date_str, "%Y-%m-%d").date()
    local_tz = datetime.now().astimezone().tzinfo
    start_local = datetime.combine(day, datetime.min.time()).replace(tzinfo=local_tz)
    end_local = start_local + timedelta(days=1)
    start_utc = start_local.astimezone(timezone.utc).replace(microsecond=0)
    end_utc = end_local.astimezone(timezone.utc).replace(microsecond=0)
    return start_utc.isoformat() + "Z", end_utc.isoformat() + "Z"


def _to_json(value: Optional[object], default: object) -> str:
    return json.dumps(value if value is not None else default, ensure_ascii=False)


def _canonical_paper_id(paper_id: str) -> str:
    value = str(paper_id or "").strip()
    match = re.search(r"(\d{4}\.\d{4,5})(v\d+)?", value)
    if match:
        return match.group(1)
    return re.sub(r"v\d+$", "", value)


class StateStore:
    """Thin service layer around a local SQLite database."""

    def __init__(self, db_path: str = str(STATE_DB_PATH)):
        ensure_runtime_dirs()
        self.db_path = db_path
        self._lock = threading.Lock()
        self._initialize()
        self._auto_migrate_once()

    @staticmethod
    def _add_column_if_missing(
        conn: sqlite3.Connection,
        table_name: str,
        column_name: str,
        column_sql: str,
    ) -> None:
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        existing = {row["name"] for row in rows}
        if column_name not in existing:
            conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_sql}")

    @contextmanager
    def _connect(self) -> Iterable[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _initialize(self) -> None:
        with self._lock, self._connect() as conn:
            conn.executescript(
                """
                PRAGMA journal_mode=WAL;

                CREATE TABLE IF NOT EXISTS schema_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS job_runs (
                    run_id TEXT PRIMARY KEY,
                    job_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    trigger_source TEXT NOT NULL DEFAULT 'unknown',
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    result_json TEXT NOT NULL DEFAULT '{}',
                    error_text TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT
                );

                CREATE TABLE IF NOT EXISTS research_collections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT NOT NULL DEFAULT '',
                    query_text TEXT NOT NULL DEFAULT '',
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS collection_papers (
                    collection_id INTEGER NOT NULL,
                    paper_id TEXT NOT NULL,
                    note TEXT NOT NULL DEFAULT '',
                    added_at TEXT NOT NULL,
                    PRIMARY KEY (collection_id, paper_id),
                    FOREIGN KEY (collection_id)
                        REFERENCES research_collections(id)
                        ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS saved_searches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    query_text TEXT NOT NULL,
                    filters_json TEXT NOT NULL DEFAULT '{}',
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS reading_queue_items (
                    paper_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT '',
                    note TEXT NOT NULL DEFAULT '',
                    tags_json TEXT NOT NULL DEFAULT '[]',
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS interaction_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    paper_id TEXT NOT NULL DEFAULT '',
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS user_topic_affinity (
                    topic TEXT PRIMARY KEY,
                    positive_score REAL NOT NULL DEFAULT 0.0,
                    negative_score REAL NOT NULL DEFAULT 0.0,
                    source_event_count INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS paper_ai_analyses (
                    paper_id TEXT PRIMARY KEY,
                    one_sentence_summary TEXT NOT NULL DEFAULT '',
                    problem TEXT NOT NULL DEFAULT '',
                    method TEXT NOT NULL DEFAULT '',
                    contribution TEXT NOT NULL DEFAULT '',
                    limitations TEXT NOT NULL DEFAULT '',
                    why_it_matters TEXT NOT NULL DEFAULT '',
                    recommended_reading_level TEXT NOT NULL DEFAULT 'skim',
                    model_name TEXT NOT NULL DEFAULT '',
                    prompt_version TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'ok',
                    error_text TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS subscriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT NOT NULL CHECK(type IN ('query', 'author', 'venue')),
                    name TEXT NOT NULL,
                    query_text TEXT DEFAULT '',
                    payload_json TEXT DEFAULT '{}',
                    enabled INTEGER DEFAULT 1,
                    latest_hit_count INTEGER DEFAULT 0,
                    last_checked_at TEXT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS subscription_hits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subscription_id INTEGER NOT NULL,
                    paper_id TEXT NOT NULL,
                    matched_reason TEXT DEFAULT '',
                    hit_date TEXT NOT NULL,
                    status TEXT DEFAULT 'new' CHECK(status IN ('new', 'sent_to_inbox', 'queued', 'ignored')),
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    FOREIGN KEY (subscription_id) REFERENCES subscriptions(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_subscriptions_type ON subscriptions(type);
                CREATE INDEX IF NOT EXISTS idx_subscriptions_enabled ON subscriptions(enabled);
                CREATE INDEX IF NOT EXISTS idx_subscription_hits_sub_id ON subscription_hits(subscription_id);
                CREATE INDEX IF NOT EXISTS idx_subscription_hits_paper_id ON subscription_hits(paper_id);
                CREATE INDEX IF NOT EXISTS idx_subscription_hits_status ON subscription_hits(status);

                CREATE TABLE IF NOT EXISTS recommendation_runs (
                    run_id TEXT PRIMARY KEY,
                    run_date TEXT NOT NULL,
                    trigger_source TEXT NOT NULL DEFAULT 'auto_homepage',
                    config_snapshot_json TEXT NOT NULL DEFAULT '{}',
                    themes_json TEXT NOT NULL DEFAULT '[]',
                    status TEXT NOT NULL DEFAULT 'completed',
                    paper_count INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    finished_at TEXT
                );

                CREATE TABLE IF NOT EXISTS recommendation_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL REFERENCES recommendation_runs(run_id),
                    paper_id TEXT NOT NULL,
                    rank INTEGER NOT NULL,
                    score REAL NOT NULL DEFAULT 0.0,
                    score_details_json TEXT NOT NULL DEFAULT '{}',
                    source_strategy TEXT DEFAULT 'for_you',
                    relevance_reason TEXT DEFAULT '',
                    title TEXT DEFAULT '',
                    authors_json TEXT DEFAULT '[]',
                    abstract TEXT DEFAULT '',
                    categories_json TEXT DEFAULT '[]',
                    source TEXT DEFAULT 'arxiv',
                    UNIQUE(run_id, paper_id)
                );

                CREATE INDEX IF NOT EXISTS idx_rec_runs_date ON recommendation_runs(run_date);
                CREATE INDEX IF NOT EXISTS idx_rec_items_run ON recommendation_items(run_id);
                CREATE INDEX IF NOT EXISTS idx_rec_items_paper ON recommendation_items(paper_id);

                CREATE TABLE IF NOT EXISTS paper_metadata (
                    paper_id TEXT PRIMARY KEY,
                    metadata_json TEXT,
                    created_at TEXT
                );

                CREATE TABLE IF NOT EXISTS paper_embeddings (
                    paper_id TEXT PRIMARY KEY,
                    embedding BLOB,
                    model_name TEXT,
                    created_at TEXT
                );

                CREATE TABLE IF NOT EXISTS research_questions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query_text TEXT NOT NULL,
                    intent_statement TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'active'
                        CHECK(status IN ('active', 'paused', 'archived')),
                    source TEXT NOT NULL DEFAULT 'manual'
                        CHECK(source IN ('manual', 'profile', 'subscription')),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS evidence_claims (
                    id TEXT PRIMARY KEY,
                    research_question_id INTEGER,
                    paper_id TEXT NOT NULL,
                    claim TEXT NOT NULL,
                    evidence_text TEXT NOT NULL DEFAULT '',
                    evidence_source TEXT NOT NULL DEFAULT 'abstract'
                        CHECK(evidence_source IN ('abstract', 'metadata', 'citation', 'user_note', 'other')),
                    claim_type TEXT NOT NULL DEFAULT 'factual'
                        CHECK(claim_type IN ('factual', 'interpretive', 'caveat', 'gap')),
                    analyst TEXT NOT NULL DEFAULT 'rule'
                        CHECK(analyst IN ('rule', 'llm', 'user')),
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (research_question_id) REFERENCES research_questions(id)
                );

                CREATE INDEX IF NOT EXISTS idx_research_questions_status
                    ON research_questions(status);
                CREATE INDEX IF NOT EXISTS idx_evidence_claims_paper
                    ON evidence_claims(paper_id);
                CREATE INDEX IF NOT EXISTS idx_evidence_claims_question
                    ON evidence_claims(research_question_id);

                CREATE TABLE IF NOT EXISTS feedback_models (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trained_at TEXT,
                    sample_count INTEGER,
                    auc REAL,
                    pickle_blob BLOB
                );

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
                    source_id      TEXT NOT NULL,
                    target_id      TEXT NOT NULL,
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

                CREATE TABLE IF NOT EXISTS agent_pending_confirmations (
                    token TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    message TEXT NOT NULL,
                    plan_json TEXT NOT NULL,
                    page_context_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending'
                );

                """
            )
            # Check current schema version and migrate if needed
            current_version_row = conn.execute(
                "SELECT value FROM schema_meta WHERE key = 'schema_version'"
            ).fetchone()
            current_version = int(current_version_row["value"]) if current_version_row else 0

            if current_version < 3:
                # Set/update schema version to 3 (was using INSERT OR IGNORE before,
                # which silently kept old versions like "2" — now we always advance)
                conn.execute(
                    "INSERT OR REPLACE INTO schema_meta(key, value) VALUES('schema_version', '3')"
                )

            if current_version < 4:
                conn.execute(
                    "INSERT OR REPLACE INTO schema_meta(key, value) VALUES('schema_version', '4')"
                )
            # Migrate existing tables: add themes_json to recommendation_runs if missing
            try:
                conn.execute("ALTER TABLE recommendation_runs ADD COLUMN themes_json TEXT NOT NULL DEFAULT '[]'")
            except sqlite3.OperationalError:
                pass  # Column already exists

            if current_version < 5:
                conn.execute(
                    "INSERT OR REPLACE INTO schema_meta(key, value) VALUES('schema_version', '5')"
                )
            # feedback_models table is created via CREATE TABLE IF NOT EXISTS above

            if current_version < 6:
                # paper_metadata table already created via CREATE TABLE IF NOT EXISTS above
                conn.execute(
                    "INSERT OR REPLACE INTO schema_meta(key, value) VALUES('schema_version', '6')"
                )
            already_migrated = conn.execute(
                "SELECT value FROM schema_meta WHERE key = 'arxiv_ids_migrated'"
            ).fetchone()
            if not already_migrated or already_migrated["value"] != "1":
                self._migrate_arxiv_paper_ids(conn)
                conn.execute(
                    "INSERT OR REPLACE INTO schema_meta(key, value) VALUES('arxiv_ids_migrated', '1')"
                )

            # Idempotent workspace column additions
            self._add_column_if_missing(
                conn, "paper_metadata", "source",
                "source TEXT NOT NULL DEFAULT ''",
            )
            self._add_column_if_missing(
                conn, "paper_metadata", "source_run_id",
                "source_run_id TEXT NOT NULL DEFAULT ''",
            )
            self._add_column_if_missing(
                conn, "paper_metadata", "first_seen_at",
                "first_seen_at TEXT NOT NULL DEFAULT ''",
            )
            self._add_column_if_missing(
                conn, "paper_metadata", "workspace_status",
                "workspace_status TEXT NOT NULL DEFAULT 'active'",
            )
            self._add_column_if_missing(
                conn, "reading_queue_items", "research_question_id",
                "research_question_id INTEGER",
            )
            self._add_column_if_missing(
                conn, "reading_queue_items", "decision_context",
                "decision_context TEXT NOT NULL DEFAULT ''",
            )
            self._add_column_if_missing(
                conn, "paper_ai_analyses", "evidence_claim_ids",
                "evidence_claim_ids TEXT NOT NULL DEFAULT '[]'",
            )
            self._add_column_if_missing(
                conn, "paper_ai_analyses", "confidence",
                "confidence REAL",
            )
            self._add_column_if_missing(
                conn, "subscriptions", "research_question_id",
                "research_question_id INTEGER",
            )
            # Phase 2: add entity_id and filters_json to subscriptions
            self._add_column_if_missing(
                conn, "subscriptions", "entity_id",
                "entity_id TEXT",
            )
            self._add_column_if_missing(
                conn, "subscriptions", "filters_json",
                "filters_json TEXT DEFAULT '{}'",
            )

            # Phase 2 migration: extend subscriptions CHECK constraint to include 'field' and 'entity'
            if current_version < 7:
                try:
                    conn.execute(
                        "INSERT INTO subscriptions(type, name, created_at, updated_at) "
                        "VALUES ('field', '__check_test__', datetime('now'), datetime('now'))"
                    )
                    conn.execute("DELETE FROM subscriptions WHERE name = '__check_test__'")
                    # Constraint already allows 'field' — just bump version
                except sqlite3.IntegrityError:
                    # Need to recreate table with new CHECK constraint
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
                            entity_id TEXT,
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

    def _migrate_arxiv_paper_ids(self, conn: sqlite3.Connection) -> None:
        queue_rows = conn.execute(
            "SELECT paper_id, status, source, note, tags_json, updated_at FROM reading_queue_items"
        ).fetchall()
        for row in queue_rows:
            old_id = row["paper_id"]
            new_id = _canonical_paper_id(old_id)
            if not new_id or new_id == old_id:
                continue
            existing = conn.execute(
                "SELECT paper_id, updated_at FROM reading_queue_items WHERE paper_id = ?",
                (new_id,),
            ).fetchone()
            if existing:
                if str(row["updated_at"] or "") >= str(existing["updated_at"] or ""):
                    conn.execute(
                        """
                        UPDATE reading_queue_items
                        SET status = ?, source = ?, note = ?, tags_json = ?, updated_at = ?
                        WHERE paper_id = ?
                        """,
                        (
                            row["status"],
                            row["source"],
                            row["note"],
                            row["tags_json"],
                            row["updated_at"],
                            new_id,
                        ),
                    )
                conn.execute("DELETE FROM reading_queue_items WHERE paper_id = ?", (old_id,))
            else:
                conn.execute(
                    "UPDATE reading_queue_items SET paper_id = ? WHERE paper_id = ?",
                    (new_id, old_id),
                )

        collection_rows = conn.execute(
            "SELECT collection_id, paper_id, note, added_at FROM collection_papers"
        ).fetchall()
        for row in collection_rows:
            old_id = row["paper_id"]
            new_id = _canonical_paper_id(old_id)
            if not new_id or new_id == old_id:
                continue
            conn.execute(
                """
                INSERT OR IGNORE INTO collection_papers(collection_id, paper_id, note, added_at)
                VALUES (?, ?, ?, ?)
                """,
                (row["collection_id"], new_id, row["note"], row["added_at"]),
            )
            conn.execute(
                "DELETE FROM collection_papers WHERE collection_id = ? AND paper_id = ?",
                (row["collection_id"], old_id),
            )

        event_rows = conn.execute(
            "SELECT id, paper_id FROM interaction_events WHERE paper_id LIKE '%v%'"
        ).fetchall()
        for row in event_rows:
            new_id = _canonical_paper_id(row["paper_id"])
            if new_id and new_id != row["paper_id"]:
                conn.execute(
                    "UPDATE interaction_events SET paper_id = ? WHERE id = ?",
                    (new_id, row["id"]),
                )

        analysis_rows = conn.execute(
            "SELECT paper_id, updated_at FROM paper_ai_analyses WHERE paper_id LIKE '%v%'"
        ).fetchall()
        for row in analysis_rows:
            old_id = row["paper_id"]
            new_id = _canonical_paper_id(old_id)
            if not new_id or new_id == old_id:
                continue
            existing = conn.execute(
                "SELECT paper_id, updated_at FROM paper_ai_analyses WHERE paper_id = ?",
                (new_id,),
            ).fetchone()
            if existing:
                if str(row["updated_at"] or "") >= str(existing["updated_at"] or ""):
                    conn.execute(
                        "DELETE FROM paper_ai_analyses WHERE paper_id = ?",
                        (new_id,),
                    )
                    conn.execute(
                        "UPDATE paper_ai_analyses SET paper_id = ? WHERE paper_id = ?",
                        (new_id, old_id),
                    )
                else:
                    conn.execute("DELETE FROM paper_ai_analyses WHERE paper_id = ?", (old_id,))
            else:
                conn.execute(
                    "UPDATE paper_ai_analyses SET paper_id = ? WHERE paper_id = ?",
                    (new_id, old_id),
                )

    def _auto_migrate_once(self) -> None:
        """Run data migrations on first start after schema upgrade (idempotent)."""
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM schema_meta WHERE key = 'schema_version'"
            ).fetchone()
            if not row or int(row["value"]) < 3:
                # Schema will be migrated by _initialize on next restart
                return
            migrated_marker = conn.execute(
                "SELECT value FROM schema_meta WHERE key = 'subscriptions_migrated'"
            ).fetchone()
            if migrated_marker and migrated_marker["value"] == "1":
                return

        # Run migrations outside the read lock to avoid deadlocks
        migrated_searches = self.migrate_from_saved_searches()
        migrated_scholars = self.migrate_from_scholars_json()

        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO schema_meta(key, value) VALUES('subscriptions_migrated', '1')"
            )

        if migrated_searches or migrated_scholars:
            import logging
            logging.getLogger(__name__).info(
                f"Auto-migrated subscriptions: {migrated_searches} searches, {migrated_scholars} scholars"
            )

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> Dict:
        data = dict(row)
        for key in (
            "payload_json", "result_json", "filters_json", "tags_json",
            "evidence_claim_ids", "aliases", "metadata_json",
            "stats_json", "external_ids", "interest_vector",
            "topic_weights", "entity_affinities", "reading_pace",
        ):
            if key in data:
                try:
                    data[key] = json.loads(data[key])
                except (TypeError, json.JSONDecodeError):
                    data[key] = [] if key in (
                        "evidence_claim_ids", "aliases", "interest_vector"
                    ) else {}
        return data

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


    def create_research_question(
        self,
        query_text: str,
        intent_statement: str = "",
        *,
        status: str = "active",
        source: str = "manual",
    ) -> Dict:
        query_text = str(query_text or "").strip()
        intent_statement = str(intent_statement or "").strip()
        if not query_text:
            raise ValueError("query_text is required")
        if status not in ("active", "paused", "archived"):
            raise ValueError(f"Invalid research question status: {status}")
        if source not in ("manual", "profile", "subscription"):
            raise ValueError(f"Invalid research question source: {source}")

        now = _utc_now()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO research_questions(
                    query_text, intent_statement, status, source, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (query_text, intent_statement, status, source, now, now),
            )
            row = conn.execute(
                "SELECT * FROM research_questions WHERE id = last_insert_rowid()"
            ).fetchone()
        return self._row_to_dict(row)

    def get_research_question(self, question_id: int) -> Optional[Dict]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM research_questions WHERE id = ?",
                (question_id,),
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def list_research_questions(
        self,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict]:
        query = "SELECT * FROM research_questions"
        params: List[object] = []
        if status:
            if status not in ("active", "paused", "archived"):
                raise ValueError(f"Invalid research question status: {status}")
            query += " WHERE status = ?"
            params.append(status)
        query += " ORDER BY updated_at DESC, id DESC LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def update_research_question(
        self,
        question_id: int,
        *,
        query_text: Optional[str] = None,
        intent_statement: Optional[str] = None,
        status: Optional[str] = None,
        source: Optional[str] = None,
    ) -> Optional[Dict]:
        updates = []
        params: List[object] = []

        if query_text is not None:
            query_text = str(query_text or "").strip()
            if not query_text:
                raise ValueError("query_text is required")
            updates.append("query_text = ?")
            params.append(query_text)
        if intent_statement is not None:
            updates.append("intent_statement = ?")
            params.append(str(intent_statement or "").strip())
        if status is not None:
            if status not in ("active", "paused", "archived"):
                raise ValueError(f"Invalid research question status: {status}")
            updates.append("status = ?")
            params.append(status)
        if source is not None:
            if source not in ("manual", "profile", "subscription"):
                raise ValueError(f"Invalid research question source: {source}")
            updates.append("source = ?")
            params.append(source)

        if not updates:
            return self.get_research_question(question_id)

        updates.append("updated_at = ?")
        params.append(_utc_now())
        params.append(question_id)

        with self._lock, self._connect() as conn:
            conn.execute(
                f"UPDATE research_questions SET {', '.join(updates)} WHERE id = ?",
                params,
            )
        return self.get_research_question(question_id)

    def seed_research_questions_from_keywords(self, keywords: Dict) -> int:
        created = 0
        for topic, config in (keywords or {}).items():
            if not isinstance(config, dict):
                continue
            category = config.get("category")
            weight = float(config.get("weight", 0) or 0)
            query_text = str(topic or "").strip()
            if not query_text or category not in ("core", "secondary") or weight <= 0:
                continue
            with self._connect() as conn:
                existing = conn.execute(
                    """
                    SELECT id FROM research_questions
                    WHERE lower(query_text) = lower(?) AND source = 'profile'
                    LIMIT 1
                    """,
                    (query_text,),
                ).fetchone()
            if existing:
                continue
            self.create_research_question(
                query_text=query_text,
                intent_statement=f"Track literature related to {query_text}.",
                source="profile",
            )
            created += 1
        return created

    # ------------------------------------------------------------------
    #  Evidence Claims
    # ------------------------------------------------------------------

    def create_evidence_claim(
        self,
        *,
        paper_id: str,
        claim: str,
        evidence_text: str = "",
        evidence_source: str = "abstract",
        claim_type: str = "factual",
        analyst: str = "rule",
        research_question_id: Optional[int] = None,
        claim_id: Optional[str] = None,
    ) -> Dict:
        paper_id = _canonical_paper_id(paper_id)
        claim = str(claim or "").strip()
        if not paper_id:
            raise ValueError("paper_id is required")
        if not claim:
            raise ValueError("claim is required")
        if evidence_source not in ("abstract", "metadata", "citation", "user_note", "other"):
            raise ValueError(f"Invalid evidence source: {evidence_source}")
        if claim_type not in ("factual", "interpretive", "caveat", "gap"):
            raise ValueError(f"Invalid claim type: {claim_type}")
        if analyst not in ("rule", "llm", "user"):
            raise ValueError(f"Invalid analyst: {analyst}")

        now = _utc_now()
        claim_id = claim_id or uuid.uuid4().hex
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO evidence_claims(
                    id, research_question_id, paper_id, claim, evidence_text,
                    evidence_source, claim_type, analyst, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    claim_id,
                    research_question_id,
                    paper_id,
                    claim,
                    str(evidence_text or "").strip(),
                    evidence_source,
                    claim_type,
                    analyst,
                    now,
                ),
            )
            row = conn.execute(
                "SELECT * FROM evidence_claims WHERE id = ?",
                (claim_id,),
            ).fetchone()
        return self._row_to_dict(row)

    def list_evidence_claims(
        self,
        *,
        paper_id: Optional[str] = None,
        research_question_id: Optional[int] = None,
        analyst: Optional[str] = None,
    ) -> List[Dict]:
        query = "SELECT * FROM evidence_claims WHERE 1 = 1"
        params: List[object] = []
        if paper_id:
            query += " AND paper_id = ?"
            params.append(_canonical_paper_id(paper_id))
        if research_question_id is not None:
            query += " AND research_question_id = ?"
            params.append(research_question_id)
        if analyst:
            query += " AND analyst = ?"
            params.append(analyst)
        query += " ORDER BY created_at ASC"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def delete_evidence_claims(
        self,
        *,
        paper_id: Optional[str] = None,
        research_question_id: Optional[int] = None,
    ) -> int:
        if not paper_id and research_question_id is None:
            raise ValueError("paper_id or research_question_id is required")
        query = "DELETE FROM evidence_claims WHERE 1 = 1"
        params: List[object] = []
        if paper_id:
            query += " AND paper_id = ?"
            params.append(_canonical_paper_id(paper_id))
        if research_question_id is not None:
            query += " AND research_question_id = ?"
            params.append(research_question_id)
        with self._lock, self._connect() as conn:
            result = conn.execute(query, params)
        return int(result.rowcount)

    def create_job(
        self,
        job_type: str,
        trigger_source: str = "unknown",
        payload: Optional[Dict] = None,
        status: str = "queued",
    ) -> Dict:
        if status not in JOB_STATUS_VALUES:
            raise ValueError(f"Invalid job status: {status}")

        now = _utc_now()
        run_id = uuid.uuid4().hex
        started_at = now if status == "running" else None

        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO job_runs(
                    run_id, job_type, status, trigger_source,
                    payload_json, result_json, created_at, updated_at, started_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    job_type,
                    status,
                    trigger_source,
                    _to_json(payload, {}),
                    _to_json({}, {}),
                    now,
                    now,
                    started_at,
                ),
            )
            row = conn.execute(
                "SELECT * FROM job_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
        return self._row_to_dict(row)

    def create_job_if_no_active_job(
        self,
        job_type: str,
        trigger_source: str = "unknown",
        payload: Optional[Dict] = None,
    ) -> Optional[Dict]:
        """Create a queued job only if no active (queued/running) job of this type exists.

        The check and insert run inside a single lock+transaction so two
        concurrent callers cannot both create jobs.
        Returns the new job dict, or None if an active job already exists.
        """
        now = _utc_now()
        run_id = uuid.uuid4().hex

        with self._lock, self._connect() as conn:
            existing = conn.execute(
                "SELECT run_id FROM job_runs WHERE job_type=? AND status IN ('queued','running') LIMIT 1",
                (job_type,),
            ).fetchone()
            if existing:
                return None

            conn.execute(
                """
                INSERT INTO job_runs(
                    run_id, job_type, status, trigger_source,
                    payload_json, result_json, created_at, updated_at
                ) VALUES (?, ?, 'queued', ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    job_type,
                    trigger_source,
                    _to_json(payload, {}),
                    _to_json({}, {}),
                    now,
                    now,
                ),
            )
            row = conn.execute(
                "SELECT * FROM job_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
        return self._row_to_dict(row)

    def update_job(
        self,
        run_id: str,
        status: str,
        *,
        result: Optional[Dict] = None,
        error_text: Optional[str] = None,
    ) -> Optional[Dict]:
        if status not in JOB_STATUS_VALUES:
            raise ValueError(f"Invalid job status: {status}")

        now = _utc_now()
        started_at = now if status == "running" else None
        finished_at = now if status in ("succeeded", "degraded", "failed") else None
        result_json = _to_json(result, {}) if result is not None else None

        with self._lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE job_runs
                SET status = ?,
                    result_json = COALESCE(?, result_json),
                    error_text = CASE WHEN ? IS NULL THEN error_text ELSE ? END,
                    updated_at = ?,
                    started_at = COALESCE(started_at, ?),
                    finished_at = CASE WHEN ? IS NULL THEN finished_at ELSE ? END
                WHERE run_id = ?
                """,
                (
                    status,
                    result_json,
                    error_text,
                    error_text,
                    now,
                    started_at,
                    finished_at,
                    finished_at,
                    run_id,
                ),
            )
            row = conn.execute(
                "SELECT * FROM job_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def get_job(self, run_id: str) -> Optional[Dict]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM job_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def get_latest_job(self, job_type: Optional[str] = None) -> Optional[Dict]:
        query = "SELECT * FROM job_runs"
        params: List[object] = []
        if job_type:
            query += " WHERE job_type = ?"
            params.append(job_type)
        query += " ORDER BY created_at DESC LIMIT 1"
        with self._connect() as conn:
            row = conn.execute(query, params).fetchone()
        return self._row_to_dict(row) if row else None

    def has_running_job(self, job_type: str) -> bool:
        """Return True if there is at least one queued or running job of the given type."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM job_runs WHERE job_type=? AND status IN ('queued', 'running') LIMIT 1",
                (job_type,),
            ).fetchone()
        return row is not None

    def recover_stale_jobs(self, stale_after_minutes: int = 120) -> int:
        """Mark jobs stuck in 'queued'/'running' for too long as 'failed'.

        Returns the number of recovered jobs. This is called on startup to
        unblock future pipeline runs that were interrupted by a crash.
        """
        now = _utc_now()
        with self._lock, self._connect() as conn:
            # Find stale jobs: queued/running and updated_at older than threshold
            rows = conn.execute(
                """SELECT run_id FROM job_runs
                   WHERE status IN ('queued', 'running')
                     AND updated_at < datetime('now', ?)""",
                (f"-{stale_after_minutes} minutes",),
            ).fetchall()
            if not rows:
                return 0
            run_ids = [row["run_id"] for row in rows]
            for run_id in run_ids:
                conn.execute(
                    """UPDATE job_runs
                       SET status = 'failed',
                           error_text = 'Recovered: stale job on startup',
                           updated_at = ?,
                           finished_at = ?
                       WHERE run_id = ?""",
                    (now, now, run_id),
                )
        return len(run_ids)

    def list_collections(self) -> List[Dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT rc.*,
                       COUNT(cp.paper_id) AS paper_count
                FROM research_collections rc
                LEFT JOIN collection_papers cp ON cp.collection_id = rc.id
                GROUP BY rc.id
                ORDER BY rc.updated_at DESC
                """
            ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def get_collection(self, collection_id: int) -> Optional[Dict]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT rc.*,
                       COUNT(cp.paper_id) AS paper_count
                FROM research_collections rc
                LEFT JOIN collection_papers cp ON cp.collection_id = rc.id
                WHERE rc.id = ?
                GROUP BY rc.id
                """,
                (collection_id,),
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def create_collection(
        self, name: str, description: str = "", query_text: str = ""
    ) -> Dict:
        now = _utc_now()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO research_collections(
                    name, description, query_text, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (name.strip(), description.strip(), query_text.strip(), now, now),
            )
            row = conn.execute(
                """
                SELECT rc.*, 0 AS paper_count
                FROM research_collections rc
                WHERE rc.name = ?
                """,
                (name.strip(),),
            ).fetchone()
        return self._row_to_dict(row)

    def delete_collection(self, collection_id: int) -> bool:
        with self._lock, self._connect() as conn:
            conn.execute(
                "DELETE FROM collection_papers WHERE collection_id = ?",
                (collection_id,),
            )
            result = conn.execute(
                "DELETE FROM research_collections WHERE id = ?",
                (collection_id,),
            )
        return result.rowcount > 0

    def update_collection(
        self,
        collection_id: int,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        query_text: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> Optional[Dict]:
        updates = []
        params: List[object] = []

        if name is not None:
            updates.append("name = ?")
            params.append(name.strip())
        if description is not None:
            updates.append("description = ?")
            params.append(description.strip())
        if query_text is not None:
            updates.append("query_text = ?")
            params.append(query_text.strip())
        if is_active is not None:
            updates.append("is_active = ?")
            params.append(1 if is_active else 0)

        if not updates:
            return self.get_collection(collection_id)

        updates.append("updated_at = ?")
        params.append(_utc_now())
        params.append(collection_id)

        with self._lock, self._connect() as conn:
            conn.execute(
                f"""
                UPDATE research_collections
                SET {", ".join(updates)}
                WHERE id = ?
                """,
                params,
            )
        return self.get_collection(collection_id)

    def add_paper_to_collection(
        self, collection_id: int, paper_id: str, note: str = ""
    ) -> bool:
        paper_id = _canonical_paper_id(paper_id)
        now = _utc_now()
        with self._lock, self._connect() as conn:
            parent = conn.execute(
                "SELECT id FROM research_collections WHERE id = ?",
                (collection_id,),
            ).fetchone()
            if parent is None:
                return False
            conn.execute(
                """
                INSERT OR REPLACE INTO collection_papers(
                    collection_id, paper_id, note, added_at
                ) VALUES (?, ?, ?, ?)
                """,
                (collection_id, paper_id, note, now),
            )
            conn.execute(
                "UPDATE research_collections SET updated_at = ? WHERE id = ?",
                (now, collection_id),
            )
        return True

    def list_collection_papers(self, collection_id: int) -> List[Dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT collection_id, paper_id, note, added_at
                FROM collection_papers
                WHERE collection_id = ?
                ORDER BY added_at DESC
                """,
                (collection_id,),
            ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def remove_paper_from_collection(self, collection_id: int, paper_id: str) -> bool:
        paper_id = _canonical_paper_id(paper_id)
        now = _utc_now()
        with self._lock, self._connect() as conn:
            result = conn.execute(
                """
                DELETE FROM collection_papers
                WHERE collection_id = ? AND paper_id = ?
                """,
                (collection_id, paper_id),
            )
            if result.rowcount > 0:
                conn.execute(
                    "UPDATE research_collections SET updated_at = ? WHERE id = ?",
                    (now, collection_id),
                )
        return result.rowcount > 0

    def list_saved_searches(self) -> List[Dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM saved_searches ORDER BY updated_at DESC"
            ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def get_saved_search(self, search_id: int) -> Optional[Dict]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM saved_searches WHERE id = ?",
                (search_id,),
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def create_saved_search(
        self, name: str, query_text: str, filters: Optional[Dict] = None
    ) -> Dict:
        now = _utc_now()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO saved_searches(
                    name, query_text, filters_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (name.strip(), query_text.strip(), _to_json(filters, {}), now, now),
            )
            row = conn.execute(
                "SELECT * FROM saved_searches WHERE name = ?",
                (name.strip(),),
            ).fetchone()
        return self._row_to_dict(row)

    def delete_saved_search(self, search_id: int) -> bool:
        with self._lock, self._connect() as conn:
            result = conn.execute(
                "DELETE FROM saved_searches WHERE id = ?",
                (search_id,),
            )
        return result.rowcount > 0

    def update_saved_search(
        self,
        search_id: int,
        *,
        name: Optional[str] = None,
        query_text: Optional[str] = None,
        filters: Optional[Dict] = None,
        is_active: Optional[bool] = None,
    ) -> Optional[Dict]:
        updates = []
        params: List[object] = []

        if name is not None:
            updates.append("name = ?")
            params.append(name.strip())
        if query_text is not None:
            updates.append("query_text = ?")
            params.append(query_text.strip())
        if filters is not None:
            updates.append("filters_json = ?")
            params.append(_to_json(filters, {}))
        if is_active is not None:
            updates.append("is_active = ?")
            params.append(1 if is_active else 0)

        if not updates:
            return self.get_saved_search(search_id)

        updates.append("updated_at = ?")
        params.append(_utc_now())
        params.append(search_id)

        with self._lock, self._connect() as conn:
            conn.execute(
                f"""
                UPDATE saved_searches
                SET {", ".join(updates)}
                WHERE id = ?
                """,
                params,
            )
        return self.get_saved_search(search_id)

    # ------------------------------------------------------------------
    # Unified Subscriptions
    # ------------------------------------------------------------------

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
            if self.get_entity(entity_id) is None:
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
                    (query_text or "").strip(),
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

    def update_subscription(self, subscription_id: int, **kwargs) -> Optional[Dict]:
        updates = []
        params: List[object] = []

        direct_fields = {"type", "name", "query_text", "enabled", "latest_hit_count", "last_checked_at"}
        for field in direct_fields:
            value = kwargs.get(field)
            if value is not None:
                if field == "enabled":
                    updates.append("enabled = ?")
                    params.append(1 if value else 0)
                else:
                    updates.append(f"{field} = ?")
                    params.append(str(value).strip() if field in ("name", "query_text") else value)

        if "payload_json" in kwargs:
            updates.append("payload_json = ?")
            payload = kwargs["payload_json"]
            params.append(payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False))

        if "research_question_id" in kwargs:
            value = kwargs["research_question_id"]
            if value in (None, ""):
                updates.append("research_question_id = ?")
                params.append(None)
            else:
                question_id = int(value)
                if self.get_research_question(question_id) is None:
                    raise ValueError(f"Unknown research question: {question_id}")
                updates.append("research_question_id = ?")
                params.append(question_id)

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

        if not updates:
            return self.get_subscription(subscription_id)

        updates.append("updated_at = ?")
        params.append(_utc_now())
        params.append(subscription_id)

        with self._lock, self._connect() as conn:
            conn.execute(
                f"""
                UPDATE subscriptions
                SET {", ".join(updates)}
                WHERE id = ?
                """,
                params,
            )
        return self.get_subscription(subscription_id)

    def delete_subscription(self, subscription_id: int) -> bool:
        with self._lock, self._connect() as conn:
            result = conn.execute(
                "DELETE FROM subscriptions WHERE id = ?",
                (subscription_id,),
            )
        return result.rowcount > 0

    def get_subscription(self, subscription_id: int) -> Optional[Dict]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM subscriptions WHERE id = ?",
                (subscription_id,),
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def list_subscriptions(self, type: Optional[str] = None) -> List[Dict]:
        query = "SELECT * FROM subscriptions"
        params: List[object] = []
        if type:
            query += " WHERE type = ?"
            params.append(type)
        query += " ORDER BY updated_at DESC"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_dict(row) for row in rows]

    # ------------------------------------------------------------------
    # Subscription Hits
    # ------------------------------------------------------------------

    def upsert_subscription_hit(
        self,
        subscription_id: int,
        paper_id: str,
        matched_reason: str = "",
        hit_date: Optional[str] = None,
        status: str = "new",
    ) -> Dict:
        paper_id = _canonical_paper_id(paper_id)
        if status not in ("new", "sent_to_inbox", "queued", "ignored"):
            raise ValueError(f"Invalid hit status: {status}")
        hit_date = hit_date or _utc_now()
        now = _utc_now()
        with self._lock, self._connect() as conn:
            existing = conn.execute(
                """
                SELECT id FROM subscription_hits
                WHERE subscription_id = ? AND paper_id = ?
                """,
                (subscription_id, paper_id),
            ).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE subscription_hits
                    SET matched_reason = ?, status = ?, created_at = ?
                    WHERE id = ?
                    """,
                    (matched_reason, status, now, existing["id"]),
                )
                row = conn.execute(
                    "SELECT * FROM subscription_hits WHERE id = ?",
                    (existing["id"],),
                ).fetchone()
            else:
                conn.execute(
                    """
                    INSERT INTO subscription_hits(
                        subscription_id, paper_id, matched_reason, hit_date, status, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (subscription_id, paper_id, matched_reason, hit_date, status, now),
                )
                row = conn.execute(
                    "SELECT * FROM subscription_hits WHERE id = last_insert_rowid()"
                ).fetchone()
            conn.execute(
                """
                UPDATE subscriptions
                SET latest_hit_count = (
                    SELECT COUNT(*) FROM subscription_hits WHERE subscription_id = ?
                ),
                updated_at = ?
                WHERE id = ?
                """,
                (subscription_id, now, subscription_id),
            )
        return self._row_to_dict(row)

    def list_subscription_hits(
        self,
        subscription_id: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict]:
        query = "SELECT * FROM subscription_hits WHERE 1 = 1"
        params: List[object] = []
        if subscription_id is not None:
            query += " AND subscription_id = ?"
            params.append(subscription_id)
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY hit_date DESC LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_dict(row) for row in rows]


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

    # ------------------------------------------------------------------
    # Migration
    # ------------------------------------------------------------------

    def migrate_from_saved_searches(self) -> int:
        """Migrate existing saved_searches rows to the subscriptions table (type='query')."""
        migrated = 0
        now = _utc_now()
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT id, name, query_text, filters_json, is_active, created_at, updated_at FROM saved_searches"
            ).fetchall()
            for row in rows:
                existing = conn.execute(
                    "SELECT id FROM subscriptions WHERE type = 'query' AND name = ?",
                    (row["name"],),
                ).fetchone()
                if existing:
                    continue
                payload = json.dumps({
                    "filters": (json.loads(row["filters_json"]) if row["filters_json"] else {}),
                    "legacy_id": row["id"],
                }, ensure_ascii=False)
                conn.execute(
                    """
                    INSERT INTO subscriptions(
                        type, name, query_text, payload_json, enabled,
                        created_at, updated_at
                    ) VALUES ('query', ?, ?, ?, ?, ?, ?)
                    """,
                    (row["name"], row["query_text"], payload, row["is_active"],
                     row["created_at"] or now, row["updated_at"] or now),
                )
                migrated += 1
        return migrated

    def migrate_from_scholars_json(self) -> int:
        """Migrate my_scholars.json entries to the subscriptions table (type='author')."""
        import os
        try:
            scholars_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "my_scholars.json",
            )
            if not os.path.exists(scholars_path):
                return 0
            with open(scholars_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return 0

        scholars = data.get("scholars", []) if isinstance(data, dict) else []

        migrated = 0
        now = _utc_now()
        with self._lock, self._connect() as conn:
            for scholar in scholars:
                name = scholar.get("name", "").strip()
                if not name:
                    continue
                existing = conn.execute(
                    "SELECT id FROM subscriptions WHERE type = 'author' AND name = ?",
                    (name,),
                ).fetchone()
                if existing:
                    continue
                payload = {
                    "affiliation": scholar.get("affiliation", ""),
                    "focus": scholar.get("focus", ""),
                    "email": scholar.get("email", ""),
                    "google_scholar": scholar.get("google_scholar", ""),
                    "website": scholar.get("website", ""),
                }
                query_text = scholar.get("arxiv", "")
                conn.execute(
                    """
                    INSERT INTO subscriptions(
                        type, name, query_text, payload_json, enabled,
                        created_at, updated_at
                    ) VALUES ('author', ?, ?, ?, 1, ?, ?)
                    """,
                    (name, query_text, json.dumps(payload, ensure_ascii=False), now, now),
                )
                migrated += 1
        return migrated

    def upsert_queue_item(
        self,
        paper_id: str,
        status: str,
        *,
        source: str = "",
        note: str = "",
        tags: Optional[List[str]] = None,
        research_question_id: Optional[int] = None,
        decision_context: str = "",
    ) -> Dict:
        paper_id = _canonical_paper_id(paper_id)
        if status not in QUEUE_STATUS_VALUES:
            raise ValueError(f"Invalid queue status: {status}")
        now = _utc_now()
        with self._lock, self._connect() as conn:
            # Merge versioned duplicates: delete rows whose canonicalized
            # paper_id matches the target but have a different string form
            # (e.g. "2604.12345v1" vs canonical "2604.12345").
            existing = conn.execute(
                "SELECT paper_id FROM reading_queue_items"
            ).fetchall()
            for row in existing:
                eid = row["paper_id"]
                if eid != paper_id and _canonical_paper_id(eid) == paper_id:
                    conn.execute(
                        "DELETE FROM reading_queue_items WHERE paper_id = ?",
                        (eid,),
                    )

            conn.execute(
                """
                INSERT INTO reading_queue_items(
                    paper_id, status, source, note, tags_json, updated_at,
                    research_question_id, decision_context
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(paper_id) DO UPDATE SET
                    status = excluded.status,
                    source = excluded.source,
                    note = excluded.note,
                    tags_json = excluded.tags_json,
                    updated_at = excluded.updated_at,
                    research_question_id = excluded.research_question_id,
                    decision_context = excluded.decision_context
                """,
                (
                    paper_id,
                    status,
                    source,
                    note,
                    _to_json(tags, []),
                    now,
                    research_question_id,
                    str(decision_context or "").strip(),
                ),
            )
            row = conn.execute(
                "SELECT * FROM reading_queue_items WHERE paper_id = ?",
                (paper_id,),
            ).fetchone()
        return self._row_to_dict(row)

    def list_queue_items(self, status: Optional[str] = None) -> List[Dict]:
        query = "SELECT * FROM reading_queue_items"
        params: List[object] = []
        if status:
            query += " WHERE status = ?"
            params.append(status)
        query += " ORDER BY updated_at DESC"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def get_queue_item(self, paper_id: str) -> Optional[Dict]:
        paper_id = _canonical_paper_id(paper_id)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM reading_queue_items WHERE paper_id = ?",
                (paper_id,),
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def get_inbox_progress(self, date_str: str) -> Dict:
        """Return triage progress stats for a given date.

        Returns counts for: handled, untriaged, liked, disliked, skimmed,
        deep_read, queued.  ``total`` is set to handled so the caller can
        override it when the page knows how many papers were shown.
        """
        start_utc, end_utc = _utc_bounds_for_local_date(date_str)
        with self._lock, self._connect() as conn:
            handled_row = conn.execute(
                """
                SELECT COUNT(DISTINCT paper_id) AS cnt
                FROM interaction_events
                WHERE created_at >= ? AND created_at < ? AND paper_id != ''
                """,
                (start_utc, end_utc),
            ).fetchone()
            handled = handled_row["cnt"] if handled_row else 0

            event_rows = conn.execute(
                """
                SELECT event_type, COUNT(*) AS cnt
                FROM interaction_events
                WHERE created_at >= ? AND created_at < ? AND paper_id != ''
                GROUP BY event_type
                """,
                (start_utc, end_utc),
            ).fetchall()

            queue_rows = conn.execute(
                """
                SELECT status, COUNT(*) AS cnt
                FROM reading_queue_items
                WHERE updated_at >= ? AND updated_at < ?
                GROUP BY status
                """,
                (start_utc, end_utc),
            ).fetchall()

        event_counts: Dict[str, int] = {row["event_type"]: row["cnt"] for row in event_rows}
        queue_counts: Dict[str, int] = {row["status"]: row["cnt"] for row in queue_rows}

        liked = event_counts.get("like", 0)
        disliked = event_counts.get("dislike", 0)
        skimmed = queue_counts.get("Skim Later", 0)
        deep_read = queue_counts.get("Deep Read", 0)
        queued = sum(queue_counts.values())

        return {
            "total": handled,
            "handled": handled,
            "untriaged": 0,
            "liked": liked,
            "disliked": disliked,
            "skimmed": skimmed,
            "deep_read": deep_read,
            "queued": queued,
        }

    def list_interaction_events(
        self, paper_id: Optional[str] = None, limit: int = 100
    ) -> List[Dict]:
        """List interaction events, optionally filtered by paper_id."""
        with self._connect() as conn:
            if paper_id:
                pid = _canonical_paper_id(paper_id)
                rows = conn.execute(
                    "SELECT * FROM interaction_events WHERE paper_id = ? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (pid, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM interaction_events ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def record_event(
        self, event_type: str, paper_id: str = "", payload: Optional[Dict] = None
    ) -> int:
        paper_id = _canonical_paper_id(paper_id)
        now = _utc_now()
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO interaction_events(event_type, paper_id, payload_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (event_type, paper_id, _to_json(payload, {}), now),
            )
            event_id = int(cursor.lastrowid)

        # Best-effort topic affinity update after event recording
        try:
            if paper_id:
                categories = self._get_paper_categories(paper_id)
                if categories:
                    # Determine effective event type for queue_status_changed
                    eff_type = event_type
                    if event_type == "queue_status_changed" and payload:
                        status = payload.get("status", "")
                        if status == "Deep Read":
                            eff_type = "deep_read"
                        elif status == "Skim Later":
                            eff_type = "skim_later"

                    # Ignore events: skip negative affinity if paper was also liked
                    skip_affinity = False
                    if eff_type in ("ignore", "ignore_topic"):
                        with self._connect() as conn_inner:
                            also_liked = conn_inner.execute(
                                "SELECT 1 FROM interaction_events WHERE paper_id = ? AND event_type = 'like' LIMIT 1",
                                (paper_id,),
                            ).fetchone()
                            if also_liked:
                                skip_affinity = True

                    if not skip_affinity:
                        self.update_affinity_from_event(eff_type, categories, [])
        except Exception:
            logger.exception("Failed to update topic affinity from event")

        return event_id

    # ------------------------------------------------------------------
    # Paper categories lookup helper
    # ------------------------------------------------------------------

    def _get_paper_categories(self, paper_id: str) -> List[str]:
        """Look up paper categories from recommendation_items."""
        try:
            from utils import CATEGORY_NAMES  # noqa: F811
        except Exception:
            CATEGORY_NAMES = {}
        paper_id = _canonical_paper_id(paper_id)
        with self._connect() as conn:
            row = conn.execute(
                """SELECT categories_json FROM recommendation_items
                   WHERE paper_id = ? LIMIT 1""",
                (paper_id,),
            ).fetchone()
            if row and row["categories_json"]:
                try:
                    return json.loads(row["categories_json"])
                except (TypeError, json.JSONDecodeError):
                    pass
        return []

    # ------------------------------------------------------------------
    # User Topic Affinity
    # ------------------------------------------------------------------

    def get_user_topic_affinities(self) -> List[Dict]:
        """Return all topic affinities ordered by positive_score DESC."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM user_topic_affinity ORDER BY positive_score DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def upsert_user_topic_affinity(
        self, topic: str, positive_score: float, negative_score: float
    ) -> bool:
        """Upsert a topic affinity score with exact values."""
        try:
            with self._lock, self._connect() as conn:
                conn.execute(
                    """INSERT OR REPLACE INTO user_topic_affinity(
                           topic, positive_score, negative_score,
                           source_event_count, updated_at)
                       VALUES (?, ?, ?,
                           COALESCE(
                               (SELECT source_event_count FROM user_topic_affinity WHERE topic = ?) + 1,
                               1
                           ),
                           datetime('now'))""",
                    (topic, positive_score, negative_score, topic),
                )
            return True
        except Exception:
            logger.exception("Failed to upsert topic affinity")
            return False

    def update_affinity_from_event(
        self,
        event_type: str,
        paper_categories: List[str],
        paper_keywords: List[str],
    ) -> bool:
        """Update topic affinity based on user interaction event."""
        positive_delta = 0.0
        negative_delta = 0.0

        if event_type in ("like", "Relevant"):
            positive_delta = 1.0
        elif event_type == "deep_read":
            positive_delta = 2.0
        elif event_type == "skim_later":
            positive_delta = 1.5
        elif event_type in ("dislike",):
            negative_delta = 1.0
        elif event_type in ("save", "save_for_later"):
            positive_delta = 2.5
        elif event_type in ("ignore", "ignore_topic"):
            negative_delta = 1.0
        else:
            return False

        if positive_delta == 0.0 and negative_delta == 0.0:
            return False

        # Map categories to topic names
        try:
            from utils import CATEGORY_NAMES  # noqa: F811
        except Exception:
            CATEGORY_NAMES = {}
        topics: List[str] = []
        for cat in paper_categories:
            topics.append(CATEGORY_NAMES.get(cat, cat))
        for kw in paper_keywords:
            topics.append(kw)

        if not topics:
            return False

        with self._lock, self._connect() as conn:
            for topic in topics:
                conn.execute(
                    """INSERT INTO user_topic_affinity(
                           topic, positive_score, negative_score,
                           source_event_count, updated_at)
                       VALUES (?, ?, ?, 1, datetime('now'))
                       ON CONFLICT(topic) DO UPDATE SET
                           positive_score = positive_score + ?,
                           negative_score = negative_score + ?,
                           source_event_count = source_event_count + 1,
                           updated_at = datetime('now')""",
                    (topic, positive_delta, negative_delta,
                     positive_delta, negative_delta),
                )
        return True

    # ------------------------------------------------------------------
    # Recommendation Runs
    # ------------------------------------------------------------------

    def save_recommendation_run(
        self,
        run_date: str,
        trigger_source: str = "auto_homepage",
        papers: Optional[List[Dict]] = None,
        themes: Optional[List[str]] = None,
    ) -> str:
        """Save a recommendation run and its items to SQLite. Returns run_id."""
        import uuid
        now = _utc_now()
        run_id = uuid.uuid4().hex
        papers = papers or []
        themes_json = json.dumps(themes or [], ensure_ascii=False)

        with self._lock, self._connect() as conn:
            conn.execute(
                """INSERT INTO recommendation_runs(run_id, run_date, trigger_source, themes_json, status, paper_count, created_at, finished_at)
                   VALUES (?, ?, ?, ?, 'completed', ?, ?, ?)""",
                (run_id, run_date, trigger_source, themes_json, len(papers), now, now),
            )
            for rank, paper in enumerate(papers, start=1):
                paper_id = paper.get("id") or paper.get("paper_id", "")
                conn.execute(
                    """INSERT OR IGNORE INTO recommendation_items(run_id, paper_id, rank, score, score_details_json, source_strategy, relevance_reason, title, authors_json, abstract, categories_json, source)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        run_id,
                        paper_id,
                        rank,
                        float(paper.get("score", 0) or 0),
                        json.dumps(paper.get("score_details", {}), ensure_ascii=False),
                        paper.get("source_strategy", "for_you"),
                        paper.get("relevance_reason", ""),
                        paper.get("title", ""),
                        json.dumps(paper.get("authors", []), ensure_ascii=False),
                        paper.get("abstract", ""),
                        json.dumps(paper.get("categories", []), ensure_ascii=False),
                        paper.get("source", "arxiv"),
                    ),
                )
        return run_id

    def get_recommendation_items(self, run_id: str) -> List[Dict]:
        """Get all recommendation items for a run."""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM recommendation_items WHERE run_id = ? ORDER BY rank",
                (run_id,),
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            for key in ("score_details_json", "authors_json", "categories_json"):
                try:
                    item[key.replace("_json", "")] = json.loads(item[key])
                except (TypeError, json.JSONDecodeError):
                    item[key.replace("_json", "")] = {}
            result.append(item)
        return result

    def list_recommendation_runs(self, limit: int = 10) -> List[Dict]:
        """List recent recommendation runs."""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM recommendation_runs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_recommendation_run_by_date(self, date: str, trigger_source: Optional[str] = None) -> Optional[Dict]:
        """Get the latest recommendation run for a specific date."""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            if trigger_source:
                row = conn.execute(
                    "SELECT * FROM recommendation_runs WHERE run_date = ? AND trigger_source = ? ORDER BY created_at DESC LIMIT 1",
                    (date, trigger_source),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM recommendation_runs WHERE run_date = ? ORDER BY created_at DESC LIMIT 1",
                    (date,),
                ).fetchone()
        return dict(row) if row else None

    def list_recommendation_dates(self, limit: int = 30, trigger_source: Optional[str] = None) -> List[str]:
        """List dates that have recommendation runs, newest first."""
        with self._connect() as conn:
            if trigger_source:
                rows = conn.execute(
                    "SELECT DISTINCT run_date FROM recommendation_runs WHERE trigger_source = ? ORDER BY run_date DESC LIMIT ?",
                    (trigger_source, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT DISTINCT run_date FROM recommendation_runs ORDER BY run_date DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [row[0] for row in rows]

    def get_paper_ai_analysis(self, paper_id: str) -> Optional[Dict]:
        paper_id = _canonical_paper_id(paper_id)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM paper_ai_analyses WHERE paper_id = ?",
                (paper_id,),
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def upsert_paper_ai_analysis(
        self,
        paper_id: str,
        analysis: Dict,
        *,
        model_name: str,
        prompt_version: str,
        status: str = "ok",
        error_text: str = "",
        evidence_claim_ids: Optional[List[str]] = None,
        confidence: Optional[float] = None,
    ) -> Dict:
        paper_id = _canonical_paper_id(paper_id)
        if not paper_id:
            raise ValueError("Missing paper_id")
        now = _utc_now()
        values = {
            "one_sentence_summary": "",
            "problem": "",
            "method": "",
            "contribution": "",
            "limitations": "",
            "why_it_matters": "",
            "recommended_reading_level": "skim",
        }
        values.update({key: analysis.get(key, values[key]) or values[key] for key in values})
        evidence_claim_ids_json = _to_json(evidence_claim_ids, [])
        with self._lock, self._connect() as conn:
            existing = conn.execute(
                "SELECT created_at FROM paper_ai_analyses WHERE paper_id = ?",
                (paper_id,),
            ).fetchone()
            created_at = existing["created_at"] if existing else now
            conn.execute(
                """
                INSERT INTO paper_ai_analyses(
                    paper_id, one_sentence_summary, problem, method, contribution,
                    limitations, why_it_matters, recommended_reading_level,
                    model_name, prompt_version, status, error_text, created_at, updated_at,
                    evidence_claim_ids, confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(paper_id) DO UPDATE SET
                    one_sentence_summary = excluded.one_sentence_summary,
                    problem = excluded.problem,
                    method = excluded.method,
                    contribution = excluded.contribution,
                    limitations = excluded.limitations,
                    why_it_matters = excluded.why_it_matters,
                    recommended_reading_level = excluded.recommended_reading_level,
                    model_name = excluded.model_name,
                    prompt_version = excluded.prompt_version,
                    status = excluded.status,
                    error_text = excluded.error_text,
                    updated_at = excluded.updated_at,
                    evidence_claim_ids = excluded.evidence_claim_ids,
                    confidence = excluded.confidence
                """,
                (
                    paper_id,
                    values["one_sentence_summary"],
                    values["problem"],
                    values["method"],
                    values["contribution"],
                    values["limitations"],
                    values["why_it_matters"],
                    values["recommended_reading_level"],
                    model_name,
                    prompt_version,
                    status,
                    error_text,
                    created_at,
                    now,
                    evidence_claim_ids_json,
                    confidence,
                ),
            )
            row = conn.execute(
                "SELECT * FROM paper_ai_analyses WHERE paper_id = ?",
                (paper_id,),
            ).fetchone()
        return self._row_to_dict(row)

    # ------------------------------------------------------------------
    # Paper Embeddings
    # ------------------------------------------------------------------

    def save_paper_embedding(self, paper_id: str, embedding_bytes: bytes, model_name: str) -> None:
        """Save a paper embedding to the paper_embeddings table."""
        paper_id = _canonical_paper_id(paper_id)
        now = _utc_now()
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO paper_embeddings(paper_id, embedding, model_name, created_at) VALUES (?, ?, ?, ?)",
                (paper_id, embedding_bytes, model_name, now),
            )

    def get_paper_embedding(self, paper_id: str):
        """Get a paper embedding. Returns (embedding_blob, model_name, created_at) or None."""
        paper_id = _canonical_paper_id(paper_id)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT embedding, model_name, created_at FROM paper_embeddings WHERE paper_id = ?",
                (paper_id,),
            ).fetchone()
        if row:
            return (row["embedding"], row["model_name"], row["created_at"])
        return None

    # ------------------------------------------------------------------
    # Paper Metadata Cache
    # ------------------------------------------------------------------

    def save_paper_metadata(
        self,
        paper_id: str,
        metadata: dict,
        *,
        source: str = "",
        source_run_id: str = "",
        first_seen_at: Optional[str] = None,
        workspace_status: str = "active",
    ) -> None:
        """Cache paper metadata (title, abstract, authors, etc.) in the metadata table."""
        paper_id = _canonical_paper_id(paper_id)
        now = _utc_now()
        metadata_json = json.dumps(metadata)
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO paper_metadata(
                    paper_id, metadata_json, created_at,
                    source, source_run_id, first_seen_at, workspace_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(paper_id) DO UPDATE SET
                    metadata_json = excluded.metadata_json,
                    source = excluded.source,
                    source_run_id = excluded.source_run_id,
                    first_seen_at = CASE
                        WHEN paper_metadata.first_seen_at = '' THEN excluded.first_seen_at
                        ELSE paper_metadata.first_seen_at
                    END,
                    workspace_status = excluded.workspace_status
                """,
                (
                    paper_id,
                    metadata_json,
                    now,
                    str(source or ""),
                    str(source_run_id or ""),
                    first_seen_at or now,
                    workspace_status,
                ),
            )

    def get_paper_metadata(self, paper_id: str) -> Optional[dict]:
        """Retrieve cached paper metadata, or None if not found."""
        paper_id = _canonical_paper_id(paper_id)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT metadata_json, created_at FROM paper_metadata WHERE paper_id = ?",
                (paper_id,),
            ).fetchone()
        if row:
            return json.loads(row["metadata_json"])
        return None

    def get_all_embeddings_for_model(self, model_name: str):
        """Get all embeddings for a given model. Returns list of (paper_id, embedding_blob, created_at)."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT paper_id, embedding, created_at FROM paper_embeddings WHERE model_name = ?",
                (model_name,),
            ).fetchall()
        return [(row["paper_id"], row["embedding"], row["created_at"]) for row in rows]

    # ------------------------------------------------------------------
    # Feedback Models
    # ------------------------------------------------------------------

    def save_feedback_model(self, sample_count: int, auc: float, model_json: str) -> int:
        """Save a trained feedback model as JSON. Returns the new row id."""
        now = _utc_now()
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                """INSERT INTO feedback_models(trained_at, sample_count, auc, pickle_blob)
                   VALUES (?, ?, ?, ?)""",
                (now, sample_count, auc, model_json),
            )
            return int(cursor.lastrowid)

    def get_latest_feedback_model(self) -> Optional[Dict]:
        """Return the most recently saved feedback model row, or None."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM feedback_models ORDER BY id DESC LIMIT 1"
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def get_feedback_model_auc(self) -> Optional[float]:
        """Return the AUC of the most recent feedback model, or None."""
        row = self.get_latest_feedback_model()
        if row:
            return float(row["auc"])
        return None

    # ------------------------------------------------------------------
    # Generic schema_meta key-value store
    # ------------------------------------------------------------------

    def get(self, key: str) -> Optional[str]:
        """Get a string value from the schema_meta table by key. Returns None if not found."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM schema_meta WHERE key = ?", (key,)
            ).fetchone()
        return row["value"] if row else None

    def save(self, key: str, value: str) -> None:
        """Save a string value into the schema_meta table (upsert by key)."""
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO schema_meta(key, value) VALUES(?, ?)",
                (key, value),
            )

    def export_state(self) -> Dict[str, List[Dict]]:
        tables = [
            "job_runs",
            "research_collections",
            "collection_papers",
            "saved_searches",
            "reading_queue_items",
            "interaction_events",
            "user_topic_affinity",
            "paper_ai_analyses",
            "subscriptions",
            "subscription_hits",
            "paper_embeddings",
            "paper_metadata",
            "feedback_models",
        ]
        snapshot: Dict[str, List[Dict]] = {}
        with self._connect() as conn:
            for table in tables:
                rows = conn.execute(f"SELECT * FROM {table}").fetchall()
                snapshot[table] = [self._row_to_dict(row) for row in rows]
        return snapshot

    _MAX_IMPORT_ROWS_PER_TABLE = 10_000

    def import_state(self, snapshot: Dict[str, List[Dict]]) -> None:
        if not isinstance(snapshot, dict):
            raise ValueError("Invalid state snapshot")
        if not snapshot:
            raise ValueError("Empty state snapshot")

        table_columns = {
            "job_runs": [
                "run_id", "job_type", "status", "trigger_source", "payload_json",
                "result_json", "error_text", "created_at", "updated_at", "started_at",
                "finished_at",
            ],
            "research_collections": [
                "id", "name", "description", "query_text", "is_active", "created_at",
                "updated_at",
            ],
            "collection_papers": ["collection_id", "paper_id", "note", "added_at"],
            "saved_searches": [
                "id", "name", "query_text", "filters_json", "is_active", "created_at",
                "updated_at",
            ],
            "reading_queue_items": [
                "paper_id", "status", "source", "note", "tags_json", "updated_at",
            ],
            "interaction_events": ["id", "event_type", "paper_id", "payload_json", "created_at"],
            "user_topic_affinity": ["topic", "positive_score", "negative_score", "source_event_count", "updated_at"],
            "paper_ai_analyses": [
                "paper_id", "one_sentence_summary", "problem", "method",
                "contribution", "limitations", "why_it_matters",
                "recommended_reading_level", "model_name", "prompt_version",
                "status", "error_text", "created_at", "updated_at",
            ],
            "subscriptions": [
                "id", "type", "name", "query_text", "payload_json", "enabled",
                "latest_hit_count", "last_checked_at", "created_at", "updated_at",
            ],
            "subscription_hits": [
                "id", "subscription_id", "paper_id", "matched_reason",
                "hit_date", "status", "created_at",
            ],
            "paper_embeddings": [
                "paper_id", "embedding", "model_name", "created_at",
            ],
            "paper_metadata": [
                "paper_id", "metadata_json", "created_at",
            ],
            "feedback_models": [
                "id", "trained_at", "sample_count", "auc", "pickle_blob",
            ],
        }

        with self._lock, self._connect() as conn:
            conn.execute("PRAGMA foreign_keys = OFF")
            for table in reversed(list(table_columns.keys())):
                conn.execute(f"DELETE FROM {table}")

            for table, columns in table_columns.items():
                rows = snapshot.get(table, [])
                if not isinstance(rows, list):
                    raise ValueError(f"Invalid rows for {table}")
                if len(rows) > self._MAX_IMPORT_ROWS_PER_TABLE:
                    raise ValueError(
                        f"Too many rows for {table}: {len(rows)} "
                        f"(max {self._MAX_IMPORT_ROWS_PER_TABLE})"
                    )
                if table not in table_columns:
                    raise ValueError(f"Unknown table: {table}")
                placeholders = ", ".join(["?"] * len(columns))
                column_sql = ", ".join(columns)
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    values = [row.get(column) for column in columns]
                    if "paper_id" in columns:
                        paper_idx = columns.index("paper_id")
                        values[paper_idx] = _canonical_paper_id(values[paper_idx])
                    for idx, column in enumerate(columns):
                        if column.endswith("_json") and not isinstance(values[idx], str):
                            values[idx] = _to_json(values[idx], [] if column == "tags_json" else {})
                    conn.execute(
                        f"INSERT OR REPLACE INTO {table}({column_sql}) VALUES ({placeholders})",
                        values,
                    )

            conn.execute("PRAGMA foreign_keys = ON")
            self._migrate_arxiv_paper_ids(conn)

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
        """List sessions, pinned first then by last_active descending."""
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
        """Update mutable fields of an agent session."""
        updates: List[str] = []
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
        """Delete a session and cascade-delete its messages."""
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

        Raises ValueError for invalid role or nonexistent session.
        """
        if role not in ("user", "assistant", "system", "tool"):
            raise ValueError(f"Invalid message role: {role}")

        now = _utc_now()
        with self._lock, self._connect() as conn:
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
        """Get messages for a session, ordered by creation time ascending."""
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

    # ------------------------------------------------------------------
    # Agent Pending Confirmations
    # ------------------------------------------------------------------

    def create_agent_pending_confirmation(
        self,
        session_id: str,
        message: str,
        plan_json: str,
        page_context_json: str,
        *,
        ttl_minutes: int = 15,
    ) -> Dict:
        """Create a pending confirmation record for a destructive action."""
        token = uuid.uuid4().hex
        now = _utc_now()
        expires = datetime.now(tz=timezone.utc) + timedelta(minutes=ttl_minutes)
        expires_at = expires.replace(microsecond=0).isoformat() + "Z"
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO agent_pending_confirmations(
                    token, session_id, message, plan_json, page_context_json,
                    created_at, expires_at, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
                """,
                (token, session_id, message, plan_json, page_context_json, now, expires_at),
            )
        return {
            "token": token,
            "session_id": session_id,
            "message": message,
            "expires_at": expires_at,
        }

    def get_agent_pending_confirmation(self, token: str) -> Optional[Dict]:
        """Get a pending confirmation by token."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM agent_pending_confirmations WHERE token = ?",
                (token,),
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def consume_agent_pending_confirmation(self, token: str) -> bool:
        """Mark a pending confirmation as consumed. Returns True if successful."""
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM agent_pending_confirmations WHERE token = ? AND status = 'pending'",
                (token,),
            ).fetchone()
            if not row:
                return False
            conn.execute(
                "UPDATE agent_pending_confirmations SET status = 'consumed' WHERE token = ?",
                (token,),
            )
        return True

    def clean_expired_agent_confirmations(self) -> int:
        """Mark expired pending confirmations as expired. Returns count cleaned."""
        now = _utc_now()
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "UPDATE agent_pending_confirmations SET status = 'expired' "
                "WHERE status = 'pending' AND expires_at < ?",
                (now,),
            )
            return rows.rowcount

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
                ORDER BY sh.created_at DESC, sh.id DESC
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
        """Return high-frequency search queries as suggestions."""
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

    # ------------------------------------------------------------------
    # User Profile
    # ------------------------------------------------------------------

    def get_user_profile(self) -> Dict:
        """Get the singleton user profile, creating it if it doesn't exist."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM user_profile WHERE id = 1"
            ).fetchone()
        if not row:
            # Create default profile
            self.upsert_user_profile()
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT * FROM user_profile WHERE id = 1"
                ).fetchone()
        profile = self._row_to_dict(row) if row else {}
        # Parse JSON fields
        for key in ("interest_vector", "topic_weights", "entity_affinities", "reading_pace"):
            raw = profile.get(key, "")
            if isinstance(raw, str):
                try:
                    profile[key] = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    profile[key] = [] if key == "interest_vector" else {}
        return profile

    def upsert_user_profile(
        self,
        interest_vector: Optional[List[str]] = None,
        topic_weights: Optional[Dict] = None,
        entity_affinities: Optional[Dict] = None,
        reading_pace: Optional[Dict] = None,
    ) -> None:
        """Create or update the singleton user profile.

        Only provided fields are updated; None fields are left unchanged.
        """
        now = _utc_now()
        with self._lock, self._connect() as conn:
            existing = conn.execute(
                "SELECT * FROM user_profile WHERE id = 1"
            ).fetchone()

            if existing:
                existing = self._row_to_dict(existing)
                updates = {}
                if interest_vector is not None:
                    updates["interest_vector"] = json.dumps(interest_vector, ensure_ascii=False)
                if topic_weights is not None:
                    updates["topic_weights"] = json.dumps(topic_weights, ensure_ascii=False)
                if entity_affinities is not None:
                    updates["entity_affinities"] = json.dumps(entity_affinities, ensure_ascii=False)
                if reading_pace is not None:
                    updates["reading_pace"] = json.dumps(reading_pace, ensure_ascii=False)
                if updates:
                    updates["updated_at"] = now
                    set_clause = ", ".join(f"{k} = ?" for k in updates)
                    conn.execute(
                        f"UPDATE user_profile SET {set_clause} WHERE id = 1",
                        list(updates.values()),
                    )
            else:
                conn.execute(
                    """INSERT INTO user_profile(id, interest_vector, topic_weights, entity_affinities, reading_pace, updated_at)
                       VALUES (1, ?, ?, ?, ?, ?)""",
                    (
                        json.dumps(interest_vector or [], ensure_ascii=False),
                        json.dumps(topic_weights or {}, ensure_ascii=False),
                        json.dumps(entity_affinities or {}, ensure_ascii=False),
                        json.dumps(reading_pace or {}, ensure_ascii=False),
                        now,
                    ),
                )

    def update_profile_from_behavior(self) -> None:
        """Auto-update user profile from reading behavior, subscriptions, and search history."""
        # 1. Collect topics from reading queue papers
        queue_items = self.list_queue_items()
        topic_counts: Dict[str, float] = {}

        for item in queue_items:
            paper_id = item.get("paper_id", "")
            meta = self.get_paper_metadata(paper_id) or {}
            categories = meta.get("categories", [])
            if isinstance(categories, str):
                try:
                    categories = json.loads(categories)
                except (json.JSONDecodeError, TypeError):
                    categories = []

            # Weight by reading depth
            weight = 2.0 if item.get("status") == "Deep Read" else 1.0
            for cat in categories:
                topic_counts[cat] = topic_counts.get(cat, 0) + weight

            # Extract title keywords (simple approach)
            title = meta.get("title") or item.get("title") or ""
            for word in title.lower().split():
                if len(word) >= 5:  # Skip short words
                    topic_counts[word] = topic_counts.get(word, 0) + weight * 0.3

        # 2. Add subscription query texts
        try:
            subs = self.list_subscriptions()
            for sub in subs:
                query = sub.get("query_text", "")
                if query:
                    for word in query.lower().split():
                        if len(word) >= 4:
                            topic_counts[word] = topic_counts.get(word, 0) + 1.5
        except Exception:
            pass

        # 3. Build interest vector from top topics
        sorted_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)
        interest_vector = [t[0] for t in sorted_topics[:30]]
        topic_weights = {t[0]: round(t[1], 2) for t in sorted_topics[:30]}

        self.upsert_user_profile(
            interest_vector=interest_vector,
            topic_weights=topic_weights,
        )

_state_store: Optional[StateStore] = None


def get_state_store() -> StateStore:
    global _state_store
    if _state_store is None:
        _state_store = StateStore()
    return _state_store

