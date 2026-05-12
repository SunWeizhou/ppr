"""Shared viewmodel helpers — nav config, serialization, and context assembly.

Extracted from web_server.py and queue_viewmodel.py to eliminate duplication.
"""

from __future__ import annotations

NAV_ITEM_CONFIG = [
    # Main section
    {"key": "search", "label": "Search", "href": "/", "icon": "search", "section": "main"},
    {"key": "recommendations", "label": "Recommendations", "href": "/recommendations", "icon": "star", "section": "main"},
    {"key": "watch", "label": "Watch", "href": "/watch", "icon": "eye", "section": "main"},
    {"key": "reading", "label": "Reading", "href": "/reading", "icon": "book", "section": "main"},
    # Subscriptions section
    {"key": "sub_journals", "label": "Journals", "href": "/watch?tab=journals", "icon": "journal", "section": "subscriptions"},
    {"key": "sub_conferences", "label": "Conferences", "href": "/watch?tab=conferences", "icon": "conference", "section": "subscriptions"},
    {"key": "sub_scholars", "label": "Scholars", "href": "/watch?tab=scholars", "icon": "scholar", "section": "subscriptions"},
    {"key": "sub_fields", "label": "Fields", "href": "/watch?tab=fields", "icon": "field", "section": "subscriptions"},
    # Footer section
    {"key": "settings", "label": "Settings", "href": "/settings", "icon": "settings", "section": "footer"},
]

# SVG icons for sidebar items
_ICON_SVG = {
    "search": '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="6.5" cy="6.5" r="4"/><path d="M11 11l3 3"/></svg>',
    "star": '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M8 2l1.5 3.5 3.5.5-2.5 2.5.5 3.5L8 10.5 5 12l.5-3.5L3 6l3.5-.5z"/></svg>',
    "eye": '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M1 8s2.5-5 7-5 7 5 7 5-2.5 5-7 5-7-5-7-5z"/><circle cx="8" cy="8" r="2"/></svg>',
    "book": '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M3 2h7a1 1 0 011 1v10a1 1 0 01-1 1H3V2z"/><path d="M10 2l2 1v11l-2-1"/></svg>',
    "journal": '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="2" y="2" width="12" height="12" rx="1"/><line x1="5" y1="6" x2="11" y2="6"/><line x1="5" y1="9" x2="9" y2="9"/></svg>',
    "conference": '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="2" y="4" width="12" height="9" rx="1"/><path d="M5 4V3a1 1 0 012 0v1M9 4V3a1 1 0 012 0v1"/></svg>',
    "scholar": '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="8" cy="5" r="3"/><path d="M2 14c0-3.3 2.7-6 6-6s6 2.7 6 6"/></svg>',
    "field": '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="8" cy="8" r="6"/><path d="M2 8h12M8 2a10 10 0 010 12M8 2a10 10 0 000 12"/></svg>',
    "settings": '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="8" cy="8" r="2.5"/><path d="M8 1v2M8 13v2M1 8h2M13 8h2M3.2 3.2l1.4 1.4M11.4 11.4l1.4 1.4M3.2 12.8l1.4-1.4M11.4 4.6l1.4-1.4"/></svg>',
    "moon": '<svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><path d="M11 1a7 7 0 000 14 7 7 0 000-14z" opacity=".3"/><path d="M11 0a8 8 0 100 16A8 8 0 0011 0zm0 14A6 6 0 1111 2a6 6 0 000 12z"/></svg>',
    "sun": '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="8" cy="8" r="3"/><line x1="8" y1="1" x2="8" y2="3"/><line x1="8" y1="13" x2="8" y2="15"/><line x1="1" y1="8" x2="3" y2="8"/><line x1="13" y1="8" x2="15" y2="8"/></svg>',
}


def build_nav_items(active_tab: str = ""):
    items = []
    for item in NAV_ITEM_CONFIG:
        items.append({
            "key": item["key"],
            "href": item["href"],
            "label": item["label"],
            "icon": item["icon"],
            "icon_svg": _ICON_SVG.get(item["icon"], ""),
            "section": item["section"],
            "active": item["key"] == active_tab,
            "count": None,
        })
    return items


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
    nav_items = build_nav_items(active_tab=active_tab)

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
