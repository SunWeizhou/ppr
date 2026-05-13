"""Home workspace viewmodel — Notion-like personal research desk.

Provides template context for Home v2:
- Continue Research: active workspaces with candidate/reading stats
- Today's Papers: recent queue items and watch hits worth attention
- Quick Start: new research question composer + search entry
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.services.workspace_service import WorkspaceService
from app.viewmodels.shared import assemble_page_context
from app.data._constants import QUEUE_STATUS_VALUES


class HomeViewModel:
    """Build the quiet, returning-user personal research desk surface."""

    def __init__(self, state_store):
        self._store = state_store

    def to_template_context(self) -> dict:
        base = assemble_page_context(self._store, active_tab="home")
        active_workspaces = self._load_active_workspaces()
        today_papers = self._load_today_papers()
        today_hits = self._load_today_hits()

        context = {
            "title": "Home - Paper Agent",
            "active_tab": "home",
            "queue_status_values": QUEUE_STATUS_VALUES,
            # Continue Research section
            "active_workspaces": active_workspaces[:8],
            "workspace_count": len(active_workspaces),
            "total_candidates": sum(w.get("undecided_count", 0) for w in active_workspaces),
            "total_reading": sum(w.get("completed_count", 0) for w in active_workspaces),
            # Today's Papers section
            "today_papers": today_papers[:8],
            "today_hits": today_hits[:5],
            "today_total": len(today_papers) + len(today_hits),
            # Quick Start data
            "inbox_count": len(today_papers),
            "watch_hit_count": len(today_hits),
            "last_active_workspace": active_workspaces[0] if active_workspaces else None,
        }
        context.update(base)
        return context

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _load_active_workspaces(self) -> list[dict]:
        """Return active research questions decorated with candidate/reading stats."""
        try:
            questions = self._store.list_research_questions(status="active")
        except Exception:
            return []

        svc = WorkspaceService(self._store)
        workspaces = []
        for q in questions:
            qid = q.get("id")
            if not qid:
                continue
            try:
                stats = svc.workspace_stats(qid)
            except Exception:
                stats = {"undecided_count": 0, "completed_count": 0}
            workspaces.append({
                "id": qid,
                "title": q.get("query_text", "Untitled"),
                "intent_statement": q.get("intent_statement") or "",
                "status": q.get("status", "active"),
                "created_at": q.get("created_at", ""),
                "updated_at": q.get("updated_at", q.get("created_at", "")),
                "undecided_count": stats.get("undecided_count", 0),
                "completed_count": stats.get("completed_count", 0),
                "inbox_count": stats.get("queue_counts", {}).get("Inbox", 0),
            })
        # Sort by most recently updated
        workspaces.sort(key=lambda w: w.get("updated_at", "") or "", reverse=True)
        return workspaces

    def _load_today_papers(self) -> list[dict]:
        """Return recent inbox queue items as today's paper activity."""
        try:
            items = self._store.list_queue_items()
        except Exception:
            return []
        # Only inbox items, sorted by created_at desc, limit to recent
        inbox = [i for i in items if i.get("status") == "Inbox"]
        inbox.sort(key=lambda i: i.get("created_at", "") or "", reverse=True)
        papers = []
        for item in inbox[:8]:
            pid = item.get("paper_id") or item.get("id", "")
            meta = {}
            if pid:
                try:
                    meta = self._store.get_paper_metadata(pid) or {}
                except Exception:
                    meta = {}
            papers.append({
                "paper_id": pid,
                "title": meta.get("title", item.get("title", "Untitled")),
                "authors": meta.get("authors", item.get("authors", [])),
                "venue": meta.get("venue", ""),
                "source": meta.get("source", ""),
                "year": meta.get("year", ""),
                "created_at": item.get("created_at", ""),
                "research_question_id": item.get("research_question_id"),
            })
        return papers

    def _load_today_hits(self) -> list[dict]:
        """Return recent subscription hits."""
        try:
            hits = self._store.list_subscription_hits(limit=10)
        except Exception:
            return []
        today_hits = []
        for hit in hits:
            pid = hit.get("paper_id") or hit.get("id", "")
            today_hits.append({
                "paper_id": pid,
                "title": hit.get("title", "Untitled"),
                "subscription_name": hit.get("subscription_name", ""),
                "created_at": hit.get("created_at", ""),
            })
        return today_hits[:5]
