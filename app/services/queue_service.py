"""Queue service facade over the local SQLite state store."""

from __future__ import annotations

from typing import Optional

from state_store import QUEUE_STATUS_VALUES, _canonical_paper_id


class QueueService:
    """Coordinate reading-queue mutations without tying callers to Flask."""

    def __init__(self, state_store):
        self.state_store = state_store

    def list_items(self, status: Optional[str] = None):
        if status and status not in QUEUE_STATUS_VALUES:
            raise ValueError(f"Invalid queue status: {status}")
        return self.state_store.list_queue_items(status=status)

    def update_item(self, paper_id: str, status: str, *, source: str = "queue_service", note=None, tags=None):
        canonical_id = _canonical_paper_id(paper_id)
        if not canonical_id:
            raise ValueError("Missing paper_id")
        if status not in QUEUE_STATUS_VALUES:
            raise ValueError(f"Invalid queue status: {status}")

        existing = self.state_store.get_queue_item(canonical_id)
        if note is None and existing:
            note = existing.get("note", "")
        if tags is None and existing:
            tags = existing.get("tags_json")
        return self.state_store.upsert_queue_item(
            canonical_id,
            status,
            source=source,
            note=note or "",
            tags=tags,
        )

    def bulk_update(self, paper_ids, status: str, *, source: str = "queue_service", note: str = ""):
        return [
            self.update_item(paper_id, status, source=source, note=note)
            for paper_id in paper_ids
        ]

