#!/usr/bin/env python3
"""Remove obvious test fixture records from the local runtime SQLite state."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


PLACEHOLDER_TITLES = {
    "Affinity Test",
    "Browser Smoke Paper",
    "Collection Test",
    "JSON Fields Paper",
    "Module Test Paper",
    "P1",
    "Stable " + "identity",
    "Test",
    "Test Paper",
    "Test Paper " + "Title",
    "Verification",
    "Verify",
    "Workspace Flow Paper",
}

PLACEHOLDER_SUBSCRIPTIONS = {
    "Hit Test",
    "Hits List",
    "Query A",
    "Query Test",
    "Test",
    "Test Query",
}

TEST_SOURCES = {
    "api_test",
    "browser-smoke",
    "bulk_test",
    "queue_api",
    "test",
}


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
        (table,),
    ).fetchone() is not None


def _metadata_title(metadata_json: str) -> str:
    try:
        payload = json.loads(metadata_json or "{}")
    except json.JSONDecodeError:
        return ""
    return str(payload.get("title") or "")


def cleanup(db_path: Path, *, apply: bool) -> dict[str, int]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    counts: dict[str, int] = {}

    try:
        if _table_exists(conn, "subscriptions"):
            sub_ids = [
                row["id"]
                for row in conn.execute("SELECT id, name, query_text FROM subscriptions")
                if str(row["name"] or "") in PLACEHOLDER_SUBSCRIPTIONS
                or str(row["query_text"] or "") in {"test", "ml"}
            ]
            counts["subscriptions"] = len(sub_ids)
            if apply and sub_ids:
                placeholders = ",".join("?" for _ in sub_ids)
                if _table_exists(conn, "subscription_hits"):
                    conn.execute(
                        f"DELETE FROM subscription_hits WHERE subscription_id IN ({placeholders})",
                        sub_ids,
                    )
                conn.execute(f"DELETE FROM subscriptions WHERE id IN ({placeholders})", sub_ids)

        if _table_exists(conn, "paper_metadata"):
            paper_ids = [
                row["paper_id"]
                for row in conn.execute("SELECT paper_id, metadata_json, source FROM paper_metadata")
                if _metadata_title(row["metadata_json"]) in PLACEHOLDER_TITLES
                or str(row["source"] or "") in TEST_SOURCES
            ]
            counts["paper_metadata"] = len(paper_ids)
            if apply and paper_ids:
                placeholders = ",".join("?" for _ in paper_ids)
                conn.execute(f"DELETE FROM paper_metadata WHERE paper_id IN ({placeholders})", paper_ids)
                if _table_exists(conn, "reading_queue_items"):
                    conn.execute(
                        f"DELETE FROM reading_queue_items WHERE paper_id IN ({placeholders})",
                        paper_ids,
                    )

        if _table_exists(conn, "recommendation_items"):
            rec_ids = [
                row["id"]
                for row in conn.execute("SELECT id, title FROM recommendation_items")
                if str(row["title"] or "") in PLACEHOLDER_TITLES
            ]
            counts["recommendation_items"] = len(rec_ids)
            if apply and rec_ids:
                placeholders = ",".join("?" for _ in rec_ids)
                conn.execute(f"DELETE FROM recommendation_items WHERE id IN ({placeholders})", rec_ids)

        if _table_exists(conn, "reading_queue_items"):
            queue_ids = [
                row["paper_id"]
                for row in conn.execute("SELECT paper_id, source FROM reading_queue_items")
                if str(row["source"] or "") in TEST_SOURCES
            ]
            counts["reading_queue_items"] = counts.get("reading_queue_items", 0) + len(queue_ids)
            if apply and queue_ids:
                placeholders = ",".join("?" for _ in queue_ids)
                conn.execute(f"DELETE FROM reading_queue_items WHERE paper_id IN ({placeholders})", queue_ids)

        if apply:
            conn.commit()
        else:
            conn.rollback()
    finally:
        conn.close()
    return counts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="cache/app_state.db")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        raise SystemExit(f"Runtime database not found: {db_path}")

    counts = cleanup(db_path, apply=args.apply)
    mode = "deleted" if args.apply else "would delete"
    for table, count in sorted(counts.items()):
        print(f"{table}: {mode} {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
