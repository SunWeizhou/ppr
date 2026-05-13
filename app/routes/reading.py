"""Reading page routes — merged queue + library experience."""

from __future__ import annotations

from flask import Blueprint, render_template, request

from app.services.queue_service import QueueService
from app.viewmodels.reading_viewmodel import ReadingViewModel
from state_store import get_state_store

bp = Blueprint("reading", __name__)
STATE_STORE = get_state_store()


_VALID_TABS = {"inbox", "completed", "collections"}


@bp.get("/reading")
def reading_page():
    tab = request.args.get("tab", "inbox")
    if tab not in _VALID_TABS:
        tab = "inbox"
    research_question_id = request.args.get("research_question_id", type=int)
    vm = ReadingViewModel(STATE_STORE)
    return render_template(
        "reading.html",
        **vm.to_template_context(tab=tab, research_question_id=research_question_id),
    )
