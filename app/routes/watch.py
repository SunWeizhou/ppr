"""Watch page routes — unified subscription monitoring."""

from __future__ import annotations

from flask import Blueprint, redirect, render_template, request

from app.viewmodels.monitor_viewmodel import MonitorViewModel
from state_store import get_state_store

bp = Blueprint("watch", __name__)


@bp.get("/watch")
def watch_page():
    store = get_state_store()
    vm = MonitorViewModel(store)
    return render_template(
        "watch.html",
        **vm.to_template_context(),
    )
