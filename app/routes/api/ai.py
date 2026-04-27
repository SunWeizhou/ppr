"""AI Analysis API routes."""
from flask import jsonify, request

from . import bp
from .helpers import _ai_analysis_service, _current_state_store


@bp.get("/api/papers/<paper_id>/analysis")
def get_paper_analysis(paper_id):
    analysis = _ai_analysis_service().get_analysis(paper_id)
    if not analysis:
        return jsonify({"success": False, "error": "analysis_not_found"}), 404
    return jsonify({"success": True, "analysis": analysis})


@bp.post("/api/papers/<paper_id>/analysis/generate")
def generate_paper_analysis(paper_id):
    service = _ai_analysis_service()
    data = request.get_json() or {}
    paper = dict(data.get("paper") or {})
    paper["id"] = paper_id

    # Build structured recommendation reason for the response
    recommendation_reason = None
    try:
        from app.services.scoring_service import build_recommendation_reason

        recommendation_reason = build_recommendation_reason(
            paper,
            user_profile=data.get("user_profile"),
            run_context=data.get("recommendation_context"),
        )
    except Exception:
        pass

    try:
        analysis = service.get_or_create_analysis(
            paper,
            user_profile=data.get("user_profile"),
            recommendation_context=data.get("recommendation_context"),
            force=bool(data.get("force", False)),
        )
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400

    result = {"success": True, "analysis": analysis}
    if recommendation_reason:
        result["recommendation_reason"] = recommendation_reason
    return jsonify(result)
