"""Library service facade for collections and durable assets."""

from __future__ import annotations


class LibraryService:
    def __init__(self, state_store):
        self.state_store = state_store

    def list_collections(self):
        return self.state_store.list_collections()

    def create_collection(self, name: str, *, description: str = "", query_text: str = ""):
        return self.state_store.create_collection(name, description=description, query_text=query_text)

    def update_collection(self, collection_id: int, **changes):
        return self.state_store.update_collection(collection_id, **changes)

    def delete_collection(self, collection_id: int):
        return self.state_store.delete_collection(collection_id)

    def get_collection(self, collection_id: int):
        return self.state_store.get_collection(collection_id)

    def list_collection_papers(self, collection_id: int):
        return self.state_store.list_collection_papers(collection_id)

    def add_collection_paper(self, collection_id: int, paper_id: str, *, note: str = ""):
        return self.state_store.add_paper_to_collection(collection_id, paper_id, note=note)

    def remove_collection_paper(self, collection_id: int, paper_id: str):
        return self.state_store.remove_paper_from_collection(collection_id, paper_id)

