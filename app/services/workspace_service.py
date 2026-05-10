"""Workspace domain service for research questions and local stats."""

from __future__ import annotations

from collections import Counter
from typing import Dict

from state_store import QUEUE_STATUS_VALUES


class WorkspaceService:
    def __init__(self, state_store):
        self.state_store = state_store

    def create_question(
        self,
        query_text: str,
        *,
        intent_statement: str = "",
        source: str = "manual",
    ) -> Dict:
        return self.state_store.create_research_question(
            query_text=query_text,
            intent_statement=intent_statement,
            source=source,
        )

    def seed_from_profile_keywords(self, keywords: Dict) -> int:
        return self.state_store.seed_research_questions_from_keywords(keywords)

    def workspace_stats(self, research_question_id: int) -> Dict:
        question = self.state_store.get_research_question(research_question_id)
        if question is None:
            raise ValueError(f"Unknown research question: {research_question_id}")

        items = [
            item for item in self.state_store.list_queue_items()
            if item.get("research_question_id") == research_question_id
        ]
        counts = Counter(item.get("status") for item in items)
        queue_counts = {status: int(counts.get(status, 0)) for status in QUEUE_STATUS_VALUES}

        return {
            "research_question_id": research_question_id,
            "status": question["status"],
            "queue_counts": queue_counts,
            "undecided_count": queue_counts.get("Inbox", 0),
            "active_reading_count": queue_counts.get("Skim Later", 0) + queue_counts.get("Deep Read", 0),
            "saved_count": queue_counts.get("Saved", 0),
            "archived_count": queue_counts.get("Archived", 0),
        }
