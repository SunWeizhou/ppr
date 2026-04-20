"""SQLite-backed state store for durable app state.

This module externalizes mutable state from the Flask routes so the app can
grow in small, auditable slices instead of scattering more JSON files.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime
from typing import Dict, Iterable, List, Optional

from app_paths import STATE_DB_PATH, ensure_runtime_dirs

JOB_STATUS_VALUES = ("queued", "running", "succeeded", "degraded", "failed")
QUEUE_STATUS_VALUES = ("Inbox", "Skim Later", "Deep Read", "Saved", "Archived")


def _utc_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _to_json(value: Optional[object], default: object) -> str:
    return json.dumps(value if value is not None else default, ensure_ascii=False)


class StateStore:
    """Thin service layer around a local SQLite database."""

    def __init__(self, db_path: str = str(STATE_DB_PATH)):
        ensure_runtime_dirs()
        self.db_path = db_path
        self._lock = threading.Lock()
        self._initialize()

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
                    PRIMARY KEY (collection_id, paper_id)
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
                """
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO schema_meta(key, value)
                VALUES('schema_version', '1')
                """
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
        now = _utc_now()
        with self._lock, self._connect() as conn:
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

    def upsert_queue_item(
        self,
        paper_id: str,
        status: str,
        *,
        source: str = "",
        note: str = "",
        tags: Optional[List[str]] = None,
    ) -> Dict:
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
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM reading_queue_items WHERE paper_id = ?",
                (paper_id,),
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def record_event(
        self, event_type: str, paper_id: str = "", payload: Optional[Dict] = None
    ) -> int:
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


_state_store: Optional[StateStore] = None


def get_state_store() -> StateStore:
    global _state_store
    if _state_store is None:
        _state_store = StateStore()
    return _state_store
