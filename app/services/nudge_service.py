"""Nudge Service — detects reading behavior patterns and generates lightweight suggestions.

Architecture-ready implementation (B-ENG-5):
  - Opened multiple times without marking as read → nudge to add takeaway
  - In reading queue for N+ days without action → nudge to prioritize
  - Recently added papers to reading → positive reinforcement

Nudges are returned as structured dicts for display in the UI.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional


NUDGE_THRESHOLD_DAYS = 7       # days in reading before nudge
NUDGE_OPEN_COUNT = 3            # paper opens before suggesting takeaway


class NudgeService:
    """Generate behavior-based nudges for a workspace."""

    def __init__(self, state_store):
        self._store = state_store

    def get_nudges(self, research_question_id: int) -> list[dict]:
        """Return a list of nudges for the given workspace."""
        nudges: list[dict] = []
        now = datetime.now(timezone.utc)

        queue_items = self._store.list_queue_items(research_question_id=research_question_id) or []
        events = self._store.list_interaction_events(limit=200) or []

        # Nudge 1: Papers in reading for N+ days
        stagnant = self._find_stagnant_papers(queue_items, now)
        nudges.extend(stagnant)

        # Nudge 2: Papers opened multiple times without takeaway
        untaken = self._find_untaken_insights(queue_items, events, research_question_id)
        nudges.extend(untaken)

        # Nudge 3: Positive reinforcement for recent reading activity
        recent = self._find_recent_activity(queue_items, now)
        nudges.extend(recent)

        return nudges[:5]  # cap at 5 nudges

    def _find_stagnant_papers(
        self, queue_items: list[dict], now: datetime,
    ) -> list[dict]:
        """Papers added to reading more than N days ago with no progress.

        Uses reading_started_at as the primary timestamp; falls back to
        updated_at for legacy records. Does not rely on created_at which
        may not exist on all queue items.
        """
        nudges = []
        threshold = now - timedelta(days=NUDGE_THRESHOLD_DAYS)
        for item in queue_items:
            if item.get("status") != "Inbox":
                continue
            timestamp = item.get("reading_started_at") or item.get("updated_at") or ""
            if not timestamp:
                continue
            try:
                added_dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                continue
            if added_dt < threshold:
                meta = self._store.get_paper_metadata(item["paper_id"]) or {}
                title = meta.get("title", item["paper_id"])
                days = (now - added_dt).days
                nudges.append({
                    "type": "stagnant_reading",
                    "paper_id": item["paper_id"],
                    "title": title,
                    "message": f"\"{title}\" has been in reading for {days} days.",
                    "action_label": "Mark as read",
                    "action_url": f"/papers/{item['paper_id']}",
                    "priority": "medium",
                })
        return nudges

    def _find_untaken_insights(
        self, queue_items: list[dict], events: list[dict], rq_id: int,
    ) -> list[dict]:
        """Papers opened multiple times without a takeaway.

        Only counts paper_opened events that are attributed to the current
        workspace (via payload.research_question_id). Falls back to paper
        membership for legacy events without payload attribution.
        """
        import json

        workspace_papers = self._store.list_workspace_papers(rq_id) or []
        ws_paper_ids = {wp["paper_id"] for wp in workspace_papers}

        nudges = []
        paper_opens: dict[str, int] = {}
        for ev in events:
            if ev["event_type"] != "paper_opened":
                continue
            pid = ev["paper_id"]
            # Check payload for workspace attribution
            payload_raw = ev.get("payload_json", {})
            if isinstance(payload_raw, str):
                try:
                    payload = json.loads(payload_raw)
                except Exception:
                    payload = {}
            else:
                payload = payload_raw
            if isinstance(payload, dict):
                e_rq = payload.get("research_question_id")
                if e_rq is not None and int(e_rq) == rq_id:
                    paper_opens[pid] = paper_opens.get(pid, 0) + 1
                    continue
            # Fallback: if paper belongs to this workspace, count it
            if pid in ws_paper_ids:
                paper_opens[pid] = paper_opens.get(pid, 0) + 1

        for pid, count in paper_opens.items():
            if count < NUDGE_OPEN_COUNT:
                continue
            # Check if takeaway exists
            takeaway = self._store.get_reading_takeaway(pid, research_question_id=rq_id)
            if takeaway and takeaway.get("takeaway_text", "").strip():
                continue
            meta = self._store.get_paper_metadata(pid) or {}
            title = meta.get("title", pid)
            nudges.append({
                "type": "missing_takeaway",
                "paper_id": pid,
                "title": title,
                "message": f"You've opened \"{title}\" {count} times. Care to capture a takeaway?",
                "action_label": "Add takeaway",
                "action_url": f"/papers/{pid}?research_question_id={rq_id}",
                "priority": "low",
            })
        return nudges

    def _find_recent_activity(
        self, queue_items: list[dict], now: datetime,
    ) -> list[dict]:
        """Positive reinforcement for papers read this week."""
        nudges = []
        week_ago = now - timedelta(days=7)
        recent_reads = []
        for item in queue_items:
            if item.get("status") != "Completed":
                continue
            updated = item.get("updated_at", "")
            if not updated:
                continue
            try:
                updated_dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                continue
            if updated_dt > week_ago:
                meta = self._store.get_paper_metadata(item["paper_id"]) or {}
                recent_reads.append(meta.get("title", item["paper_id"]))

        if recent_reads:
            count = len(recent_reads)
            nudges.append({
                "type": "recent_progress",
                "paper_id": "",
                "title": "",
                "message": f"You read {count} paper{'s' if count > 1 else ''} this week. Keep it up!",
                "action_label": "View reading",
                "action_url": "/reading",
                "priority": "low",
            })
        return nudges
