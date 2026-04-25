"""API route ownership for the Flask app."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.services.queue_service import QueueService
from state_store import QUEUE_STATUS_VALUES, get_state_store

bp = Blueprint("api", __name__)
STATE_STORE = get_state_store()


def _queue_service():
    try:
        import web_server

        state_store = web_server.STATE_STORE
    except Exception:
        state_store = STATE_STORE
    return QueueService(state_store)


@bp.post("/api/feedback")
def handle_feedback():
    import web_server

    return web_server.handle_feedback()


@bp.get("/api/feedback/stats")
def feedback_stats():
    import web_server

    return web_server.feedback_stats()


@bp.get("/api/pdf/<paper_id>")
def download_pdf(paper_id):
    import web_server

    return web_server.download_pdf(paper_id)


@bp.get("/api/dates")
def get_dates():
    import web_server

    return web_server.get_dates()


@bp.post("/api/feedback/learn")
def trigger_learning():
    import web_server

    return web_server.trigger_learning()


@bp.get("/api/citation/<paper_id>")
def get_citation(paper_id):
    import web_server

    return web_server.get_citation(paper_id)


@bp.get("/api/fetch_paper/<paper_id>")
def fetch_paper_info(paper_id):
    import web_server

    return web_server.fetch_paper_info(paper_id)


@bp.get("/api/export/bibtex/<paper_id>")
def export_bibtex(paper_id):
    import web_server

    return web_server.export_bibtex(paper_id)


@bp.get("/api/refresh")
def refresh_recommendations():
    import web_server

    return web_server.refresh_recommendations()


@bp.get("/api/status")
def get_status():
    import web_server

    return web_server.get_status()


@bp.get("/api/state/export")
def export_state_snapshot():
    import web_server

    return web_server.export_state_snapshot()


@bp.post("/api/state/import")
def import_state_snapshot():
    import web_server

    return web_server.import_state_snapshot()


@bp.get("/api/job/status")
def get_job_status():
    import web_server

    return web_server.get_job_status()


@bp.route("/api/collections", methods=["GET", "POST", "PUT", "DELETE"])
def manage_collections():
    import web_server

    return web_server.manage_collections()


@bp.get("/api/collections/<int:collection_id>")
def get_collection_detail(collection_id):
    import web_server

    return web_server.get_collection_detail(collection_id)


@bp.route("/api/collections/<int:collection_id>/papers", methods=["GET", "POST", "DELETE"])
def add_collection_paper(collection_id):
    import web_server

    return web_server.add_collection_paper(collection_id)


@bp.route("/api/saved-searches", methods=["GET", "POST", "PUT", "DELETE"])
def manage_saved_searches():
    import web_server

    return web_server.manage_saved_searches()


@bp.get("/api/saved-searches/<int:search_id>/run")
def run_saved_search(search_id):
    import web_server

    return web_server.run_saved_search(search_id)


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
        existing = service.state_store.get_queue_item(paper_id)
        status = existing.get("status") if existing else None
    if status not in QUEUE_STATUS_VALUES:
        return jsonify({"success": False, "error": "Invalid status"}), 400

    item, event_id = service.update_status(
        paper_id,
        status,
        source=data.get("source", "queue_api"),
        note=data.get("note"),
        tags=data.get("tags"),
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

    return jsonify({"success": True, "items": updated, "count": len(updated)})


@bp.post("/api/search")
def api_search():
    import web_server

    return web_server.api_search()


@bp.post("/api/settings")
def save_settings():
    import web_server

    return web_server.save_settings()


@bp.get("/api/related/<paper_id>")
def get_related_papers(paper_id):
    import web_server

    return web_server.get_related_papers(paper_id)


@bp.route("/api/keywords", methods=["GET", "POST", "DELETE"])
def manage_keywords():
    import web_server

    return web_server.manage_keywords()


@bp.post("/api/scholars/add")
def api_add_scholar():
    import web_server

    return web_server.api_add_scholar()


@bp.post("/api/scholars/parse_gscholar")
def api_parse_gscholar():
    import web_server

    return web_server.api_parse_gscholar()


@bp.post("/api/scholars/remove")
def api_remove_scholar():
    import web_server

    return web_server.api_remove_scholar()


@bp.post("/api/scholars/update")
def api_update_scholar():
    import web_server

    return web_server.api_update_scholar()


@bp.get("/debug")
def debug_info():
    import web_server

    return web_server.debug_info()
