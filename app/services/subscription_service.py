"""Subscription CRUD helper — list hits, manage hit lifecycle."""
from __future__ import annotations
from typing import Dict, List
from logger_config import get_logger

logger = get_logger(__name__)


class SubscriptionService:
    """CRUD helpers for subscription hits (send_to_inbox, ignore, list).

    Execution logic lives in SubscriptionRunner.
    """

    def __init__(self, state_store, *, queue_service=None):
        self._store = state_store
        self._queue = queue_service

    def recent_hits(self, limit: int = 50) -> List[Dict]:
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

        from app.data._constants import canonical_paper_id as _canonical_paper_id
        paper_id = _canonical_paper_id(target.get("paper_id", ""))
        sub_id = target.get("subscription_id", 0)

        self._store.upsert_subscription_hit(
            sub_id, paper_id,
            matched_reason=target.get("matched_reason", ""),
            hit_date=target.get("hit_date", ""),
            status="sent_to_inbox",
        )

        sub = self._store.get_subscription(sub_id) if sub_id else None
        matched_reason = target.get("matched_reason", "")
        subscription_name = (sub or {}).get("name", "")
        research_question_id = (sub or {}).get("research_question_id")
        decision_context_parts = []
        if subscription_name:
            decision_context_parts.append(f"Watch subscription: {subscription_name}")
        if matched_reason:
            decision_context_parts.append(f"Match: {matched_reason}")
        decision_context = " | ".join(decision_context_parts)

        if self._queue is not None:
            self._queue.add_to_reading(
                paper_id=paper_id,
                source=f"subscription:{sub_id}",
                note=matched_reason,
                research_question_id=research_question_id,
                decision_context=decision_context,
            )
        else:
            self._store.upsert_queue_item(
                paper_id=paper_id,
                status="Inbox",
                source=f"subscription:{sub_id}",
                note=matched_reason,
                research_question_id=research_question_id,
                decision_context=decision_context,
            )
            self._store.record_event(
                "reading_added", paper_id,
                {"research_question_id": research_question_id, "source": f"subscription:{sub_id}"},
            )
            self._store.record_event(
                "queue_status_changed", paper_id,
                {"status": "Inbox", "source": f"subscription:{sub_id}", "research_question_id": research_question_id},
            )
            if research_question_id is not None:
                self._store.upsert_workspace_paper(
                    paper_id, research_question_id, "reading",
                    reason="subscription hit sent to inbox",
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

        from app.data._constants import canonical_paper_id as _canonical_paper_id
        paper_id = _canonical_paper_id(target.get("paper_id", ""))
        sub_id = target.get("subscription_id", 0)

        self._store.upsert_subscription_hit(
            sub_id, paper_id,
            matched_reason=target.get("matched_reason", ""),
            hit_date=target.get("hit_date", ""),
            status="ignored",
        )
        return True
