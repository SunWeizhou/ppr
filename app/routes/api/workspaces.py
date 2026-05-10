"""Workspace API routes for research questions and planner runs."""

from flask import jsonify, request

from app.services.workspace_planner import WorkspacePlannerService
from app.services.workspace_service import WorkspaceService

from . import bp
from .helpers import _current_state_store


@bp.get("/api/workspaces/questions")
def list_workspace_questions():
    store = _current_state_store()
    status = request.args.get("status")
    try:
        questions = store.list_research_questions(status=status)
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    return jsonify({"success": True, "questions": questions})


@bp.post("/api/workspaces/questions")
def create_workspace_question():
    store = _current_state_store()
    data = request.get_json() or {}
    query_text = str(data.get("query_text") or "").strip()
    intent_statement = str(data.get("intent_statement") or "").strip()
    if not query_text:
        return jsonify({"success": False, "error": "Missing query_text"}), 400

    try:
        question = WorkspaceService(store).create_question(
            query_text,
            intent_statement=intent_statement,
            source="manual",
        )
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400

    return jsonify({"success": True, "question": question})


@bp.get("/api/workspaces/questions/<int:question_id>")
def get_workspace_question(question_id):
    store = _current_state_store()
    question = store.get_research_question(question_id)
    if question is None:
        return jsonify({"success": False, "error": "Research question not found"}), 404
    return jsonify({"success": True, "question": question})


@bp.get("/api/workspaces/questions/<int:question_id>/stats")
def get_workspace_stats(question_id):
    store = _current_state_store()
    try:
        stats = WorkspaceService(store).workspace_stats(question_id)
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404
    return jsonify({"success": True, "stats": stats})


@bp.post("/api/workspaces/questions/<int:question_id>/planner-runs")
def start_workspace_planner_run(question_id):
    store = _current_state_store()
    data = request.get_json() or {}
    trigger = str(data.get("trigger") or "manual").strip() or "manual"
    try:
        result = WorkspacePlannerService(store).start_run(question_id, trigger=trigger)
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    return jsonify({"success": True, "result": result})
