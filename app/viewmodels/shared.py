"""Shared viewmodel helpers — nav config, serialization, and context assembly.

Extracted from web_server.py and queue_viewmodel.py to eliminate duplication.
"""

from __future__ import annotations

NAV_ITEM_CONFIG = [
    ("inbox", "/", "Inbox", "tone-home"),
    ("queue", "/queue", "Queue", "tone-queue"),
    ("library", "/library", "Library", "tone-library"),
    ("monitor", "/monitor", "Monitor", "tone-monitor"),
    ("settings", "/settings", "Settings", "tone-settings"),
]


def build_nav_items():
    return [
        {"key": key, "href": href, "label": label, "tone": tone, "confirm": None}
        for key, href, label, tone in NAV_ITEM_CONFIG
    ]


def serialize_collection(collection):
    item = dict(collection)
    item["seed_query"] = item.get("query_text", "")
    return item


def serialize_saved_search(saved_search):
    item = dict(saved_search)
    filters = item.get("filters_json") or {}
    item["description"] = filters.get("description", "")
    item["subscription_type"] = "query"
    item["latest_hit_count"] = int(filters.get("latest_hit_count", 0) or 0)
    item["seed_query"] = item.get("query_text", "")
    return item


def serialize_job(job):
    if not job:
        return None
    return {
        "run_id": job.get("run_id"),
        "job_type": job.get("job_type"),
        "status": job.get("status"),
        "trigger_source": job.get("trigger_source"),
        "payload": job.get("payload_json", {}),
        "result": job.get("result_json", {}),
        "error_text": job.get("error_text"),
        "created_at": job.get("created_at"),
        "updated_at": job.get("updated_at"),
        "started_at": job.get("started_at"),
        "finished_at": job.get("finished_at"),
    }


def assemble_page_context(state_store, *, active_tab: str, feedback: dict | None = None):
    """Assemble the shared context used by every page."""
    if feedback is None:
        feedback = {"liked": [], "disliked": []}

    collections_raw = state_store.list_collections()
    collections = [serialize_collection(c) for c in collections_raw]
    saved_searches_raw = state_store.list_saved_searches()
    saved_searches = [serialize_saved_search(s) for s in saved_searches_raw]
    latest_job = serialize_job(state_store.get_latest_job("daily_recommendation"))

    liked_count = len(feedback.get("liked", []))
    nav_items = build_nav_items()

    return {
        "feedback": feedback,
        "liked_count": liked_count,
        "nav_items": nav_items,
        "collections": collections[:6],
        "all_collections": collections,
        "saved_searches": saved_searches[:6],
        "all_saved_searches": saved_searches,
        "latest_job": latest_job,
        "latest_job_tone": f"job-{latest_job.get('status')}" if latest_job else "job-idle",
        "recommendation_health": {},
    }
