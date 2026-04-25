"""Queue page viewmodel boundary."""

from __future__ import annotations

from state_store import QUEUE_STATUS_VALUES


NAV_ITEM_CONFIG = [
    ("inbox", "/", "Inbox", "tone-home"),
    ("queue", "/queue", "Queue", "tone-queue"),
    ("library", "/library", "Library", "tone-library"),
    ("monitor", "/monitor", "Monitor", "tone-monitor"),
    ("settings", "/settings", "Settings", "tone-settings"),
]


def _serialize_collection(collection):
    item = dict(collection)
    item["seed_query"] = item.get("query_text", "")
    return item


def _serialize_saved_search(saved_search):
    item = dict(saved_search)
    filters = item.get("filters_json") or {}
    item["description"] = filters.get("description", "")
    item["subscription_type"] = "query"
    item["latest_hit_count"] = int(filters.get("latest_hit_count", 0) or 0)
    item["seed_query"] = item.get("query_text", "")
    return item


def _serialize_job(job):
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


class QueueViewModel:
    def __init__(self, queue_service, state_store):
        self.queue_service = queue_service
        self.state_store = state_store

    def _nav_items(self):
        return [
            {
                "key": key,
                "href": href,
                "label": label,
                "tone": tone,
                "confirm": None,
            }
            for key, href, label, tone in NAV_ITEM_CONFIG
        ]

    def to_template_context(self, *, active_status: str = "Inbox"):
        feedback = self.queue_service.load_feedback()
        collections = [_serialize_collection(item) for item in self.state_store.list_collections()]
        saved_searches = [_serialize_saved_search(item) for item in self.state_store.list_saved_searches()]
        latest_job = _serialize_job(self.state_store.get_latest_job("daily_recommendation"))
        queue_counts = self.queue_service.count_by_status()
        return {
            "title": "Queue - arXiv Recommender",
            "active_tab": "queue",
            "feedback": feedback,
            "liked_count": len(feedback.get("liked", [])),
            "nav_items": self._nav_items(),
            "queue_counts": queue_counts,
            "collections": collections[:6],
            "all_collections": collections,
            "saved_searches": saved_searches[:6],
            "all_saved_searches": saved_searches,
            "latest_job": latest_job,
            "latest_job_tone": f"job-{latest_job.get('status')}" if latest_job else "job-idle",
            "queue_status_values": QUEUE_STATUS_VALUES,
            "recommendation_health": {},
            "queue_items": self.queue_service.resolve_papers(status=active_status),
            "active_status": active_status,
        }
