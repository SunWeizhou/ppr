"""Feedback service — likes, dislikes, favorites, paper cache, and feedback actions."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from app.data._constants import canonical_paper_id as _canonical_paper_id
from utils import CATEGORY_NAMES, atomic_write_json, parse_markdown_digest, safe_load_json

QUEUE_ACTIONS = {
    "inbox": "Inbox",
    "save": "Inbox",
    "save_for_later": "Inbox",
    "deep_read": "Inbox",
}


# ---------------------------------------------------------------------------
# Standalone helpers (moved from arxiv_recommender_v5)
# ---------------------------------------------------------------------------


def load_user_feedback(cache_dir: str) -> Dict:
    """Load user feedback from file."""
    feedback_file = os.path.join(cache_dir, 'user_feedback.json')
    if os.path.exists(feedback_file):
        try:
            with open(feedback_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {'liked': [], 'disliked': [], 'topic_adjustments': {}}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _canonicalize_feedback(feedback: dict) -> dict:
    if not isinstance(feedback, dict):
        feedback = {}
    liked = _unique_canonical_ids(feedback.get("liked", []))
    disliked = [pid for pid in _unique_canonical_ids(feedback.get("disliked", [])) if pid not in set(liked)]
    normalized = dict(feedback)
    normalized["liked"] = liked
    normalized["disliked"] = disliked
    return normalized


def _canonicalize_favorites(favorites: dict) -> dict:
    if not isinstance(favorites, dict):
        return {}
    normalized = {}
    for raw_id, paper_info in favorites.items():
        canonical = _canonical_paper_id(raw_id)
        if not canonical:
            continue
        info = dict(paper_info) if isinstance(paper_info, dict) else {}
        existing = normalized.get(canonical, {})
        merged = {**info, **existing} if existing else info
        merged["id"] = canonical
        merged["link"] = merged.get("link") or f"https://arxiv.org/abs/{canonical}"
        normalized[canonical] = merged
    return normalized


def _unique_canonical_ids(values) -> list:
    seen = set()
    result = []
    for value in values or []:
        canonical = _canonical_paper_id(value)
        if canonical and canonical not in seen:
            seen.add(canonical)
            result.append(canonical)
    return result


# ---------------------------------------------------------------------------
# Handler registry for feedback actions (strategy pattern)
# ---------------------------------------------------------------------------

_HANDLERS: dict[str, callable] = {}


def _register(action: str):
    """Decorator: register a function as the handler for *action*."""
    def wrapper(func):
        _HANDLERS[action] = func
        return func
    return wrapper


@_register("like")
def _handle_like(service, data, event_payload):
    paper_id = _canonical_paper_id(data.get("paper_id", ""))
    feedback = service.load_feedback()
    if paper_id not in feedback["liked"]:
        feedback["liked"].append(paper_id)
    if paper_id in feedback.get("disliked", []):
        feedback["disliked"].remove(paper_id)

    paper_title = data.get("title", "")
    paper_abstract = data.get("abstract", "")
    paper_authors = data.get("authors", "")
    paper_score = data.get("score", 0)
    paper_relevance = data.get("relevance", "")
    service.save_paper_to_cache(paper_id, paper_title, paper_abstract)
    paper_info = {
        "id": paper_id, "title": paper_title, "authors": paper_authors,
        "abstract": paper_abstract,
        "summary": paper_abstract[:300] + "..." if len(paper_abstract) > 300 else paper_abstract,
        "link": f"https://arxiv.org/abs/{paper_id}", "score": paper_score,
        "relevance": paper_relevance, "date": datetime.now().strftime("%Y-%m-%d"),
    }
    full_info = service.find_paper_in_history(paper_id)
    if full_info:
        paper_info.update(full_info)
    service.add_to_favorites(paper_id, paper_info)
    event_id = service.state_store.record_event("like", paper_id, event_payload)
    service.save_feedback(feedback)
    return {"success": True, "feedback": feedback, "event_id": event_id}, 200


@_register("dislike")
def _handle_dislike(service, data, event_payload):
    paper_id = _canonical_paper_id(data.get("paper_id", ""))
    feedback = service.load_feedback()
    if paper_id not in feedback.get("disliked", []):
        feedback.setdefault("disliked", []).append(paper_id)
    if paper_id in feedback["liked"]:
        feedback["liked"].remove(paper_id)
    service.remove_from_favorites(paper_id)
    event_id = service.state_store.record_event("dislike", paper_id, event_payload)
    service.save_feedback(feedback)
    return {"success": True, "feedback": feedback, "event_id": event_id}, 200


@_register("finish")
def _handle_finish(service, data, event_payload):
    paper_id = _canonical_paper_id(data.get("paper_id", ""))
    if service._queue is not None:
        item = service._queue.mark_paper_as_read(
            paper_id,
            research_question_id=data.get("research_question_id"),
            source=data.get("source", "web_feedback"),
        )
        event_id = service.state_store.record_event("finish", paper_id, event_payload)
    else:
        item = service.state_store.mark_as_completed(
            paper_id, source=data.get("source", "web_feedback"),
        )
        event_id = service.state_store.record_event("finish", paper_id, event_payload)
    return {"success": True, "queue_item": item, "event_id": event_id}, 200


def _handle_queue_action(service, data, event_payload):
    paper_id = _canonical_paper_id(data.get("paper_id", ""))
    action = data.get("action", "inbox")
    source = data.get("source", "web_feedback")
    status = QUEUE_ACTIONS[action]

    if service._queue is not None:
        queue_item, event_id = service._queue.update_status(
            paper_id, status, source=source,
            note=data.get("note", ""), tags=data.get("tags"),
        )
    else:
        queue_item = service.state_store.upsert_queue_item(
            paper_id, status,
            source=source, note=data.get("note", ""), tags=data.get("tags"),
        )
        event_id = service.state_store.record_event(action, paper_id, event_payload)
    return {"success": True, "queue_item": queue_item, "event_id": event_id}, 200


for _action in QUEUE_ACTIONS:
    _HANDLERS[_action] = _handle_queue_action


def _handle_event_only(service, data, event_payload):
    paper_id = _canonical_paper_id(data.get("paper_id", ""))
    event_id = service.state_store.record_event(
        data.get("action"), paper_id, event_payload,
    )
    return {"success": True, "event_id": event_id}, 200


for _action in ("open_paper", "impression", "export_to_zotero"):
    _HANDLERS[_action] = _handle_event_only


@_register("follow_author")
def _handle_follow_author(service, data, event_payload):
    paper_id = _canonical_paper_id(data.get("paper_id", ""))
    author_name = str(data.get("author", "")).strip()
    if not author_name:
        return {"success": False, "error": "Missing author"}, 400
    if service._scholar_service:
        success, result = service._scholar_service.add(
            name=author_name, focus=data.get("focus", ""),
        )
    else:
        # TODO: migrate ScholarService to use subscriptions(type='author')
        from app.services.scholar_service import ScholarService

        svc = ScholarService(str(service.history_dir.parent / "my_scholars.json"))
        success, result = svc.add(name=author_name, focus=data.get("focus", ""))
    event_id = service.state_store.record_event(
        "follow_author", paper_id, {**event_payload, "author": author_name},
    )
    return {
        "success": True, "followed": success, "author": author_name,
        "result": result if success else str(result), "event_id": event_id,
    }, 200


@_register("ignore_topic")
def _handle_ignore_topic(service, data, event_payload):
    paper_id = _canonical_paper_id(data.get("paper_id", ""))
    topic = str(data.get("topic", "")).strip().lower()
    if not topic:
        return {"success": False, "error": "Missing topic"}, 400
    if service._keywords_loader and service._keywords_saver:
        config = service._keywords_loader()
        dislike_topics = config.get("dislike_topics", {})
        if isinstance(dislike_topics, list):
            dislike_topics = {item: -1.0 for item in dislike_topics}
        dislike_topics[topic] = -1.0
        config["dislike_topics"] = dislike_topics
        service._keywords_saver(config)
    event_id = service.state_store.record_event(
        "ignore_topic", paper_id, {**event_payload, "topic": topic},
    )
    return {"success": True, "topic": topic, "event_id": event_id}, 200


class FeedbackService:
    def __init__(
        self,
        state_store,
        *,
        feedback_file: str,
        favorites_file: str,
        cache_file: str,
        history_dir: str,
        scholar_service=None,
        keywords_loader=None,
        keywords_saver=None,
        queue_service=None,
    ):
        self.state_store = state_store
        self.feedback_file = Path(feedback_file)
        self.favorites_file = Path(favorites_file)
        self.cache_file = Path(cache_file)
        self.history_dir = Path(history_dir)
        self._scholar_service = scholar_service
        self._keywords_loader = keywords_loader
        self._keywords_saver = keywords_saver
        self._queue = queue_service

    # ---- feedback ----

    def load_feedback(self) -> dict:
        feedback = safe_load_json(str(self.feedback_file), {"liked": [], "disliked": []})
        normalized = _canonicalize_feedback(feedback)
        if normalized != feedback:
            atomic_write_json(str(self.feedback_file), normalized)
        return normalized

    def save_feedback(self, feedback: dict) -> None:
        feedback = _canonicalize_feedback(feedback)
        atomic_write_json(str(self.feedback_file), feedback)

    # ---- favorites ----

    def load_favorites(self) -> dict:
        favorites = safe_load_json(str(self.favorites_file), {})
        normalized = _canonicalize_favorites(favorites)
        if normalized != favorites:
            atomic_write_json(str(self.favorites_file), normalized)
        return normalized

    def save_favorites(self, favorites: dict) -> None:
        favorites = _canonicalize_favorites(favorites)
        atomic_write_json(str(self.favorites_file), favorites)

    def add_to_favorites(self, paper_id: str, paper_info: dict) -> dict:
        paper_id = _canonical_paper_id(paper_id)
        favorites = self.load_favorites()
        favorites[paper_id] = {
            "id": paper_id,
            "title": paper_info.get("title", ""),
            "authors": paper_info.get("authors", ""),
            "abstract": paper_info.get("abstract", ""),
            "summary": paper_info.get("summary", ""),
            "link": paper_info.get("link", f"https://arxiv.org/abs/{paper_id}"),
            "score": paper_info.get("score", 0),
            "relevance": paper_info.get("relevance", ""),
            "categories": paper_info.get("categories", []),
            "date_added": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "date_published": paper_info.get("date", ""),
        }
        self.save_favorites(favorites)
        return favorites[paper_id]

    def remove_from_favorites(self, paper_id: str) -> None:
        paper_id = _canonical_paper_id(paper_id)
        favorites = self.load_favorites()
        if paper_id in favorites:
            del favorites[paper_id]
            self.save_favorites(favorites)

    # ---- paper cache ----

    def save_paper_to_cache(self, paper_id: str, title: str, abstract: str) -> None:
        paper_id = _canonical_paper_id(paper_id)
        paper_cache = safe_load_json(str(self.cache_file), {})
        if isinstance(paper_cache, dict):
            normalized = {}
            for raw_id, info in paper_cache.items():
                canonical = _canonical_paper_id(raw_id)
                if canonical:
                    normalized[canonical] = info
            paper_cache = normalized
        for k, v in list(paper_cache.items()):
            if not isinstance(v, dict):
                paper_cache[k] = {"title": "", "abstract": "", "date": v if isinstance(v, str) else datetime.now().strftime("%Y-%m-%d"), "score": 0}
        existing = paper_cache.get(paper_id, {})
        if isinstance(existing, dict) and existing.get("score", 0) > 0:
            paper_cache[paper_id]["date"] = datetime.now().strftime("%Y-%m-%d")
        else:
            full_info = self.find_paper_in_history(paper_id)
            if full_info:
                paper_cache[paper_id] = full_info
            else:
                paper_cache[paper_id] = {"title": title, "abstract": abstract, "date": datetime.now().strftime("%Y-%m-%d"), "score": 0}
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(str(self.cache_file), paper_cache)

    def find_paper_in_history(self, paper_id: str) -> Optional[dict]:
        from app.services.paper_utils import breakdown_from_text

        paper_id = _canonical_paper_id(paper_id)
        dates = self._available_history_dates()
        for date in dates:
            filepath = self.history_dir / f"digest_{date}.md"
            if not filepath.exists():
                continue
            papers, _ = parse_markdown_digest(str(filepath))
            for paper in papers:
                if _canonical_paper_id(paper.get("id")) == paper_id:
                    return {
                        "title": paper.get("title", ""),
                        "abstract": paper.get("summary", ""),
                        "authors": paper.get("authors", ""),
                        "date": date,
                        "score": paper.get("score", 0),
                        "relevance": paper.get("relevance", ""),
                    }
        return None

    def _available_history_dates(self) -> list:
        if not self.history_dir.exists():
            return []
        dates = []
        for path in self.history_dir.glob("digest_*.md"):
            match = re.search(r"digest_(\d{4}-\d{2}-\d{2})", path.name)
            if match:
                dates.append(match.group(1))
        return sorted(dates, reverse=True)

    # ---- handle_feedback action handler -- strategy pattern ----------------

    def handle_feedback(self, data: dict) -> tuple[dict, int]:
        action = data.get("action")
        if not action:
            return {"success": False, "error": "Missing action"}, 400

        handler = _HANDLERS.get(action)
        if handler is None:
            return {"success": False, "error": f"Unsupported action: {action}"}, 400

        paper_id = _canonical_paper_id(data.get("paper_id", ""))
        if action != "ignore_topic" and not paper_id:
            return {"success": False, "error": "Missing paper_id"}, 400

        event_payload = {
            "title": data.get("title", ""),
            "authors": data.get("authors", ""),
            "score": data.get("score", 0),
            "relevance": data.get("relevance", ""),
            "source": data.get("source", "web_feedback"),
        }

        return handler(self, data, event_payload)


__all__ = ["load_user_feedback", "FeedbackService", "_canonicalize_feedback", "_canonicalize_favorites"]
