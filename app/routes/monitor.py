"""Monitor routes."""

from __future__ import annotations

from flask import Blueprint, render_template, request

from app.viewmodels.monitor_viewmodel import MonitorViewModel
from state_store import get_state_store

bp = Blueprint("monitor", __name__)


@bp.get("/monitor")
def monitor_page():
    store = get_state_store()
    vm = MonitorViewModel(store)
    return render_template(
        "monitor_research.html",
        **vm.to_template_context(tab=request.args.get("tab", "authors")),
    )


@bp.get("/evaluation")
def evaluation_page():
    """Render the evaluation dashboard."""
    from app.viewmodels.eval_viewmodel import EvalViewModel

    store = get_state_store()
    vm = EvalViewModel(store)
    return render_template("eval_dashboard.html", **vm.to_dashboard_context())


