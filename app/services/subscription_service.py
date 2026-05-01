"""Subscription CRUD helper — list hits, manage hit lifecycle."""
from __future__ import annotations

from typing import Dict, List

from logger_config import get_logger

logger = get_logger(__name__)


class SubscriptionService:
    """CRUD helpers for subscription hits (send_to_inbox, ignore, list).

    Execution logic lives in SubscriptionRunner.
    """

    def __init__(self, state_store):
        self._store = state_store

    def recent_hits(self, limit: int = 50) -> list[dict]:
        """Get recent hits with subscription metadata."""
        hits = self._store.list_subscription_hits(limit=limit)
        result = []
        for hit in hits:
            sub = self._store.get_subscription(hit.get("subscription_id", 0))
            if sub:
                hit["subscription_name"] = sub.get("name", "")
                hit["subscription_type"] = sub.get("type", "")
            result.append(hit)
        return result

    def send_hit_to_inbox(self, hit_id: int) -> bool:
        """Mark a hit as sent to inbox and add to queue."""
        hits = self._store.list_subscription_hits(limit=1000)
        target = None
        for h in hits:
            if h.get("id") == hit_id:
                target = h
                break
        if not target:
            return False

        from state_store import _canonical_paper_id
        paper_id = _canonical_paper_id(target.get("paper_id", ""))
        sub_id = target.get("subscription_id", 0)

        self._store.upsert_subscription_hit(
            sub_id, paper_id,
            matched_reason=target.get("matched_reason", ""),
            hit_date=target.get("hit_date", ""),
            status="sent_to_inbox",
        )

        self._store.upsert_queue_item(
            paper_id=paper_id,
            status="Inbox",
            source=f"subscription:{sub_id}",
            note=target.get("matched_reason", ""),
        )
        return True

    def ignore_hit(self, hit_id: int) -> bool:
        """Mark a hit as ignored."""
        hits = self._store.list_subscription_hits(limit=1000)
        target = None
        for h in hits:
            if h.get("id") == hit_id:
                target = h
                break
        if not target:
            return False

        from state_store import _canonical_paper_id
        paper_id = _canonical_paper_id(target.get("paper_id", ""))
        sub_id = target.get("subscription_id", 0)

        self._store.upsert_subscription_hit(
            sub_id, paper_id,
            matched_reason=target.get("matched_reason", ""),
            hit_date=target.get("hit_date", ""),
            status="ignored",
        )
        return True
