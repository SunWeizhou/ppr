"""Reading queue page routes."""

from __future__ import annotations

from flask import Blueprint, render_template, request

from state_store import QUEUE_STATUS_VALUES

bp = Blueprint("queue", __name__)


@bp.get("/queue")
def queue_page():
    import web_server

    status = request.args.get("status", "")
    if status and status not in QUEUE_STATUS_VALUES:
        status = ""
    page_context = web_server._build_page_context("queue")
    page_context.update(
        {
            "queue_items": web_server._resolve_queue_papers(status=status if status else None),
            "active_status": status,
            "queue_status_values": QUEUE_STATUS_VALUES,
        }
    )
    return render_template("queue_research.html", **page_context)
