"""Inbox Triage API routes."""
from datetime import datetime

from flask import jsonify, request

from . import bp
from .helpers import _current_state_store


@bp.get("/api/inbox/progress")
def inbox_progress():
    """Return today's triage progress stats.

    Query params:
        date  — YYYY-MM-DD (defaults to today)
        total — total papers shown on the page (defaults to handled count)
    """
    date_str = request.args.get("date") or datetime.now().strftime("%Y-%m-%d")
    progress = _current_state_store().get_inbox_progress(date_str)
    total_override = request.args.get("total", type=int)
    if total_override is not None and total_override > progress["handled"]:
        progress["total"] = total_override
        progress["untriaged"] = total_override - progress["handled"]
    return jsonify({"success": True, "data": progress})


@bp.post("/api/inbox/triage-complete")
def inbox_triage_complete():
    """Record that the user completed today's inbox triage session."""
    data = request.get_json() or {}
    date_str = data.get("date") or datetime.now().strftime("%Y-%m-%d")
    progress = _current_state_store().get_inbox_progress(date_str)
    total = data.get("total", progress["total"])

    summary = {
        "timestamp": datetime.now().isoformat(),
        "date": date_str,
        "papers_processed": progress["handled"],
        "papers_total": total,
        "papers_liked": progress["liked"],
        "papers_disliked": progress["disliked"],
        "papers_skimmed": progress["skimmed"],
        "papers_deep_read": progress["deep_read"],
        "papers_queued": progress["queued"],
    }

    _current_state_store().record_event(
        "inbox_triage_complete",
        payload=summary,
    )
    return jsonify({"success": True, "message": "Triage session recorded", "summary": summary})
