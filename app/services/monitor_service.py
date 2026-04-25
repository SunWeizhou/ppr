"""Monitor service facade for long-term author, venue, and query tracking."""

from __future__ import annotations


class MonitorService:
    def __init__(self, state_store):
        self.state_store = state_store

    def list_saved_searches(self):
        return self.state_store.list_saved_searches()

    def create_saved_search(self, name: str, query_text: str, *, filters=None):
        return self.state_store.create_saved_search(name, query_text, filters=filters or {})

    def update_saved_search(self, search_id: int, **changes):
        return self.state_store.update_saved_search(search_id, **changes)

    def delete_saved_search(self, search_id: int):
        return self.state_store.delete_saved_search(search_id)

