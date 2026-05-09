"""Evaluation dashboard page route."""
from __future__ import annotations

from flask import Blueprint, render_template

from app.viewmodels.eval_viewmodel import EvalViewModel
from state_store import get_state_store

bp = Blueprint("evaluation", __name__, url_prefix="")


@bp.get("/evaluation")
def evaluation_dashboard():
    """Render the evaluation dashboard."""
    store = get_state_store()
    vm = EvalViewModel(store)
    return render_template("eval_dashboard.html", **vm.to_dashboard_context())
