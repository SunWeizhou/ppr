"""Queue service for reading workflow state and page data."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

from app_paths import CACHE_DIR, HISTORY_DIR
from app.services.paper_utils import (
    category_labels,
    extract_primary_author as _extract_primary_author,
    format_author_text as _format_author_text,
    generate_relevance_html as _generate_relevance_html,
    normalize_queue_status as _normalize_queue_status,
    status_class as _status_class,
)
from state_store import QUEUE_STATUS_VALUES, _canonical_paper_id


def _safe_load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


class QueueService:
    """Own queue business logic independently from Flask route handlers."""

    def __init__(self, state_store, *, cache_dir: Path | str = CACHE_DIR, history_dir: Path | str = HISTORY_DIR):
        self.state_store = state_store
        self.cache_dir = Path(cache_dir)
        self.history_dir = Path(history_dir)

    def list_items(self, status: Optional[str] = None):
        if status and status not in QUEUE_STATUS_VALUES:
            raise ValueError(f"Invalid queue status: {status}")
        return self.state_store.list_queue_items(status=status)

    def update_item(self, paper_id: str, status: str, *, source: str = "queue_service", note=None, tags=None):
        canonical_id = _canonical_paper_id(paper_id)
        if not canonical_id:
            raise ValueError("Missing paper_id")
        if status not in QUEUE_STATUS_VALUES:
            raise ValueError(f"Invalid queue status: {status}")

        existing = self.state_store.get_queue_item(canonical_id)
        if note is None and existing:
            note = existing.get("note", "")
        if tags is None and existing:
            tags = existing.get("tags_json")
        return self.state_store.upsert_queue_item(
            canonical_id,
            status,
            source=source,
            note=note or "",
            tags=tags,
        )

    def update_status(self, paper_id: str, status: str, *, source: str = "queue_api", note=None, tags=None):
        item = self.update_item(paper_id, status, source=source, note=note, tags=tags)
        event_id = self.state_store.record_event(
            "queue_status_changed",
            item["paper_id"],
            {"status": status, "source": source, "note": item.get("note", "")},
        )
        return item, event_id

    def bulk_update(self, paper_ids, status: str, *, source: str = "queue_service", note: str = ""):
        return [
            self.update_item(paper_id, status, source=source, note=note)
            for paper_id in paper_ids
        ]

    def bulk_update_status(self, paper_ids, status: str, *, source: str = "queue_bulk", note: str = ""):
        canonical_ids = [_canonical_paper_id(item) for item in paper_ids if str(item).strip()]
        if not canonical_ids or not status:
            raise ValueError("Missing paper_ids or status")
        if status not in QUEUE_STATUS_VALUES:
            raise ValueError(f"Invalid queue status: {status}")
        updated = []
        for paper_id in canonical_ids:
            item, _ = self.update_status(paper_id, status, source=source, note=note)
            updated.append(item)
        return updated

    def count_by_status(self):
        counts = {status: 0 for status in QUEUE_STATUS_VALUES}
        for item in self.state_store.list_queue_items():
            status = item.get("status")
            if status in counts:
                counts[status] += 1
        return counts

    def load_feedback(self):
        feedback = _safe_load_json(self.cache_dir / "user_feedback.json", {"liked": [], "disliked": []})
        liked = {_canonical_paper_id(item) for item in feedback.get("liked", [])}
        disliked = {_canonical_paper_id(item) for item in feedback.get("disliked", [])}
        return {
            "liked": [item for item in liked if item],
            "disliked": [item for item in disliked if item and item not in liked],
        }

    def _load_favorites(self):
        raw = _safe_load_json(self.cache_dir / "favorite_papers.json", {})
        favorites = {}
        if not isinstance(raw, dict):
            return favorites
        for paper_id, info in raw.items():
            canonical = _canonical_paper_id(paper_id)
            if canonical:
                favorites[canonical] = dict(info) if isinstance(info, dict) else {}
        return favorites

    def _load_paper_cache(self):
        raw = _safe_load_json(self.cache_dir / "paper_cache.json", {})
        paper_cache = {}
        if not isinstance(raw, dict):
            return paper_cache
        for paper_id, info in raw.items():
            canonical = _canonical_paper_id(paper_id)
            if canonical:
                paper_cache[canonical] = dict(info) if isinstance(info, dict) else {}
        return paper_cache

    def _available_history_dates(self):
        if not self.history_dir.exists():
            return []
        dates = []
        for path in self.history_dir.glob("digest_*.md"):
            match = re.search(r"digest_(\d{4}-\d{2}-\d{2})", path.name)
            if match:
                dates.append(match.group(1))
        return sorted(dates, reverse=True)

    def _parse_history_digest(self, path: Path):
        content = path.read_text(encoding="utf-8")
        papers = []
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
                        paper["id"] = _canonical_paper_id(match.group(1))
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

    def _load_history_paper_index(self):
        index = {}
        for date in self._available_history_dates():
            path = self.history_dir / f"digest_{date}.md"
            try:
                papers = self._parse_history_digest(path)
            except OSError:
                continue
            for paper in papers:
                paper_id = paper.get("id")
                if paper_id and paper_id not in index:
                    item = dict(paper)
                    item["date"] = date
                    index[paper_id] = item
        return index

    def _resolve_paper_record(self, paper_id, *, history_index, favorites, paper_cache):
        paper_id = _canonical_paper_id(paper_id)
        if paper_id in favorites:
            favorite = favorites[paper_id]
            return {
                "id": paper_id,
                "title": favorite.get("title", f"论文 {paper_id}"),
                "link": favorite.get("link", f"https://arxiv.org/abs/{paper_id}"),
                "authors": favorite.get("authors", ""),
                "summary": favorite.get("summary", favorite.get("abstract", "")[:300] if favorite.get("abstract") else ""),
                "abstract": favorite.get("abstract", favorite.get("summary", "")),
                "relevance": favorite.get("relevance", "来自你的长期收藏"),
                "score": favorite.get("score", 0),
                "date": (favorite.get("date_published") or favorite.get("date_added") or "")[:10],
                "categories": favorite.get("categories", []),
                "source": "favorites",
            }
        if paper_id in history_index:
            item = dict(history_index[paper_id])
            item.setdefault("source", "history")
            item.setdefault("summary", item.get("abstract", ""))
            item.setdefault("abstract", item.get("summary", ""))
            item.setdefault("relevance", item.get("relevance_reason", item.get("relevance", "")))
            return item
        if paper_id in paper_cache:
            cached = paper_cache[paper_id]
            return {
                "id": paper_id,
                "title": cached.get("title", f"论文 {paper_id}"),
                "link": f"https://arxiv.org/abs/{paper_id}",
                "authors": cached.get("authors", "作者信息不可用"),
                "summary": cached.get("abstract", "摘要不可用"),
                "abstract": cached.get("abstract", ""),
                "relevance": cached.get("relevance", "来自缓存"),
                "score": cached.get("score", 0),
                "date": cached.get("date", ""),
                "categories": cached.get("categories", []),
                "source": "paper_cache",
            }
        return {
            "id": paper_id,
            "title": f"论文 {paper_id}",
            "link": f"https://arxiv.org/abs/{paper_id}",
            "authors": "详情不可用",
            "summary": "此论文信息暂时不在历史记录或缓存中，可按需补全。",
            "abstract": "",
            "relevance": "点击查看 arXiv 页面",
            "score": 0,
            "date": "",
            "categories": [],
            "source": "placeholder",
        }

    def _decorate_papers(self, papers, feedback, *, queue_overrides=None):
        queue_map = {
            item.get("paper_id"): _normalize_queue_status(item.get("status"))
            for item in self.state_store.list_queue_items()
        }
        if queue_overrides:
            queue_map.update(queue_overrides)

        decorated = []
        for idx, paper in enumerate(papers, start=1):
            item = dict(paper)
            item["rank"] = idx
            item["author_text"] = _format_author_text(item.get("authors"))
            item["first_author"] = _extract_primary_author(item.get("authors"))
            item["queue_status"] = queue_map.get(item.get("id"))
            item["queue_status_class"] = _status_class(item["queue_status"])
            item["relevance_html"] = _generate_relevance_html(item)
            item["is_incomplete"] = not item.get("score")
            item["is_liked"] = item.get("id") in feedback.get("liked", [])
            item["is_disliked"] = item.get("id") in feedback.get("disliked", [])
            item["category_labels"] = category_labels(item.get("categories", []))
            item["summary_short"] = (item.get("summary") or item.get("abstract") or "")[:220]
            decorated.append(item)
        return decorated

    def get_todays_reading_plan(self) -> dict:
        """Return today's reading plan: top Deep Read and Skim Later papers.

        Each paper is resolved against the history index, favorites, and
        paper cache so the template gets title, authors, score, etc.
        """
        from datetime import datetime

        from app.services.paper_utils import format_author_text as _fmt_authors

        today = datetime.now().strftime("%Y-%m-%d")
        all_items = self.list_items()
        today_items = [
            item
            for item in all_items
            if (item.get("updated_at") or "").startswith(today)
            and item.get("status") in ("Deep Read", "Skim Later")
        ]

        history_index = self._load_history_paper_index()
        favorites = self._load_favorites()
        paper_cache = self._load_paper_cache()

        deep_read: list = []
        skim_later: list = []

        for item in today_items:
            paper = self._resolve_paper_record(
                item.get("paper_id"),
                history_index=history_index,
                favorites=favorites,
                paper_cache=paper_cache,
            )
            paper["queue_status"] = item.get("status")
            paper["updated_at"] = item.get("updated_at", "")
            paper["queue_note"] = item.get("note", "")
            if item.get("status") == "Deep Read":
                deep_read.append(paper)
            else:
                skim_later.append(paper)

        # Sort by time added (most recent first)
        deep_read.sort(key=lambda p: p.get("updated_at", ""), reverse=True)
        skim_later.sort(key=lambda p: p.get("updated_at", ""), reverse=True)

        # Decorate with author formatting and short summary, then limit
        for paper in deep_read[:3] + skim_later[:5]:
            paper["author_text"] = _fmt_authors(paper.get("authors"))
            paper["summary_short"] = (paper.get("summary") or paper.get("abstract") or "")[:220]

        return {
            "deep_read": deep_read[:3],
            "skim_later": skim_later[:5],
        }

    def resolve_papers(self, status: Optional[str] = None):
        feedback = self.load_feedback()
        history_index = self._load_history_paper_index()
        favorites = self._load_favorites()
        paper_cache = self._load_paper_cache()
        resolved = []
        for item in self.list_items(status=status):
            queue_status = _normalize_queue_status(item.get("status"))
            paper = self._resolve_paper_record(
                item.get("paper_id"),
                history_index=history_index,
                favorites=favorites,
                paper_cache=paper_cache,
            )
            paper["queue_status"] = queue_status
            paper["queue_status_class"] = _status_class(queue_status)
            paper["queue_note"] = item.get("note", "")
            paper["queue_tags"] = item.get("tags_json", [])
            paper["queue_source"] = item.get("source", "")
            paper["updated_at"] = item.get("updated_at", "")
            resolved.append(paper)
        return self._decorate_papers(
            resolved,
            feedback,
            queue_overrides={paper["id"]: paper["queue_status"] for paper in resolved},
        )
