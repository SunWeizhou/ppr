"""Onboarding wizard route for first-time user setup."""

from __future__ import annotations

from flask import Blueprint, render_template

from app.viewmodels.shared import build_nav_items

bp = Blueprint("onboarding", __name__)


def _safe_list_collections():
    try:
        from state_store import get_state_store
        from app.viewmodels.shared import serialize_collection

        store = get_state_store()
        return [serialize_collection(c) for c in store.list_collections()]
    except Exception:
        return []


def _safe_list_saved_searches():
    try:
        from state_store import get_state_store
        from app.viewmodels.shared import serialize_saved_search

        store = get_state_store()
        return [serialize_saved_search(s) for s in store.list_saved_searches()]
    except Exception:
        return []


def _safe_latest_job():
    try:
        from state_store import get_state_store
        from app.viewmodels.shared import serialize_job

        store = get_state_store()
        return serialize_job(store.get_latest_job("daily_recommendation"))
    except Exception:
        return None


def _safe_queue_counts():
    try:
        from state_store import get_state_store

        store = get_state_store()
        items = store.list_queue_items() or []
        counts: dict[str, int] = {}
        for item in items:
            status = item.get("status", "Inbox")
            counts[status] = counts.get(status, 0) + 1
        return counts
    except Exception:
        return {}


def _safe_liked_count():
    try:
        from app.services.feedback_service import FeedbackService
        from state_store import get_state_store

        store = get_state_store()
        feedback = FeedbackService(
            store,
            feedback_file="",
            favorites_file="",
            cache_file="",
            history_dir="",
            scholar_service=None,
            keywords_loader=lambda: {},
            keywords_saver=lambda _: None,
        ).load_feedback()
        return len(feedback.get("liked", []))
    except Exception:
        return 0


@bp.get("/onboarding")
def onboarding_page():
    collections = _safe_list_collections()
    saved_searches = _safe_list_saved_searches()
    latest_job = _safe_latest_job()
    queue_counts = _safe_queue_counts()
    liked_count = _safe_liked_count()

    return render_template(
        "onboarding.html",
        title="Setup - StatDesk",
        body_class="",
        nav_items=build_nav_items(),
        active_tab="",
        all_collections=collections,
        all_saved_searches=saved_searches,
        latest_job=latest_job,
        queue_counts=queue_counts,
        liked_count=liked_count,
        queue_status_values=[],
    )
