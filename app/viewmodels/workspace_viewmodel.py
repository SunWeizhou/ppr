"""Workspace overview viewmodel — research question homepage."""

from __future__ import annotations

from typing import Optional

from app.services.workspace_service import WorkspaceService
from app.viewmodels.shared import assemble_page_context
from app.data._constants import QUEUE_STATUS_VALUES


class WorkspaceOverviewViewModel:
    """Build template context for the workspace overview page.

    Shows: workspace title, intent, stats, recent papers, reading progress,
    watch links, and future-facing placeholders (Memo, Reviews).
    """

    def __init__(self, state_store):
        self._store = state_store

    def to_template_context(self, workspace_id: int) -> dict:
        workspace = self._load_workspace(workspace_id)
        stats = self._load_stats(workspace_id)
        recent_papers = self._load_recent_papers(workspace_id)
        subscriptions = self._load_subscriptions(workspace_id)
        reading_items = self._load_reading_items(workspace_id)
        memo = self._load_memo(workspace_id)
        memory_stats = self._load_memory_stats(workspace_id)
        key_suggestions = self._load_key_suggestions(workspace_id)
        nudges = self._load_nudges(workspace_id)
        rag_papers = self._load_rag_papers(workspace_id)

        context = {
            "title": f"{workspace.get('title', 'Workspace')} - Paper Agent",
            "active_tab": "workspaces",
            "workspace": workspace,
            "workspace_id": workspace_id,
            "stats": stats,
            "queue_status_values": QUEUE_STATUS_VALUES,
            "recent_papers": recent_papers[:8],
            "subscription_count": len(subscriptions),
            "subscriptions": subscriptions[:5],
            "reading_items": reading_items[:10],
            "inbox_count": stats.get("undecided_count", 0),
            "completed_count": stats.get("completed_count", 0),
            "watch_count": len(subscriptions),
            "memo": memo,
            "has_memo": memo is not None,
            "has_reviews": bool(memo and memo.get("review_sections")),
            "memory_stats": memory_stats,
            "key_suggestions": key_suggestions,
            "has_key_suggestions": len(key_suggestions) > 0,
            "nudges": nudges,
            "rag_papers": rag_papers,
            "rag_paper_ids": [p["paper_id"] for p in rag_papers],
            "has_rag_papers": len(rag_papers) > 0,
        }
        # Shared page context
        base = assemble_page_context(self._store, active_tab="workspaces")
        context.update(base)
        return context

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _load_workspace(self, workspace_id: int) -> dict:
        try:
            q = self._store.get_research_question(workspace_id)
        except Exception:
            q = None
        if q is None:
            return {
                "id": workspace_id,
                "title": "Unknown workspace",
                "intent_statement": "",
                "status": "unknown",
                "created_at": "",
                "updated_at": "",
            }
        return {
            "id": q.get("id"),
            "title": q.get("query_text", "Untitled"),
            "intent_statement": q.get("intent_statement") or "",
            "status": q.get("status", "active"),
            "source": q.get("source", "manual"),
            "created_at": q.get("created_at", ""),
            "updated_at": q.get("updated_at", q.get("created_at", "")),
        }

    def _load_stats(self, workspace_id: int) -> dict:
        try:
            svc = WorkspaceService(self._store)
            return svc.workspace_stats(workspace_id)
        except Exception:
            return {
                "research_question_id": workspace_id,
                "queue_counts": {"Inbox": 0, "Completed": 0},
                "undecided_count": 0,
                "completed_count": 0,
            }

    def _load_recent_papers(self, workspace_id: int) -> list[dict]:
        """Return recent paper metadata for items linked to this workspace."""
        try:
            items = self._store.list_queue_items()
        except Exception:
            return []
        ws_items = [i for i in items if i.get("research_question_id") == workspace_id]
        ws_items.sort(key=lambda i: i.get("reading_started_at") or i.get("updated_at", "") or "", reverse=True)
        papers = []
        for item in ws_items[:8]:
            pid = item.get("paper_id") or ""
            meta = {}
            if pid:
                try:
                    meta = self._store.get_paper_metadata(pid) or {}
                except Exception:
                    meta = {}
            papers.append({
                "paper_id": pid,
                "title": meta.get("title", item.get("title", pid or "Untitled")),
                "authors": meta.get("authors", []),
                "author_text": ", ".join(meta.get("authors", [])[:3]),
                "venue": meta.get("venue", ""),
                "year": meta.get("year", ""),
                "status": item.get("status", "Inbox"),
                "source": item.get("source", ""),
                "created_at": item.get("created_at", ""),
            })
        return papers

    def _load_subscriptions(self, workspace_id: int) -> list[dict]:
        """Return subscriptions linked to this workspace."""
        try:
            all_subs = self._store.list_subscriptions()
        except Exception:
            return []
        return [s for s in all_subs if s.get("research_question_id") == workspace_id]

    def _load_memo(self, workspace_id: int) -> Optional[dict]:
        """Load the research memo for this workspace."""
        try:
            return self._store.get_memo(workspace_id)
        except Exception:
            return None

    def _load_nudges(self, workspace_id: int) -> list[dict]:
        """Load behavior-based nudges for this workspace."""
        try:
            from app.services.nudge_service import NudgeService
            return NudgeService(self._store).get_nudges(workspace_id)
        except Exception:
            return []

    def _load_memory_stats(self, workspace_id: int) -> dict:
        """Return counts for each workspace-paper relationship type."""
        try:
            papers = self._store.list_workspace_papers(workspace_id)
        except Exception:
            return {"candidate": 0, "reading": 0, "read": 0, "key_confirmed": 0}
        counts = {"candidate": 0, "reading": 0, "read": 0, "key_suggested": 0, "key_confirmed": 0}
        for p in papers:
            rel = p.get("relationship")
            if rel in counts:
                counts[rel] += 1
        return counts

    def _load_key_suggestions(self, workspace_id: int) -> list[dict]:
        """Use KeyPaperService to score and suggest key papers with explanations."""
        try:
            from app.services.key_paper_service import KeyPaperService
            service = KeyPaperService(self._store)
            return service.suggest_key_papers(workspace_id, max_results=5)
        except Exception:
            return []

    def _load_reading_items(self, workspace_id: int) -> list[dict]:
        """Return queue items in 'Completed' status for this workspace."""
        try:
            items = self._store.list_queue_items()
        except Exception:
            return []
        completed = [
            i for i in items
            if i.get("research_question_id") == workspace_id
            and i.get("status") == "Completed"
        ]
        completed.sort(key=lambda i: i.get("reading_completed_at") or i.get("updated_at", "") or "", reverse=True)
        return completed

    def _load_rag_papers(self, workspace_id: int) -> list[dict]:
        """Return papers that are enabled for RAG in this workspace."""
        try:
            wps = self._store.list_workspace_papers(workspace_id, rag_enabled=True) or []
        except Exception:
            return []
        papers = []
        for wp in wps:
            meta = self._store.get_paper_metadata(wp["paper_id"]) or {}
            papers.append({
                "paper_id": wp["paper_id"],
                "title": meta.get("title", wp["paper_id"]),
                "author_text": ", ".join((meta.get("authors") or [])[:2]) or "",
            })
        return papers
