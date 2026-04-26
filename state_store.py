"""SQLite-backed state store for durable app state.

This module externalizes mutable state from the Flask routes so the app can
grow in small, auditable slices instead of scattering more JSON files.
"""

from __future__ import annotations

import json
import re
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional

from app_paths import STATE_DB_PATH, ensure_runtime_dirs

JOB_STATUS_VALUES = ("queued", "running", "succeeded", "degraded", "failed")
QUEUE_STATUS_VALUES = ("Inbox", "Skim Later", "Deep Read", "Saved", "Archived")


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat() + "Z"


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

    @contextmanager
    def _connect(self) -> Iterable[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
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
                """
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO schema_meta(key, value)
                VALUES('schema_version', '2')
                """
            )
            self._migrate_arxiv_paper_ids(conn)

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
            if not row or row["value"] != "2":
                # Only auto-migrate when schema version is v2
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
        for key in ("payload_json", "result_json", "filters_json", "tags_json"):
            if key in data:
                try:
                    data[key] = json.loads(data[key])
                except (TypeError, json.JSONDecodeError):
                    data[key] = {}
        return data

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
    ) -> Dict:
        if type not in ("query", "author", "venue"):
            raise ValueError(f"Invalid subscription type: {type}")
        if isinstance(payload_json, dict):
            payload_json = json.dumps(payload_json, ensure_ascii=False)
        now = _utc_now()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO subscriptions(
                    type, name, query_text, payload_json, enabled,
                    latest_hit_count, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 0, ?, ?)
                """,
                (type, name.strip(), query_text.strip(), payload_json, 1 if enabled else 0, now, now),
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
    ) -> Dict:
        paper_id = _canonical_paper_id(paper_id)
        if status not in QUEUE_STATUS_VALUES:
            raise ValueError(f"Invalid queue status: {status}")
        now = _utc_now()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO reading_queue_items(
                    paper_id, status, source, note, tags_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(paper_id) DO UPDATE SET
                    status = excluded.status,
                    source = excluded.source,
                    note = excluded.note,
                    tags_json = excluded.tags_json,
                    updated_at = excluded.updated_at
                """,
                (
                    paper_id,
                    status,
                    source,
                    note,
                    _to_json(tags, []),
                    now,
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
        with self._lock, self._connect() as conn:
            # _utc_now() produces timestamps like "2026-04-26T10:15:37+00:00Z".
            # SQLite DATE() cannot parse the +00:00Z suffix, so we use
            # substr(..., 1, 10) to extract the YYYY-MM-DD prefix.
            handled_row = conn.execute(
                """
                SELECT COUNT(DISTINCT paper_id) AS cnt
                FROM interaction_events
                WHERE substr(created_at, 1, 10) = ? AND paper_id != ''
                """,
                (date_str,),
            ).fetchone()
            handled = handled_row["cnt"] if handled_row else 0

            event_rows = conn.execute(
                """
                SELECT event_type, COUNT(*) AS cnt
                FROM interaction_events
                WHERE substr(created_at, 1, 10) = ? AND paper_id != ''
                GROUP BY event_type
                """,
                (date_str,),
            ).fetchall()

            queue_rows = conn.execute(
                """
                SELECT status, COUNT(*) AS cnt
                FROM reading_queue_items
                WHERE substr(updated_at, 1, 10) = ?
                GROUP BY status
                """,
                (date_str,),
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
            return int(cursor.lastrowid)

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
                    model_name, prompt_version, status, error_text, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    updated_at = excluded.updated_at
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
                ),
            )
            row = conn.execute(
                "SELECT * FROM paper_ai_analyses WHERE paper_id = ?",
                (paper_id,),
            ).fetchone()
        return self._row_to_dict(row)

    def export_state(self) -> Dict[str, List[Dict]]:
        tables = [
            "job_runs",
            "research_collections",
            "collection_papers",
            "saved_searches",
            "reading_queue_items",
            "interaction_events",
            "paper_ai_analyses",
            "subscriptions",
            "subscription_hits",
        ]
        snapshot: Dict[str, List[Dict]] = {}
        with self._connect() as conn:
            for table in tables:
                rows = conn.execute(f"SELECT * FROM {table}").fetchall()
                snapshot[table] = [self._row_to_dict(row) for row in rows]
        return snapshot

    def import_state(self, snapshot: Dict[str, List[Dict]]) -> None:
        if not isinstance(snapshot, dict):
            raise ValueError("Invalid state snapshot")

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
        }

        with self._lock, self._connect() as conn:
            conn.execute("PRAGMA foreign_keys = OFF")
            for table in reversed(list(table_columns.keys())):
                conn.execute(f"DELETE FROM {table}")

            for table, columns in table_columns.items():
                rows = snapshot.get(table, [])
                if not isinstance(rows, list):
                    raise ValueError(f"Invalid rows for {table}")
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


_state_store: Optional[StateStore] = None


def get_state_store() -> StateStore:
    global _state_store
    if _state_store is None:
        _state_store = StateStore()
    return _state_store
