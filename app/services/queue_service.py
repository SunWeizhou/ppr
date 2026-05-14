"""Queue service for reading workflow state and page data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from app.services.paper_resolver import PaperResolver
from app.services.paper_utils import (
    category_labels,
)
from app.services.paper_utils import (
    extract_primary_author as _extract_primary_author,
)
from app.services.paper_utils import (
    format_author_text as _format_author_text,
)
from app.services.paper_utils import (
    generate_relevance_html as _generate_relevance_html,
)
from app.services.paper_utils import (
    normalize_queue_status as _normalize_queue_status,
)
from app.services.paper_utils import (
    status_class as _status_class,
)
from app_paths import CACHE_DIR, HISTORY_DIR
from app.data._constants import QUEUE_STATUS_VALUES, canonical_paper_id as _canonical_paper_id


def _safe_load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


class QueueService:
    """Own queue business logic independently from Flask route handlers."""

    def __init__(self, state_store, *, cache_dir: Path | str = CACHE_DIR, history_dir: Path | str = HISTORY_DIR):
        self.state_store = state_store
        self.cache_dir = Path(cache_dir)
        self.history_dir = Path(history_dir)
        self._resolver = PaperResolver(state_store)

    def list_items(self, status: str | None = None):
        if status and status not in QUEUE_STATUS_VALUES:
            raise ValueError(f"Invalid queue status: {status}")
        return self.state_store.list_queue_items(status=status)

    def update_item(
        self,
        paper_id: str,
        status: str,
        *,
        source: str = "queue_service",
        note=None,
        tags=None,
        research_question_id=None,
        decision_context: str = "",
    ):
        canonical_id = _canonical_paper_id(paper_id)
        if not canonical_id:
            raise ValueError("Missing paper_id")
        if status not in QUEUE_STATUS_VALUES:
            raise ValueError(f"Invalid queue status: {status}")

        existing = self.state_store.get_queue_item(canonical_id)
        if note is None and existing:
            note = existing.get("note", "")
        if tags is None and existing:
            tags = existing.get("tags_json")
        if research_question_id is None and existing:
            research_question_id = existing.get("research_question_id")
        if not decision_context and existing:
            decision_context = existing.get("decision_context", "")
        return self.state_store.upsert_queue_item(
            canonical_id,
            status,
            source=source,
            note=note or "",
            tags=tags,
            research_question_id=research_question_id,
            decision_context=decision_context,
        )

    def update_status(
        self,
        paper_id: str,
        status: str,
        *,
        source: str = "queue_api",
        note=None,
        tags=None,
        research_question_id=None,
        decision_context: str = "",
    ):
        item = self.update_item(
            paper_id,
            status,
            source=source,
            note=note,
            tags=tags,
            research_question_id=research_question_id,
            decision_context=decision_context,
        )
        event_id = self.state_store.record_event(
            "queue_status_changed",
            item["paper_id"],
            {
                "status": status,
                "source": source,
                "note": item.get("note", ""),
                "research_question_id": research_question_id,
                "decision_context": decision_context,
            },
        )
        # Record reading_added event when moving to Inbox
        if status == "Inbox":
            self.state_store.record_event(
                "reading_added",
                item["paper_id"],
                {
                    "research_question_id": research_question_id,
                    "source": source,
                },
            )
        # Sync workspace-paper relationship
        if research_question_id is not None:
            ws_rel = "reading" if status == "Inbox" else "read" if status == "Completed" else "candidate"
            self.state_store.upsert_workspace_paper(
                item["paper_id"],
                research_question_id,
                ws_rel,
                reason=f"queue status: {status}",
            )
        return item, event_id

    def bulk_update(self, paper_ids, status: str, *, source: str = "queue_service", note: str = ""):
        return [
            self.update_item(paper_id, status, source=source, note=note)
            for paper_id in paper_ids
        ]

    def bulk_update_status(self, paper_ids, status: str, *, source: str = "queue_bulk", note: str = ""):
        canonical_ids = [_canonical_paper_id(item) for item in paper_ids if str(item).strip()]
        if not canonical_ids or not status:
            raise ValueError("Missing paper_ids or status")
        if status not in QUEUE_STATUS_VALUES:
            raise ValueError(f"Invalid queue status: {status}")
        updated = []
        for paper_id in canonical_ids:
            item, _ = self.update_status(paper_id, status, source=source, note=note)
            updated.append(item)
        return updated

    def add_to_reading(
        self,
        paper_id: str,
        *,
        source: str = "queue_service",
        note: str = "",
        research_question_id: Optional[int] = None,
        decision_context: str = "",
    ):
        """Unified entry point for adding a paper to the reading queue.

        Produces: queue item upsert, reading_added event,
        queue_status_changed event, and workspace_papers relation sync.
        """
        return self.update_status(
            paper_id, "Inbox",
            source=source,
            note=note,
            research_question_id=research_question_id,
            decision_context=decision_context,
        )

    def record_reading_event(
        self,
        event_type: str,
        paper_id: str,
        *,
        research_question_id: Optional[int] = None,
        detail: str = "",
    ) -> int:
        """Record a reading behavior event (reading_added, paper_opened,
        reading_completed, takeaway_added, etc.)."""
        return self.state_store.record_event(
            event_type,
            paper_id,
            {
                "research_question_id": research_question_id,
                "detail": detail,
            },
        )

    def mark_paper_as_read(
        self,
        paper_id: str,
        *,
        research_question_id: Optional[int] = None,
        takeaway: str = "",
        source: str = "reading_page",
    ) -> Dict:
        """Mark a paper as Completed, record reading_completed event,
        and optionally save a takeaway."""
        canonical_id = _canonical_paper_id(paper_id)
        item = self.update_item(
            canonical_id, "Completed", source=source,
            research_question_id=research_question_id,
        )
        self.record_reading_event(
            "reading_completed", canonical_id,
            research_question_id=research_question_id,
            detail="takeaway" if takeaway else "skip",
        )
        # Track workspace-paper relationship
        if research_question_id is not None:
            self.state_store.upsert_workspace_paper(
                canonical_id, research_question_id, "read",
                reason="marked as read",
            )
        if takeaway:
            self.state_store.save_reading_takeaway(
                canonical_id, takeaway,
                research_question_id=research_question_id,
            )
            self.record_reading_event(
                "takeaway_added", canonical_id,
                research_question_id=research_question_id,
                detail=takeaway[:200],
            )
        return item

    def count_by_status(self):
        counts = dict.fromkeys(QUEUE_STATUS_VALUES, 0)
        for item in self.state_store.list_queue_items():
            status = item.get("status")
            if status in counts:
                counts[status] += 1
        return counts

    def load_feedback(self):
        feedback = _safe_load_json(self.cache_dir / "user_feedback.json", {"liked": [], "disliked": []})
        liked = {_canonical_paper_id(item) for item in feedback.get("liked", [])}
        disliked = {_canonical_paper_id(item) for item in feedback.get("disliked", [])}
        return {
            "liked": [item for item in liked if item],
            "disliked": [item for item in disliked if item and item not in liked],
        }

    def _load_favorites(self):
        raw = _safe_load_json(self.cache_dir / "favorite_papers.json", {})
        favorites = {}
        if not isinstance(raw, dict):
            return favorites
        for paper_id, info in raw.items():
            canonical = _canonical_paper_id(paper_id)
            if canonical:
                favorites[canonical] = dict(info) if isinstance(info, dict) else {}
        return favorites

    def _load_paper_cache(self):
        raw = _safe_load_json(self.cache_dir / "paper_cache.json", {})
        paper_cache = {}
        if not isinstance(raw, dict):
            return paper_cache
        for paper_id, info in raw.items():
            canonical = _canonical_paper_id(paper_id)
            if canonical:
                paper_cache[canonical] = dict(info) if isinstance(info, dict) else {}
        return paper_cache

    def _load_history_paper_index(self):
        from utils import load_history_paper_index

        return load_history_paper_index(self.history_dir)

    def _resolve_paper_record(self, paper_id, *, history_index, favorites, paper_cache):
        return self._resolver.resolve(
            paper_id,
            history_index=history_index,
            favorites=favorites,
            paper_cache=paper_cache,
        )

    def _decorate_papers(self, papers, feedback, *, queue_overrides=None):
        queue_map = {
            item.get("paper_id"): _normalize_queue_status(item.get("status"))
            for item in self.state_store.list_queue_items()
        }
        if queue_overrides:
            queue_map.update(queue_overrides)

        decorated = []
        for idx, paper in enumerate(papers, start=1):
            item = dict(paper)
            item["rank"] = idx
            item["author_text"] = _format_author_text(item.get("authors"))
            item["first_author"] = _extract_primary_author(item.get("authors"))
            item["queue_status"] = queue_map.get(item.get("id"))
            item["queue_status_class"] = _status_class(item["queue_status"])
            item["relevance_html"] = _generate_relevance_html(item)
            item["is_incomplete"] = not item.get("score")
            item["is_liked"] = item.get("id") in feedback.get("liked", [])
            item["is_disliked"] = item.get("id") in feedback.get("disliked", [])
            item["category_labels"] = category_labels(item.get("categories", []))
            item["summary_short"] = (item.get("summary") or item.get("abstract") or "")[:220]
            decorated.append(item)
        return decorated

    def _attach_workspace_context(self, paper: dict, queue_item: dict) -> dict:
        research_question_id = queue_item.get("research_question_id")
        question = None
        if research_question_id is not None:
            question = self.state_store.get_research_question(research_question_id)

        claims = self.state_store.list_evidence_claims(
            paper_id=paper.get("id"),
            research_question_id=research_question_id,
        )
        by_type = {}
        for claim in claims:
            claim_type = claim.get("claim_type") or "factual"
            by_type[claim_type] = by_type.get(claim_type, 0) + 1

        paper["research_question_id"] = research_question_id
        paper["active_research_question"] = question
        paper["decision_context"] = queue_item.get("decision_context", "")
        paper["evidence_claims"] = claims[:3]
        paper["evidence_summary"] = {
            "total": len(claims),
            "by_type": by_type,
            "has_claims": bool(claims),
        }
        paper["detail_url"] = (
            f"/papers/{paper.get('id')}?research_question_id={research_question_id}"
            if research_question_id is not None
            else f"/papers/{paper.get('id')}"
        )
        return paper

    def get_todays_reading_plan(self) -> dict:
        """Return today's reading items."""
        from datetime import datetime

        from app.services.paper_utils import format_author_text as _fmt_authors

        today = datetime.now().strftime("%Y-%m-%d")
        all_items = self.list_items()
        today_items = [
            item
            for item in all_items
            if (item.get("updated_at") or "").startswith(today)
        ]

        history_index = self._load_history_paper_index()
        favorites = self._load_favorites()
        paper_cache = self._load_paper_cache()

        items: list = []

        for item in today_items:
            paper = self._resolve_paper_record(
                item.get("paper_id"),
                history_index=history_index,
                favorites=favorites,
                paper_cache=paper_cache,
            )
            paper["queue_status"] = item.get("status")
            paper["updated_at"] = item.get("updated_at", "")
            paper["queue_note"] = item.get("note", "")
            items.append(paper)

        items.sort(key=lambda p: p.get("updated_at", ""), reverse=True)
        for paper in items[:8]:
            paper["author_text"] = _fmt_authors(paper.get("authors"))
            paper["summary_short"] = (paper.get("summary") or paper.get("abstract") or "")[:220]

        return {
            "items": items[:8],
        }

    def resolve_papers(self, status: str | None = None):
        feedback = self.load_feedback()
        history_index = self._load_history_paper_index()
        favorites = self._load_favorites()
        paper_cache = self._load_paper_cache()
        resolved = []
        for item in self.list_items(status=status):
            queue_status = _normalize_queue_status(item.get("status"))
            paper = self._resolve_paper_record(
                item.get("paper_id"),
                history_index=history_index,
                favorites=favorites,
                paper_cache=paper_cache,
            )
            paper["queue_status"] = queue_status
            paper["queue_status_class"] = _status_class(queue_status)
            paper["queue_note"] = item.get("note", "")
            paper["queue_tags"] = item.get("tags_json", [])
            paper["queue_source"] = item.get("source", "")
            paper["updated_at"] = item.get("updated_at", "")
            self._attach_workspace_context(paper, item)
            resolved.append(paper)
        return self._decorate_papers(
            resolved,
            feedback,
            queue_overrides={paper["id"]: paper["queue_status"] for paper in resolved},
        )
