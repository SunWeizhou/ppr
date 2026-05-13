"""Weekly Review Service — generates structured weekly reviews from workspace activity."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional


def _week_start(dt: Optional[datetime] = None) -> str:
    """Return the Monday of the current week as YYYY-MM-DD."""
    if dt is None:
        dt = datetime.now(timezone.utc)
    monday = dt - timedelta(days=dt.weekday())
    return monday.strftime("%Y-%m-%d")


def _format_duration(days: int) -> str:
    if days == 0:
        return "today"
    if days == 1:
        return "yesterday"
    return f"{days} days ago"


class WeeklyReviewService:
    """Generate and manage weekly reviews from workspace activity."""

    def __init__(self, state_store):
        self._store = state_store

    def generate_review(
        self,
        research_question_id: int,
        week_start: Optional[str] = None,
    ) -> dict:
        """Generate a structured weekly review for a workspace.

        Returns a dict with:
          - week_start
          - papers_read: list of papers marked read this week
          - takeaways: list of takeaways added this week
          - memo_updated: whether the memo was updated this week
          - reading_added: list of papers added to reading this week
          - event_summary: summary counts
          - content: a markdown-formatted review
        """
        if week_start is None:
            week_start = _week_start()

        week_end = (
            datetime.strptime(week_start, "%Y-%m-%d") + timedelta(days=7)
        ).strftime("%Y-%m-%d")

        # Gather workspace papers
        workspace_papers = self._store.list_workspace_papers(research_question_id) or []

        # Gather queue items for this workspace
        queue_items = self._store.list_queue_items() or []
        ws_items = [i for i in queue_items if i.get("research_question_id") == research_question_id]

        # Gather interaction events for this workspace
        events = self._store.list_interaction_events(limit=200) or []

        # Filter events relevant to this workspace and week
        ws_paper_ids = {wp["paper_id"] for wp in workspace_papers}
        week_events = [
            e for e in events
            if e["paper_id"] in ws_paper_ids
            and week_start <= (e.get("created_at", "") or "")[:10] < week_end
        ]

        # Categorize events
        reading_completed_events = [e for e in week_events if e["event_type"] == "reading_completed"]
        reading_added_events = [e for e in week_events if e["event_type"] == "reading_added"]
        takeaway_events = [e for e in week_events if e["event_type"] == "takeaway_added"]

        # Resolve paper titles for completed readings
        papers_read = []
        for event in reading_completed_events:
            pid = event["paper_id"]
            meta = self._store.get_paper_metadata(pid) or {}
            papers_read.append({
                "paper_id": pid,
                "title": meta.get("title", pid),
                "read_at": event.get("created_at", "")[:10],
            })

        # Load takeaways
        takeaways = self._store.list_reading_takeaways(research_question_id=research_question_id) or []

        # Check memo update
        memo = self._store.get_memo(research_question_id)
        memo_updated = bool(memo and memo.get("updated_at", "")[:10] >= week_start)

        # Counts
        event_summary = {
            "papers_read": len(papers_read),
            "papers_added": len(reading_added_events),
            "takeaways_added": len(takeaway_events),
            "memo_updated": memo_updated,
            "total_events": len(week_events),
        }

        # Read papers added (for the "added" list)
        added_papers = []
        for event in reading_added_events:
            pid = event["paper_id"]
            meta = self._store.get_paper_metadata(pid) or {}
            added_papers.append({
                "paper_id": pid,
                "title": meta.get("title", pid),
                "added_at": event.get("created_at", "")[:10],
            })

        # Generate markdown content
        content = self._build_review_markdown(
            workspace_name=self._get_workspace_name(research_question_id),
            week_start=week_start,
            papers_read=papers_read,
            added_papers=added_papers,
            takeaways=takeaways,
            event_summary=event_summary,
            memo_updated=memo_updated,
        )

        return {
            "week_start": week_start,
            "papers_read": papers_read,
            "added_papers": added_papers,
            "takeaways": takeaways,
            "memo_updated": memo_updated,
            "event_summary": event_summary,
            "content": content,
        }

    def _get_workspace_name(self, research_question_id: int) -> str:
        try:
            q = self._store.get_research_question(research_question_id)
            if q:
                return q.get("query_text", "Untitled Workspace")
        except Exception:
            pass
        return "Untitled Workspace"

    @staticmethod
    def _build_review_markdown(
        workspace_name: str,
        week_start: str,
        papers_read: list,
        added_papers: list,
        takeaways: list,
        event_summary: dict,
        memo_updated: bool,
    ) -> str:
        """Build a markdown-formatted weekly review."""
        week_end_dt = datetime.strptime(week_start, "%Y-%m-%d") + timedelta(days=6)
        week_end = week_end_dt.strftime("%Y-%m-%d")

        lines = [
            f"# Weekly Review: {workspace_name}",
            f"**Week:** {week_start} — {week_end}",
            "",
            "## Summary",
            f"- Papers read: {event_summary['papers_read']}",
            f"- Papers added: {event_summary['papers_added']}",
            f"- Takeaways: {event_summary['takeaways_added']}",
            f"- Memo updated: {'Yes' if memo_updated else 'No'}",
            "",
        ]

        if papers_read:
            lines.append("## Papers Read")
            lines.append("")
            for p in papers_read:
                title = p.get("title", p["paper_id"])
                lines.append(f"- [{title}](/papers/{p['paper_id']}) — read on {p['read_at']}")
            lines.append("")

        if added_papers:
            lines.append("## Papers Added to Reading")
            lines.append("")
            for p in added_papers:
                title = p.get("title", p["paper_id"])
                lines.append(f"- [{title}](/papers/{p['paper_id']})")
            lines.append("")

        if takeaways:
            lines.append("## Takeaways")
            lines.append("")
            for t in takeaways:
                pid = t.get("paper_id", "")
                meta = {}  # We don't have the service here, just use basic info
                lines.append(f"- {t.get('takeaway_text', '')}")
            lines.append("")

        lines.append("## Reflection")
        lines.append("")
        lines.append("### Which paper changed your understanding most?")
        lines.append("")
        lines.append("*(Write your reflection here)*")
        lines.append("")
        lines.append("### What uncertainty remains?")
        lines.append("")
        lines.append("*(Write your reflection here)*")
        lines.append("")
        lines.append("### What do you want to investigate next week?")
        lines.append("")
        lines.append("*(Write your reflection here)*")
        lines.append("")

        return "\n".join(lines)
