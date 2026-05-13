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
    store = _current_state_store()
    service = RecommendationWorkspaceService(store)
    research_question_id = data.get("research_question_id")

    # Enrich query with workspace context if available
    query = str(data.get("query") or data.get("q") or "")
    if research_question_id and not query:
        ws = store.get_research_question(int(research_question_id))
        if ws:
            query = ws.get("query_text", "")

    result = service.run(
        mode=str(data.get("mode") or "for_you"),
        query=query,
        max_results=int(data.get("max_results") or 20),
        research_question_id=research_question_id,
    )
    # Serialize sections: convert Candidate objects to dicts
    sections = []
    for section in result.get("sections", []):
        sections.append({
            "strategy": section["strategy"],
            "title": section["title"],
            "papers": section["papers"],
        })
    return jsonify({
        "success": True,
        "run_id": result.get("run_id"),
        "mode": result.get("mode"),
        "query": result.get("query"),
        "sections": sections,
        "papers": result.get("papers", []),
        "count": result.get("count", 0),
    })


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