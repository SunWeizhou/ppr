"""Writing Prep API — generate outlines, skeletons, summaries, and export."""
from flask import jsonify, request

from . import bp
from .helpers import _current_state_store
from app.services.writing_prep_service import WritingPrepService


@bp.route("/api/writing-prep/<int:research_question_id>/<output_type>", methods=["POST"])
def generate_writing_prep(research_question_id: int, output_type: str):
    """Generate a writing-prep output for a workspace."""
    store = _current_state_store()
    ws = store.get_research_question(research_question_id)
    if not ws:
        return jsonify({"success": False, "error": "Workspace not found"}), 404

    service = WritingPrepService(store)

    generators = {
        "literature-review": service.generate_literature_review_outline,
        "related-work": service.generate_related_work_skeleton,
        "progress-summary": service.generate_progress_summary,
        "supervisor-update": service.generate_supervisor_update,
        "memo-suggestions": lambda rqid: service.generate_memo_suggestions(rqid),
    }

    gen = generators.get(output_type)
    if not gen:
        return jsonify({"success": False, "error": f"Unknown output type: {output_type}"}), 400

    result = gen(research_question_id)
    if isinstance(result, dict):
        return jsonify({"success": True, "output_type": output_type, **result})
    return jsonify({"success": True, "output_type": output_type, "content": result})


@bp.get("/api/review/<int:research_question_id>/export")
def export_review_markdown(research_question_id: int):
    """Export a weekly review as downloadable markdown."""
    store = _current_state_store()
    week_start = request.args.get("week_start", "")
    if not week_start:
        return jsonify({"success": False, "error": "Missing week_start parameter"}), 400

    saved = store.get_weekly_review_by_week(week_start, research_question_id=research_question_id)
    if not saved:
        return jsonify({"success": False, "error": "No review found for this week"}), 404

    service = WritingPrepService(store)
    ws = store.get_research_question(research_question_id) or {}
    ws_name = ws.get("query_text", "Untitled")

    # Build full review dict
    event_summary = saved.get("event_summary_json", {})
    if isinstance(event_summary, str):
        import json
        try:
            event_summary = json.loads(event_summary)
        except (json.JSONDecodeError, TypeError):
            event_summary = {}

    reflection = saved.get("reflection_answers_json", {})
    if isinstance(reflection, str):
        try:
            reflection = json.loads(reflection)
        except (json.JSONDecodeError, TypeError):
            reflection = {}

    review = {
        "content": saved.get("content", ""),
        "event_summary": event_summary,
        "reflection_answers": reflection,
    }

    markdown = service.export_review_markdown(review)
    filename = f"weekly-review-{ws_name}-{week_start}.md".replace(" ", "-")

    from flask import Response
    return Response(
        markdown,
        mimetype="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
