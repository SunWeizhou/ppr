"""Recommendations API routes."""

from __future__ import annotations

from flask import jsonify, request

from . import bp
from .helpers import _current_state_store
from app.services.recommendation_workspace_service import RecommendationWorkspaceService


@bp.get("/api/recommendations")
def list_recommendations():
    service = RecommendationWorkspaceService(_current_state_store())
    return jsonify({
        "success": True,
        "papers": service.latest_items(),
        "runs": service.list_recent(limit=6),
    })


@bp.post("/api/recommendations/runs")
def create_recommendation_run():
    data = request.get_json() or {}
    service = RecommendationWorkspaceService(_current_state_store())
    result = service.run(
        mode=str(data.get("mode") or "for_you"),
        query=str(data.get("query") or data.get("q") or ""),
        max_results=int(data.get("max_results") or 20),
    )
    return jsonify({"success": True, **result})


@bp.get("/api/recommendations/runs/<run_id>")
def get_recommendation_run(run_id):
    store = _current_state_store()
    items = store.get_recommendation_items(run_id)
    service = RecommendationWorkspaceService(store)
    return jsonify({
        "success": True,
        "run_id": run_id,
        "papers": service._decorate_items(items),
    })
