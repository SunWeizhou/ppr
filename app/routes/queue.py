"""Reading queue page routes."""

from __future__ import annotations

from flask import Blueprint, render_template, request

from app.services.queue_service import QueueService
from app.viewmodels.queue_viewmodel import QueueViewModel
from state_store import QUEUE_STATUS_VALUES, get_state_store

bp = Blueprint("queue", __name__)
STATE_STORE = get_state_store()


@bp.get("/queue")
def queue_page():
    status = request.args.get("status") or "Inbox"
    if status not in QUEUE_STATUS_VALUES:
        status = "Inbox"
    service = QueueService(STATE_STORE)
    viewmodel = QueueViewModel(service, STATE_STORE)
    return render_template("queue_research.html", **viewmodel.to_template_context(active_status=status))
