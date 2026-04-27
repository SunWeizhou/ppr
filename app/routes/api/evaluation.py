"""Evaluation API routes."""
from flask import jsonify, request

from . import bp
from .helpers import _current_state_store


@bp.post("/api/evaluation/run")
def run_evaluation_api():
    """Run evaluation and return results."""
    from app.viewmodels.eval_viewmodel import EvalViewModel

    vm = EvalViewModel(_current_state_store())
    k = request.args.get("k", "5,10,20")
    return jsonify(vm.run_evaluation(k))


@bp.get("/api/evaluation/reports")
def list_evaluation_api():
    """List evaluation reports."""
    from app.viewmodels.eval_viewmodel import EvalViewModel

    vm = EvalViewModel(_current_state_store())
    reports = vm.list_reports()
    return jsonify({"success": True, "reports": reports})
