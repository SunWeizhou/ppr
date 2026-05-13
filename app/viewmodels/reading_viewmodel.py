"""Reading page viewmodel — merged queue + library experience."""

from __future__ import annotations

from app.services.queue_service import QueueService
from app.viewmodels.library_viewmodel import LibraryViewModel
from app.viewmodels.shared import assemble_page_context, serialize_collection
from app.data._constants import QUEUE_STATUS_VALUES

ACTIVE_READING_STATUSES = ("Inbox",)


class ReadingViewModel:
    def __init__(self, state_store):
        self._store = state_store

    def to_template_context(self, *, tab: str = "inbox"):
        base = assemble_page_context(self._store, active_tab="reading")
        queue_service = QueueService(self._store)
        all_status_counts = queue_service.count_by_status()

        def _valid(paper: dict) -> bool:
            return paper.get("source") != "placeholder"

        inbox_items = [p for p in queue_service.resolve_papers(status="Inbox") if _valid(p)]
        completed_items = [p for p in queue_service.resolve_papers(status="Completed") if _valid(p)]

        library_vm = LibraryViewModel(self._store)
        library_ctx = library_vm.to_template_context(tab="collections")

        context = {
            "title": "Reading - Paper Agent",
            "active_tab": "reading",
            "tab": tab,
            "queue_counts": all_status_counts,
            "all_status_counts": all_status_counts,
            "queue_status_values": QUEUE_STATUS_VALUES,
            "active_statuses": ACTIVE_READING_STATUSES,
            "inbox_items": inbox_items,
            "completed_items": completed_items,
            "collections_raw": library_ctx.get("collections_raw", base.get("all_collections", [])),
            "inbox_count": len(inbox_items),
            "completed_count": len(completed_items),
        }
        context.update(base)
        return context
