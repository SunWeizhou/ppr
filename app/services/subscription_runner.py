"""Cleaner execution layer for subscription lifecycle.

SubscriptionRunner wraps SubscriptionService with type-specific search
methods, standalone deduplication, and explicit hit persistence.  The
type-specific runners (run_query_subscription, run_author_subscription,
run_venue_subscription) each search local recommendation data as well as
the arXiv API, then dedupe and persist new hits.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from logger_config import get_logger
from app.services.subscription_service import SubscriptionService
from state_store import _canonical_paper_id

logger = get_logger(__name__)


class SubscriptionRunner:
    """High-level subscription runner used by CLI, scheduler, and API routes."""

    def __init__(self, state_store):
        self._store = state_store
        self._svc = SubscriptionService(state_store)

    # ------------------------------------------------------------------
    # Top-level delegation
    # ------------------------------------------------------------------

    def run_subscription(self, subscription_id: int) -> dict:
        """Run a single subscription by ID.

        Delegates to ``SubscriptionService.run_subscription``.  Returns a
        dict with *hit_count*, *success*, and *error* keys.
        """
        try:
            result = self._svc.run_subscription(subscription_id)
            return {
                "success": result.get("success", False),
                "hit_count": result.get("hit_count", 0),
                "subscription": result.get("subscription"),
                "error": result.get("error"),
            }
        except Exception as e:
            logger.error(f"Error running subscription {subscription_id}: {e}")
            return {"success": False, "hit_count": 0, "error": str(e)}

    def run_all_subscriptions(self) -> dict:
        """Run all enabled subscriptions and return a summary.

        Returns a dict with *total_run*, *total_hits*, and *errors* list.
        """
        try:
            result = self._svc.run_all_subscriptions()
            return {
                "success": result.get("success", False),
                "total_run": result.get("subscriptions_run", 0),
                "total_hits": result.get("total_hits", 0),
                "errors": [],
                "results": result.get("results", []),
            }
        except Exception as e:
            logger.error(f"Error running all subscriptions: {e}")
            return {
                "success": False,
                "total_run": 0,
                "total_hits": 0,
                "errors": [str(e)],
            }

    # ------------------------------------------------------------------
    # Type-specific runners
    # ------------------------------------------------------------------

    def run_query_subscription(self, sub: dict) -> int:
        """Run a single query-type subscription.

        Searches the arXiv API for papers matching the subscription's query
        text and also checks cached recommendation items for keyword matches
        in titles.  Returns the number of *new* hits persisted.
        """
        from app.services.arxiv_source import search_by_keywords

        query_text = sub.get("query_text") or sub.get("name", "")
        keywords = [
            k.strip()
            for k in query_text.replace(",", " ").split()
            if k.strip()
        ]
        if not keywords:
            return 0

        paper_ids: List[str] = []

        # 1. Check cached recommendation_items for matching titles
        try:
            runs = self._store.list_recommendation_runs(limit=10)
            for run in runs:
                items = self._store.get_recommendation_items(run["run_id"])
                for item in items:
                    title = (item.get("title") or "").lower()
                    abstract = (item.get("abstract") or "").lower()
                    for kw in keywords:
                        if kw.lower() in title or kw.lower() in abstract:
                            pid = _canonical_paper_id(
                                item.get("paper_id") or ""
                            )
                            if pid and pid not in paper_ids:
                                paper_ids.append(pid)
                            break
        except Exception as e:
            logger.debug(f"Query local lookup failed: {e}")

        # 2. Search arXiv API
        try:
            papers = search_by_keywords(keywords, max_results=10, days_back=90)
            for p in papers:
                pid = _canonical_paper_id(
                    p.get("id") or p.get("paper_id") or ""
                )
                if pid and pid not in paper_ids:
                    paper_ids.append(pid)
        except Exception as e:
            logger.warning(f"Query arXiv search failed for '{query_text}': {e}")

        return self.persist_hits(sub["id"], paper_ids, "query")

    def run_author_subscription(self, sub: dict) -> int:
        """Run a single author-type subscription.

        Checks cached recommendation items for papers by the target author
        and also searches the arXiv API via the ``au:`` prefix.  Returns the
        number of *new* hits persisted.
        """
        from app.services.arxiv_source import search_by_keywords

        author_name = sub.get("query_text") or sub.get("name", "")
        if not author_name:
            return 0

        paper_ids: List[str] = []

        # 1. Check cached recommendation_items for papers by this author
        try:
            runs = self._store.list_recommendation_runs(limit=10)
            for run in runs:
                items = self._store.get_recommendation_items(run["run_id"])
                for item in items:
                    authors = item.get("authors", [])
                    if isinstance(authors, list):
                        for a in authors:
                            if author_name.lower() in a.lower():
                                pid = _canonical_paper_id(
                                    item.get("paper_id") or ""
                                )
                                if pid and pid not in paper_ids:
                                    paper_ids.append(pid)
                                break
        except Exception as e:
            logger.debug(f"Author local lookup failed: {e}")

        # 2. Search arXiv API via author prefix
        try:
            papers = search_by_keywords(
                [f'au:{author_name}'], max_results=10, days_back=90
            )
            for p in papers:
                pid = _canonical_paper_id(
                    p.get("id") or p.get("paper_id") or ""
                )
                if pid and pid not in paper_ids:
                    paper_ids.append(pid)
        except Exception as e:
            logger.warning(
                f"Author arXiv search failed for '{author_name}': {e}"
            )

        return self.persist_hits(sub["id"], paper_ids, "author")

    def run_venue_subscription(self, sub: dict) -> int:
        """Run a single venue-type subscription.

        Checks cached recommendation items for papers whose categories match
        the venue string and also searches the arXiv API.  Returns the
        number of *new* hits persisted.
        """
        from app.services.arxiv_source import search_by_keywords

        venue = sub.get("query_text") or sub.get("name", "")
        if not venue:
            return 0

        paper_ids: List[str] = []

        # 1. Check recommendation_items for papers matching venue/category
        try:
            runs = self._store.list_recommendation_runs(limit=10)
            for run in runs:
                items = self._store.get_recommendation_items(run["run_id"])
                for item in items:
                    categories = item.get("categories", [])
                    if isinstance(categories, list):
                        for cat in categories:
                            if venue.lower() in cat.lower():
                                pid = _canonical_paper_id(
                                    item.get("paper_id") or ""
                                )
                                if pid and pid not in paper_ids:
                                    paper_ids.append(pid)
                                break
        except Exception as e:
            logger.debug(f"Venue local lookup failed: {e}")

        # 2. Search arXiv API
        try:
            papers = search_by_keywords([venue], max_results=10, days_back=90)
            for p in papers:
                pid = _canonical_paper_id(
                    p.get("id") or p.get("paper_id") or ""
                )
                if pid and pid not in paper_ids:
                    paper_ids.append(pid)
        except Exception as e:
            logger.warning(f"Venue arXiv search failed for '{venue}': {e}")

        return self.persist_hits(sub["id"], paper_ids, "venue")

    # ------------------------------------------------------------------
    # Hit management
    # ------------------------------------------------------------------

    def persist_hits(
        self,
        subscription_id: int,
        paper_ids: List[str],
        matched_reason: str = "",
    ) -> int:
        """Dedupe and persist paper IDs as subscription hits.

        Only IDs that are not already recorded against *subscription_id*
        will be inserted.  Returns the count of new hits persisted.
        """
        new_ids = self.dedupe_hits(paper_ids, subscription_id)
        for pid in new_ids:
            paper_id = _canonical_paper_id(pid)
            if not paper_id:
                continue
            self._store.upsert_subscription_hit(
                subscription_id,
                paper_id,
                matched_reason=matched_reason,
            )
        return len(new_ids)

    def dedupe_hits(
        self, paper_ids: List[str], subscription_id: int
    ) -> List[str]:
        """Return only *paper_ids* not yet recorded for this subscription."""
        if not paper_ids:
            return []
        existing = self._store.list_subscription_hits(
            subscription_id=subscription_id, limit=10000
        )
        existing_ids = {h["paper_id"] for h in existing}
        return [pid for pid in paper_ids if pid not in existing_ids]

    # ------------------------------------------------------------------
    # Inbox lifecycle
    # ------------------------------------------------------------------

    def send_hit_to_inbox(self, hit_id: int) -> bool:
        """Send a hit to the reading queue inbox."""
        try:
            return self._svc.send_hit_to_inbox(hit_id)
        except Exception as e:
            logger.error(f"Error sending hit {hit_id} to inbox: {e}")
            return False

    def ignore_hit(self, hit_id: int) -> bool:
        """Mark a hit as ignored."""
        try:
            return self._svc.ignore_hit(hit_id)
        except Exception as e:
            logger.error(f"Error ignoring hit {hit_id}: {e}")
            return False
