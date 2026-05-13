"""Queue API routes."""
from flask import jsonify, request

from . import bp
from .helpers import _current_state_store, _queue_service
from app.data._constants import QUEUE_STATUS_VALUES


@bp.route("/api/queue", methods=["GET", "POST"])
def manage_queue():
    service = _queue_service()
    if request.method == "GET":
        status = request.args.get("status")
        if status and status not in QUEUE_STATUS_VALUES:
            return jsonify({"success": False, "error": "Invalid status"}), 400
        return jsonify({"success": True, "items": service.list_items(status=status)})

    data = request.get_json() or {}
    paper_id = data.get("paper_id", "")
    status = data.get("status")
    if not paper_id:
        return jsonify({"success": False, "error": "Missing paper_id"}), 400
    if status is None:
        existing = _current_state_store().get_queue_item(paper_id)
        status = existing.get("status") if existing else None
    if status not in QUEUE_STATUS_VALUES:
        return jsonify({"success": False, "error": "Invalid status"}), 400

    item, event_id = service.update_status(
        paper_id,
        status,
        source=data.get("source", "queue_api"),
        note=data.get("note"),
        tags=data.get("tags"),
        research_question_id=data.get("research_question_id"),
        decision_context=data.get("decision_context", ""),
    )
    # Record queue status change interaction event
    _current_state_store().record_event(
        "queue_status_changed",
        paper_id,
        {
            "status": status,
            "research_question_id": data.get("research_question_id"),
            "decision_context": data.get("decision_context", ""),
        },
    )
    return jsonify({"success": True, "item": item, "event_id": event_id})


@bp.post("/api/queue/bulk")
def manage_queue_bulk():
    service = _queue_service()
    data = request.get_json() or {}
    try:
        updated = service.bulk_update_status(
            data.get("paper_ids", []),
            data.get("status"),
            source=data.get("source", "queue_bulk"),
            note=data.get("note", ""),
        )
    except ValueError as exc:
        message = str(exc)
        if "Invalid queue status" in message:
            message = "Invalid status"
        return jsonify({"success": False, "error": message}), 400

    # Record queue status change interaction events for each paper
    store = _current_state_store()
    for paper_id in data.get("paper_ids", []):
        store.record_event("queue_status_changed", paper_id, {"status": data.get("status")})

    return jsonify({"success": True, "items": updated, "count": len(updated)})
