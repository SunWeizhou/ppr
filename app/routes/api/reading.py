"""Reading API routes — Mark as Read, takeaways."""
from flask import jsonify, request

from . import bp
from .helpers import _current_state_store, _queue_service


@bp.route("/api/reading/mark-read", methods=["POST"])
def mark_paper_read():
    """Mark a paper as Read, optionally with a takeaway."""
    data = request.get_json() or {}
    paper_id = data.get("paper_id", "")
    if not paper_id:
        return jsonify({"success": False, "error": "Missing paper_id"}), 400

    service = _queue_service()
    item = service.mark_paper_as_read(
        paper_id,
        research_question_id=data.get("research_question_id"),
        takeaway=data.get("takeaway", ""),
        source=data.get("source", "paper_detail"),
    )

    return jsonify({"success": True, "item": item})


@bp.route("/api/reading/takeaway", methods=["GET", "POST"])
def reading_takeaway():
    """Get or save a reading takeaway."""
    store = _current_state_store()

    if request.method == "GET":
        paper_id = request.args.get("paper_id", "")
        research_question_id = request.args.get("research_question_id", type=int)
        if not paper_id:
            return jsonify({"success": False, "error": "Missing paper_id"}), 400
        takeaway = store.get_reading_takeaway(paper_id, research_question_id=research_question_id)
        return jsonify({
            "success": True,
            "takeaway": takeaway.get("takeaway_text", "") if takeaway else "",
        })

    data = request.get_json() or {}
    paper_id = data.get("paper_id", "")
    if not paper_id:
        return jsonify({"success": False, "error": "Missing paper_id"}), 400

    takeaway_text = data.get("takeaway_text", "")
    if not takeaway_text:
        return jsonify({"success": False, "error": "Missing takeaway_text"}), 400

    store.save_reading_takeaway(
        paper_id,
        takeaway_text,
        research_question_id=data.get("research_question_id"),
    )
    store.record_event(
        "takeaway_added", paper_id,
        {"research_question_id": data.get("research_question_id"), "detail": takeaway_text[:200]},
    )

    return jsonify({"success": True})


@bp.route("/api/reading/key-paper", methods=["POST"])
def set_key_paper():
    """Accept or dismiss a paper as a key paper for a workspace."""
    data = request.get_json() or {}
    paper_id = data.get("paper_id", "")
    research_question_id = data.get("research_question_id")
    action = data.get("action", "")  # "accept" or "dismiss"

    if not paper_id or research_question_id is None or action not in ("accept", "dismiss"):
        return jsonify({"success": False, "error": "Missing paper_id, research_question_id, or invalid action"}), 400

    store = _current_state_store()
    relationship = "key_confirmed" if action == "accept" else "dismissed"
    store.upsert_workspace_paper(
        paper_id, research_question_id, relationship,
        reason=f"user {action}ed as key paper",
    )
    store.record_event(
        "key_paper_set", paper_id,
        {"research_question_id": research_question_id, "action": action},
    )

    return jsonify({"success": True, "relationship": relationship})
