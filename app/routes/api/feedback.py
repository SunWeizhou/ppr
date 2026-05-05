"""Feedback and recommendation-status API routes."""
import json
import logging
import threading
from datetime import datetime

from flask import jsonify, request

from . import bp
from .helpers import (
    _build_recommendation_health,
    _current_state_store,
    _feedback_service,
    FEEDBACK_FILE,
    CACHE_DIR,
    HISTORY_DIR,
    serialize_job,
)

logger = logging.getLogger(__name__)


@bp.post("/api/feedback")
def handle_feedback():
    data = request.get_json() or {}
    result, status = _feedback_service().handle_feedback(data)

    # Record semantic interaction events for feedback actions
    if status == 200 and result.get("success"):
        store = _current_state_store()
        action = data.get("action", "")
        paper_id = data.get("paper_id", "")
        if paper_id:
            if action == "like":
                store.record_event("feedback_relevant", paper_id)
            elif action == "dislike":
                store.record_event("feedback_ignored", paper_id)

    return jsonify(result), status


@bp.post("/api/feedback/batch")
def handle_feedback_batch():
    data = request.get_json() or {}
    paper_ids = data.get("paper_ids", [])
    action = data.get("action", "dislike")
    if not isinstance(paper_ids, list) or not paper_ids:
        return jsonify({"success": False, "error": "paper_ids must be a non-empty list"}), 400
    if action not in ("like", "dislike"):
        return jsonify({"success": False, "error": "action must be like or dislike"}), 400

    svc = _feedback_service()
    store = _current_state_store()
    success_count = 0
    for paper_id in paper_ids:
        result, _status = svc.handle_feedback({
            "paper_id": paper_id, "action": action, "source": "batch_triage",
        })
        if _status == 200 and result.get("success"):
            success_count += 1
            if action == "like":
                store.record_event("feedback_relevant", paper_id)
            elif action == "dislike":
                store.record_event("feedback_ignored", paper_id)
    return jsonify({"success": True, "processed": success_count, "total": len(paper_ids)})


@bp.get("/api/feedback/stats")
def feedback_stats():
    feedback = _feedback_service().load_feedback()
    return jsonify({
        "liked_count": len(feedback.get("liked", [])),
        "disliked_count": len(feedback.get("disliked", [])),
        "total_feedback": len(feedback.get("liked", [])) + len(feedback.get("disliked", [])),
    })


@bp.post("/api/feedback/learn")
def trigger_learning():
    """Trigger feedback model training (new v2 learner)."""
    try:
        from app.services.learner import retrain_if_needed
        from state_store import get_state_store

        trained = retrain_if_needed(get_state_store())
        auc = get_state_store().get_feedback_model_auc()

        return jsonify({
            "success": True,
            "trained": trained,
            "auc": auc,
        })
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@bp.post("/api/refresh")
def refresh_recommendations():
    """Force refresh today's recommendations via a background job."""
    force = request.args.get("force", "0") == "1"

    try:
        from arxiv_recommender_v5 import load_daily_recommendation, CONFIG as PIPELINE_CONFIG

        today = datetime.now().strftime("%Y-%m-%d")

        # Check SQLite first
        sqlite_run = _current_state_store().get_recommendation_run_by_date(today)
        has_sqlite = sqlite_run is not None

        # Then check JSON cache
        cached_papers, _ = load_daily_recommendation(PIPELINE_CONFIG["cache_dir"])
        has_json = cached_papers is not None

        if (has_sqlite or has_json) and not force:
            return jsonify({
                "success": True,
                "message": "今日推荐已存在",
                "has_recommendation": True,
                "source": "sqlite" if has_sqlite else "json",
                "date": today,
                "job_id": None,
            })

        # Recover stale running jobs (stuck > 30 min) before creating new one
        _current_state_store().recover_stale_jobs(stale_after_minutes=30)
        job = _current_state_store().create_job_if_no_active_job(
            "daily_recommendation",
            trigger_source="manual_refresh",
            payload={"force_refresh": True, "requested_force": force},
        )
        if job is None:
            return jsonify({
                "success": False,
                "error": "已有刷新任务正在排队或运行",
            }), 409

        def _run_pipeline_bg(run_id, force_refresh):
            try:
                from arxiv_recommender_v5 import run_pipeline

                _current_state_store().update_job(run_id, "running")
                papers = run_pipeline(force_refresh=force_refresh)
                _current_state_store().update_job(
                    run_id,
                    "succeeded",
                    result={
                        "paper_count": len(papers) if papers else 0,
                        "mode": "manual_refresh",
                    },
                )
            except Exception as exc:
                _current_state_store().update_job(run_id, "failed", error_text=str(exc))

        thread = threading.Thread(
            target=_run_pipeline_bg,
            args=(job["run_id"], True),
            daemon=True,
        )
        thread.start()

        return jsonify({
            "success": True,
            "message": "刷新任务已提交",
            "job_id": job["run_id"],
            "date": today,
        })
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@bp.get("/api/status")
def get_status():
    """Get recommendation status for today."""
    try:
        from arxiv_recommender_v5 import load_daily_recommendation, CONFIG as PIPELINE_CONFIG
        import json as _json

        today = datetime.now().strftime("%Y-%m-%d")

        # Check SQLite first
        sqlite_run = _current_state_store().get_recommendation_run_by_date(today)
        if sqlite_run:
            items = _current_state_store().get_recommendation_items(sqlite_run["run_id"])
            try:
                themes = _json.loads(sqlite_run.get("themes_json", "[]"))
            except (TypeError, _json.JSONDecodeError):
                themes = []
            latest_job = _current_state_store().get_latest_job("daily_recommendation")
            recommendation_health = _build_recommendation_health(items)
            return jsonify({
                "date": today,
                "has_recommendation": True,
                "source": "sqlite",
                "paper_count": len(items),
                "themes": themes,
                "run_id": sqlite_run["run_id"],
                "generated_at": sqlite_run.get("created_at", ""),
                "job": serialize_job(latest_job),
                "recommendation_health": recommendation_health,
            })

        # Fallback to JSON cache
        cached_papers, cached_themes = load_daily_recommendation(PIPELINE_CONFIG["cache_dir"])
        latest_job = _current_state_store().get_latest_job("daily_recommendation")
        recommendation_health = _build_recommendation_health(cached_papers)

        return jsonify({
            "date": today,
            "has_recommendation": cached_papers is not None,
            "source": "json" if cached_papers else None,
            "paper_count": len(cached_papers) if cached_papers else 0,
            "themes": cached_themes or [],
            "generated_at": datetime.now().isoformat(),
            "job": serialize_job(latest_job),
            "recommendation_health": recommendation_health,
        })
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500
