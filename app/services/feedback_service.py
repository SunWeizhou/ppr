"""Feedback service for normalized paper actions and interaction events."""

from __future__ import annotations

from state_store import _canonical_paper_id


class FeedbackService:
    def __init__(self, state_store):
        self.state_store = state_store

    def normalize_paper_id(self, paper_id: str) -> str:
        return _canonical_paper_id(paper_id)

    def record_event(self, event_type: str, paper_id: str = "", payload=None):
        return self.state_store.record_event(
            event_type,
            self.normalize_paper_id(paper_id) if paper_id else "",
            payload or {},
        )

