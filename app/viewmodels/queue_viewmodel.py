"""Queue page viewmodel."""

from __future__ import annotations

from app.viewmodels.shared import (
    assemble_page_context,
    build_nav_items,
    serialize_collection,
    serialize_job,
    serialize_saved_search,
)
from state_store import QUEUE_STATUS_VALUES


class QueueViewModel:
    def __init__(self, queue_service, state_store):
        self.queue_service = queue_service
        self.state_store = state_store

    def to_template_context(self, *, active_status: str = "Inbox"):
        feedback = self.queue_service.load_feedback()
        context = assemble_page_context(self.state_store, active_tab="queue", feedback=feedback)
        context.update({
            "title": "Queue - arXiv Recommender",
            "active_tab": "queue",
            "queue_counts": self.queue_service.count_by_status(),
            "queue_status_values": QUEUE_STATUS_VALUES,
            "queue_items": self.queue_service.resolve_papers(status=active_status),
            "active_status": active_status,
            "reading_plan": self.queue_service.get_todays_reading_plan(),
        })
        return context
