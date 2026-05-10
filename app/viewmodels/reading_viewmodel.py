"""Reading page viewmodel — merged queue + library experience."""

from __future__ import annotations

from app.services.queue_service import QueueService
from app.viewmodels.library_viewmodel import LibraryViewModel
from app.viewmodels.shared import assemble_page_context, serialize_collection
from state_store import QUEUE_STATUS_VALUES

ACTIVE_READING_STATUSES = ("Skim Later", "Deep Read")


class ReadingViewModel:
    def __init__(self, state_store):
        self._store = state_store

    def to_template_context(self, *, tab: str = "active"):
        base = assemble_page_context(self._store, active_tab="reading")
        queue_service = QueueService(self._store)
        all_status_counts = queue_service.count_by_status()
        queue_counts = {
            k: v for k, v in all_status_counts.items()
            if k in ACTIVE_READING_STATUSES
        }

        def _valid(paper: dict) -> bool:
            """Exclude unresolvable placeholder items."""
            return paper.get("source") != "placeholder"

        active_items = [p for p in queue_service.resolve_papers(status="Skim Later") if _valid(p)]
        deep_read_items = [p for p in queue_service.resolve_papers(status="Deep Read") if _valid(p)]
        saved_items = [p for p in queue_service.resolve_papers(status="Saved") if _valid(p)]

        library_vm = LibraryViewModel(self._store)
        library_ctx = library_vm.to_template_context(tab="collections")

        context = {
            "title": "Reading - Agent Literature Research Assistant",
            "active_tab": "reading",
            "tab": tab,
            "queue_counts": queue_counts,
            "all_status_counts": all_status_counts,
            "queue_status_values": QUEUE_STATUS_VALUES,
            "active_statuses": ACTIVE_READING_STATUSES,
            "active_items": active_items,
            "deep_read_items": deep_read_items,
            "saved_items": saved_items,
            "collections_raw": library_ctx.get("collections_raw", base.get("all_collections", [])),
            "active_reading_count": sum(queue_counts.values()),
            "saved_count": len(saved_items),
        }
        context.update(base)
        return context
