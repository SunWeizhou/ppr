"""Subscription execution service -- run subscriptions, persist hits, manage lifecycle."""
from __future__ import annotations
import json
from datetime import datetime
from typing import Dict, List, Optional
from logger_config import get_logger

logger = get_logger(__name__)


class SubscriptionService:
    def __init__(self, state_store):
        self._store = state_store

    def run_subscription(self, subscription_id: int) -> Dict:
        """Run a single subscription: search for new hits, persist them."""
        sub = self._store.get_subscription(subscription_id)
        if not sub:
            return {"success": False, "error": "Subscription not found"}

        sub_type = sub["type"]
        query_text = sub.get("query_text") or sub.get("name", "")

        papers = self._search_by_type(sub_type, query_text)

        now = datetime.now().strftime("%Y-%m-%d")
        hit_count = 0
        for paper in papers:
            from state_store import _canonical_paper_id
            paper_id = _canonical_paper_id(
                paper.get("id") or paper.get("paper_id") or ""
            )
            if not paper_id:
                continue
            self._store.upsert_subscription_hit(
                subscription_id, paper_id,
                matched_reason=sub_type,
                hit_date=now,
                status="new",
            )
            hit_count += 1

        self._store.update_subscription(
            subscription_id,
            latest_hit_count=hit_count,
            last_checked_at=now,
        )

        logger.info(f"Subscription {subscription_id} ({sub_type}): {hit_count} hits")
        return {"success": True, "hit_count": hit_count, "subscription": sub}

    def run_all_subscriptions(self) -> Dict:
        """Run all enabled subscriptions."""
        subs = self._store.list_subscriptions()
        enabled = [s for s in subs if s.get("enabled", True)]

        total_hits = 0
        results = []
        for sub in enabled:
            try:
                result = self.run_subscription(sub["id"])
                if result["success"]:
                    total_hits += result["hit_count"]
                    results.append({
                        "id": sub["id"],
                        "name": sub.get("name", ""),
                        "type": sub["type"],
                        "hit_count": result["hit_count"],
                    })
            except Exception as e:
                logger.warning(f"Subscription {sub['id']} failed: {e}")

        return {
            "success": True,
            "total_hits": total_hits,
            "subscriptions_run": len(results),
            "results": results,
        }

    def _search_by_type(self, sub_type: str, query_text: str) -> List[Dict]:
        """Search for papers matching the subscription type."""
        from app.services.arxiv_source import search_by_keywords

        if sub_type == "query":
            keywords = [k.strip() for k in query_text.replace(",", " ").split() if k.strip()]
            if not keywords:
                return []
            return search_by_keywords(keywords, max_results=10, days_back=90)
        elif sub_type == "author":
            # Simple author search via keywords
            keywords = [f'au:{query_text}']
            try:
                return search_by_keywords(keywords, max_results=10, days_back=90)
            except Exception as e:
                logger.warning(f"Author search failed for {query_text}: {e}")
                return []
        elif sub_type == "venue":
            keywords = [query_text]
            return search_by_keywords(keywords, max_results=10, days_back=90)
        return []

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
