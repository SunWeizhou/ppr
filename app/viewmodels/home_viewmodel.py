"""Home workspace viewmodel."""

from __future__ import annotations

from app.viewmodels.shared import assemble_page_context
from state_store import QUEUE_STATUS_VALUES


class HomeViewModel:
    """Build the quiet research workspace home surface."""

    def __init__(self, state_store):
        self._store = state_store

    def to_template_context(self) -> dict:
        base = assemble_page_context(self._store, active_tab="home")
        questions = self._safe_questions()
        queue_items = self._safe_queue_items()
        subscriptions = self._safe_subscriptions()
        watch_hits = self._safe_watch_hits()

        active_reading = [
            item for item in queue_items
            if item.get("status") in ("Skim Later", "Deep Read")
        ]
        inbox_items = [item for item in queue_items if item.get("status") == "Inbox"]

        context = {
            "title": "Search - Paper Agent",
            "active_tab": "home",
            "queue_status_values": QUEUE_STATUS_VALUES,
            "recent_questions": questions[:4],
            "active_reading_count": len(active_reading),
            "inbox_count": len(inbox_items),
            "watch_count": len(subscriptions),
            "watch_hit_count": len(watch_hits),
            "home_summaries": [
                {
                    "label": "Recent questions",
                    "value": len(questions),
                    "href": "/search",
                    "description": "Continue a research thread.",
                },
                {
                    "label": "Active reading",
                    "value": len(active_reading),
                    "href": "/reading",
                    "description": "Papers waiting for attention.",
                },
                {
                    "label": "Watch hits",
                    "value": len(watch_hits),
                    "href": "/watch",
                    "description": "New papers from tracked topics.",
                },
            ],
        }
        context.update(base)
        return context

    def _safe_questions(self) -> list[dict]:
        try:
            return self._store.list_research_questions(status="active")
        except Exception:
            return []

    def _safe_queue_items(self) -> list[dict]:
        try:
            return self._store.list_queue_items()
        except Exception:
            return []

    def _safe_subscriptions(self) -> list[dict]:
        try:
            return self._store.list_subscriptions()
        except Exception:
            return []

    def _safe_watch_hits(self) -> list[dict]:
        try:
            return self._store.list_subscription_hits(limit=20)
        except Exception:
            return []
