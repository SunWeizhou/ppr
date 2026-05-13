"""Cleaner execution layer for subscription lifecycle.

SubscriptionRunner wraps SubscriptionService with type-specific search
methods, standalone deduplication, and explicit hit persistence.  The
type-specific runners (run_query_subscription, run_author_subscription,
run_venue_subscription) each search local recommendation data as well as
the arXiv API, then dedupe and persist new hits.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional

from logger_config import get_logger
from app.services.subscription_service import SubscriptionService
from app.data._constants import canonical_paper_id as _canonical_paper_id

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
        """Run a single subscription by ID, dispatching to type-specific methods."""
        sub = self._store.get_subscription(subscription_id)
        if not sub:
            return {"success": False, "hit_count": 0, "error": "Subscription not found"}

        sub_type = sub.get("type", "query")
        entity_id = sub.get("entity_id")

        try:
            if sub_type == "query":
                hit_count = self.run_query_subscription(sub)
            elif sub_type == "author":
                hit_count = self.run_author_subscription(sub)
            elif sub_type == "venue":
                # Dispatch to journal or conference runner based on entity type
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

    def run_all_subscriptions(self) -> dict:
        """Run all enabled subscriptions, dispatching each by type."""
        subs = self._store.list_subscriptions()
        enabled_subs = [s for s in subs if s.get("enabled")]
        total_hits = 0
        errors = []

        for sub in enabled_subs:
            try:
                result = self.run_subscription(sub["id"])
                if result["success"]:
                    total_hits += result.get("hit_count", 0)
                elif result.get("error"):
                    errors.append({"subscription_id": sub["id"], "name": sub["name"], "error": result["error"]})
            except Exception as e:
                errors.append({"subscription_id": sub["id"], "name": sub["name"], "error": str(e)})

        self._store.record_event(
            "run_all_subscriptions",
            payload={"total_hits": total_hits, "subscriptions_checked": len(enabled_subs), "errors": len(errors)},
        )

        return {
            "success": True,
            "subscriptions_checked": len(enabled_subs),
            "total_hits": total_hits,
            "errors": errors,
        }

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _search_local_recommendations(
        self, match_fn: Callable[[dict], bool]
    ) -> List[str]:
        """Iterate recent recommendation items and collect paper_ids where *match_fn* is True."""
        paper_ids: List[str] = []
        try:
            runs = self._store.list_recommendation_runs(limit=10)
            for run in runs:
                items = self._store.get_recommendation_items(run["run_id"])
                for item in items:
                    if match_fn(item):
                        pid = _canonical_paper_id(item.get("paper_id") or "")
                        if pid and pid not in paper_ids:
                            paper_ids.append(pid)
        except Exception as e:
            logger.debug("Local recommendation lookup failed: %s", e)
        return paper_ids

    def _search_arxiv_api(
        self, query_terms: List[str], subscription_name: str
    ) -> List[str]:
        """Search arXiv API and return paper IDs."""
        from app.services.arxiv_source import search_by_keywords

        try:
            papers = search_by_keywords(
                query_terms, max_results=10, days_back=90
            )
        except Exception as e:
            logger.warning(
                f"arXiv search failed for '{subscription_name}': {e}"
            )
            return []
        paper_ids: List[str] = []
        for p in papers:
            pid = _canonical_paper_id(p.get("id") or p.get("paper_id") or "")
            if pid and pid not in paper_ids:
                paper_ids.append(pid)
        return paper_ids

    # ------------------------------------------------------------------
    # Type-specific runners
    # ------------------------------------------------------------------

    def run_query_subscription(self, sub: dict) -> int:
        """Run a single query-type subscription.

        Searches the arXiv API for papers matching the subscription's query
        text and also checks cached recommendation items for keyword matches
        in titles.  Returns the number of *new* hits persisted.
        """
        query_text = sub.get("query_text") or sub.get("name", "")
        keywords = [
            k.strip()
            for k in query_text.replace(",", " ").split()
            if k.strip()
        ]
        if not keywords:
            return 0

        def _match(item: dict) -> bool:
            title = (item.get("title") or "").lower()
            abstract = (item.get("abstract") or "").lower()
            return any(kw.lower() in title or kw.lower() in abstract for kw in keywords)

        paper_ids = self._search_local_recommendations(_match)
        paper_ids.extend(self._search_arxiv_api(keywords, query_text))
        return self.persist_hits(sub["id"], paper_ids, "query")

    def run_author_subscription(self, sub: dict) -> int:
        """Run a single author-type subscription.

        Checks cached recommendation items for papers by the target author
        and also searches the arXiv API via the ``au:`` prefix.  Returns the
        number of *new* hits persisted.
        """
        author_name = sub.get("query_text") or sub.get("name", "")
        if not author_name:
            return 0

        def _match(item: dict) -> bool:
            authors = item.get("authors", [])
            if isinstance(authors, list):
                return any(author_name.lower() in a.lower() for a in authors)
            return False

        paper_ids = self._search_local_recommendations(_match)
        paper_ids.extend(
            self._search_arxiv_api([f"au:{author_name}"], author_name)
        )
        return self.persist_hits(sub["id"], paper_ids, "author")

    def run_venue_subscription(self, sub: dict) -> int:
        """Run a venue subscription by category match."""
        venue = sub.get("query_text") or sub.get("name", "")
        if not venue:
            return 0

        def _match(item: dict) -> bool:
            categories = item.get("categories", [])
            if isinstance(categories, list):
                return any(venue.lower() in cat.lower() for cat in categories)
            return False

        paper_ids = self._search_local_recommendations(_match)
        paper_ids.extend(self._search_arxiv_api([venue], venue))
        return self.persist_hits(sub["id"], paper_ids, "venue")

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
            title = (item.get("title") or "").lower()
            abstract = (item.get("abstract") or "").lower()
            categories = item.get("categories", [])
            name_lower = journal_name.lower()
            return (
                name_lower in title
                or name_lower in abstract
                or any(name_lower in str(c).lower() for c in (categories if isinstance(categories, list) else []))
            )

        paper_ids = self._search_local_recommendations(_match)
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

        Searches arXiv by category (e.g. cs.AI) and matches local
        recommendations by category. Applies filters_json if present.
        """
        query_text = sub.get("query_text") or ""
        field_name = sub.get("name", "")

        # Get arXiv categories from linked entity if available
        entity_id = sub.get("entity_id")
        categories_to_search: List[str] = []
        if entity_id:
            entity = self._store.get_entity(entity_id)
            if entity:
                import json as _json
                meta = entity.get("metadata_json") or {}
                if isinstance(meta, str):
                    try:
                        meta = _json.loads(meta)
                    except (TypeError, _json.JSONDecodeError):
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
        for cat in categories_to_search:
            paper_ids.extend(self._search_arxiv_api([f"cat:{cat}"], field_name))
        paper_ids = self._apply_filters(paper_ids, sub.get("filters_json"))
        return self.persist_hits(sub["id"], paper_ids, f"field:{','.join(categories_to_search)}")

    def _run_entity_subscription(self, sub: dict) -> int:
        """Run a generic entity subscription with cross-type keyword search."""
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

    def _apply_filters(self, paper_ids: List[str], filters_json) -> List[str]:
        """Apply filters_json criteria to filter paper IDs.

        Currently supports keyword filtering from metadata cache.
        Papers without cached metadata are kept (can't filter them).
        """
        if not filters_json:
            return paper_ids

        import json as _json
        filters = filters_json
        if isinstance(filters, str):
            try:
                filters = _json.loads(filters)
            except (TypeError, _json.JSONDecodeError):
                return paper_ids

        if not isinstance(filters, dict) or not filters:
            return paper_ids

        keywords = filters.get("keywords", [])
        if not keywords:
            return paper_ids

        filtered = []
        for pid in paper_ids:
            metadata = self._store.get_paper_metadata(pid)
            if not metadata:
                filtered.append(pid)
                continue
            title = str((metadata.get("metadata_json") or {}).get("title", "")).lower()
            abstract = str((metadata.get("metadata_json") or {}).get("abstract", "")).lower()
            if any(kw.lower() in title or kw.lower() in abstract for kw in keywords):
                filtered.append(pid)
        return filtered


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
            logger.error("Error sending hit %s to inbox: %s", hit_id, e)
            return False

    def ignore_hit(self, hit_id: int) -> bool:
        """Mark a hit as ignored."""
        try:
            return self._svc.ignore_hit(hit_id)
        except Exception as e:
            logger.error("Error ignoring hit %s: %s", hit_id, e)
            return False
