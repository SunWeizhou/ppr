"""Feedback service — likes, dislikes, favorites, paper cache, and feedback actions."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from state_store import _canonical_paper_id
from utils import CATEGORY_NAMES, atomic_write_json, safe_load_json

QUEUE_ACTIONS = {
    "inbox": "Inbox",
    "save_for_later": "Skim Later",
    "deep_read": "Deep Read",
    "save": "Saved",
    "archive": "Archived",
}


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
    ):
        self.state_store = state_store
        self.feedback_file = Path(feedback_file)
        self.favorites_file = Path(favorites_file)
        self.cache_file = Path(cache_file)
        self.history_dir = Path(history_dir)
        self._scholar_service = scholar_service
        self._keywords_loader = keywords_loader
        self._keywords_saver = keywords_saver

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
            papers = self._parse_markdown_digest(str(filepath))
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

    @staticmethod
    def _parse_markdown_digest(filepath: str) -> list:
        papers = []
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
        except OSError:
            return papers
        for section in re.split(r"## \d+\.\s*", content)[1:]:
            lines = [line.strip() for line in section.strip().splitlines() if line.strip()]
            if not lines:
                continue
            paper = {"title": lines[0]}
            for line in lines[1:]:
                if line.startswith("**Authors:**"):
                    paper["authors"] = line.replace("**Authors:**", "").strip()
                elif line.startswith("**arXiv:**") or line.startswith("**arXiv Link:**"):
                    match = re.search(r"\[([^\]]+)\]\(([^)]+)\)", line)
                    if match:
                        paper["id"] = match.group(1)
                        paper["link"] = match.group(2)
                elif line.startswith("**Summary:**"):
                    paper["summary"] = line.replace("**Summary:**", "").strip()
                    paper["abstract"] = paper["summary"]
                elif line.startswith("**Relevance:**"):
                    paper["relevance"] = line.replace("**Relevance:**", "").strip()
                elif line.startswith("**Score:**"):
                    try:
                        paper["score"] = float(line.replace("**Score:**", "").strip())
                    except ValueError:
                        paper["score"] = 0
            if paper.get("id"):
                papers.append(paper)
        return papers

    # ---- handle_feedback action handler ----

    def handle_feedback(self, data: dict) -> tuple[dict, int]:
        paper_id = _canonical_paper_id(data.get("paper_id", ""))
        action = data.get("action")
        paper_title = data.get("title", "")
        paper_abstract = data.get("abstract", "")
        paper_authors = data.get("authors", "")
        paper_score = data.get("score", 0)
        paper_relevance = data.get("relevance", "")
        source = data.get("source", "web_feedback")

        if not action:
            return {"success": False, "error": "Missing action"}, 400
        if action != "ignore_topic" and not paper_id:
            return {"success": False, "error": "Missing paper_id"}, 400

        event_payload = {"title": paper_title, "authors": paper_authors, "score": paper_score, "relevance": paper_relevance, "source": source}

        feedback = self.load_feedback()
        event_id = None

        if action == "like":
            if paper_id not in feedback["liked"]:
                feedback["liked"].append(paper_id)
            if paper_id in feedback.get("disliked", []):
                feedback["disliked"].remove(paper_id)
            self.save_paper_to_cache(paper_id, paper_title, paper_abstract)
            paper_info = {
                "id": paper_id, "title": paper_title, "authors": paper_authors,
                "abstract": paper_abstract,
                "summary": paper_abstract[:300] + "..." if len(paper_abstract) > 300 else paper_abstract,
                "link": f"https://arxiv.org/abs/{paper_id}", "score": paper_score,
                "relevance": paper_relevance, "date": datetime.now().strftime("%Y-%m-%d"),
            }
            full_info = self.find_paper_in_history(paper_id)
            if full_info:
                paper_info.update(full_info)
            self.add_to_favorites(paper_id, paper_info)
            event_id = self.state_store.record_event("like", paper_id, event_payload)

        elif action == "dislike":
            if paper_id not in feedback.get("disliked", []):
                feedback.setdefault("disliked", []).append(paper_id)
            if paper_id in feedback["liked"]:
                feedback["liked"].remove(paper_id)
            self.remove_from_favorites(paper_id)
            event_id = self.state_store.record_event("dislike", paper_id, event_payload)

        elif action in QUEUE_ACTIONS:
            queue_item = self.state_store.upsert_queue_item(paper_id, QUEUE_ACTIONS[action], source=source, note=data.get("note", ""), tags=data.get("tags"))
            event_id = self.state_store.record_event(action, paper_id, event_payload)
            # Record additional semantic events for analytics
            if action == "save_for_later":
                self.state_store.record_event("paper_skimmed", paper_id, {**event_payload, "parent_action": action})
            elif action == "deep_read":
                self.state_store.record_event("paper_deep_read", paper_id, {**event_payload, "parent_action": action})
            return {"success": True, "queue_item": queue_item, "event_id": event_id}, 200

        elif action in {"open_paper", "impression", "export_to_zotero"}:
            event_id = self.state_store.record_event(action, paper_id, event_payload)
            return {"success": True, "event_id": event_id}, 200

        elif action == "follow_author":
            author_name = str(data.get("author", "")).strip()
            if not author_name:
                return {"success": False, "error": "Missing author"}, 400
            if self._scholar_service:
                success, result = self._scholar_service.add(name=author_name, focus=data.get("focus", ""))
            else:
                import urllib.parse

                from app.services.scholar_service import ScholarService

                svc = ScholarService(str(self.history_dir.parent / "my_scholars.json"))
                success, result = svc.add(name=author_name, focus=data.get("focus", ""))
            event_id = self.state_store.record_event("follow_author", paper_id, {**event_payload, "author": author_name})
            return {"success": True, "followed": success, "author": author_name, "result": result if success else str(result), "event_id": event_id}, 200

        elif action == "ignore_topic":
            topic = str(data.get("topic", "")).strip().lower()
            if not topic:
                return {"success": False, "error": "Missing topic"}, 400
            if self._keywords_loader and self._keywords_saver:
                config = self._keywords_loader()
                dislike_topics = config.get("dislike_topics", {})
                if isinstance(dislike_topics, list):
                    dislike_topics = {item: -1.0 for item in dislike_topics}
                dislike_topics[topic] = -1.0
                config["dislike_topics"] = dislike_topics
                self._keywords_saver(config)
            event_id = self.state_store.record_event("ignore_topic", paper_id, {**event_payload, "topic": topic})
            return {"success": True, "topic": topic, "event_id": event_id}, 200

        else:
            return {"success": False, "error": f"Unsupported action: {action}"}, 400

        self.save_feedback(feedback)
        return {"success": True, "feedback": feedback, "event_id": event_id}, 200
