"""Unified paper metadata resolution with configurable fallback chain.

Standard fallback: favorites → history → state_store → cache → placeholder.
Replaces duplicated ``_resolve_paper_record`` methods across services.
"""

from __future__ import annotations

from typing import Optional

from app.data._constants import canonical_paper_id as _canonical_paper_id


class PaperResolver:
    """Resolve paper metadata from multiple sources.

    Usage::

        resolver = PaperResolver(state_store)
        paper = resolver.resolve(paper_id, history_index=..., favorites=..., paper_cache=...)
    """

    def __init__(self, state_store):
        self._state_store = state_store

    def resolve(
        self,
        paper_id: str,
        *,
        history_index: Optional[dict] = None,
        favorites: Optional[dict] = None,
        paper_cache: Optional[dict] = None,
    ) -> dict:
        """Resolve paper metadata. Always returns a dict with at least ``id`` and ``title``."""
        paper_id = _canonical_paper_id(paper_id)

        # 1. Favorites
        if favorites and paper_id in favorites:
            return self._from_favorites(paper_id, favorites[paper_id])

        # 2. History index
        if history_index and paper_id in history_index:
            return self._from_history(paper_id, history_index[paper_id])

        # 3. StateStore paper metadata (missing from some older resolvers)
        metadata = self._state_store.get_paper_metadata(paper_id)
        if metadata:
            return self._from_metadata(paper_id, metadata)

        # 4. Paper cache file
        if paper_cache and paper_id in paper_cache:
            return self._from_cache(paper_id, paper_cache[paper_id])

        # 5. Fallback placeholder
        return self._placeholder(paper_id)

    # ── tier builders ─────────────────────────────────────────────────────

    @staticmethod
    def _from_favorites(paper_id: str, favorite: dict) -> dict:
        return {
            "id": paper_id,
            "title": favorite.get("title", f"Paper {paper_id}"),
            "link": favorite.get("link", f"https://arxiv.org/abs/{paper_id}"),
            "authors": favorite.get("authors", ""),
            "summary": favorite.get(
                "summary",
                favorite.get("abstract", "")[:300] if favorite.get("abstract") else "",
            ),
            "abstract": favorite.get("abstract", favorite.get("summary", "")),
            "relevance": favorite.get("relevance", "From your long-term collection"),
            "score": favorite.get("score", 0),
            "date": (favorite.get("date_published") or favorite.get("date_added") or "")[:10],
            "categories": favorite.get("categories", []),
            "source": "favorites",
        }

    @staticmethod
    def _from_history(paper_id: str, item: dict) -> dict:
        result = dict(item)
        result.setdefault("source", "history")
        result.setdefault("summary", result.get("abstract", ""))
        result.setdefault("abstract", result.get("summary", ""))
        result.setdefault("relevance", result.get("relevance_reason", result.get("relevance", "")))
        result["id"] = _canonical_paper_id(result.get("id", paper_id)) or paper_id
        return result

    def _from_metadata(self, paper_id: str, metadata: dict) -> dict:
        return {
            "id": paper_id,
            "title": metadata.get("title", f"Paper {paper_id}"),
            "link": metadata.get("link") or metadata.get("source_url") or f"https://arxiv.org/abs/{paper_id}",
            "authors": metadata.get("authors", []),
            "summary": metadata.get("summary") or metadata.get("abstract", ""),
            "abstract": metadata.get("abstract", metadata.get("summary", "")),
            "relevance": metadata.get("relevance_reason", metadata.get("relevance", "From workspace metadata")),
            "score": metadata.get("workspace_score", metadata.get("score", 0)),
            "date": (metadata.get("published_at") or metadata.get("published") or metadata.get("date") or "")[:10],
            "categories": metadata.get("categories", []),
            "source": "paper_metadata",
        }

    @staticmethod
    def _from_cache(paper_id: str, cached: dict) -> dict:
        info = dict(cached) if isinstance(cached, dict) else {}
        return {
            "id": paper_id,
            "title": info.get("title", f"Paper {paper_id}"),
            "link": f"https://arxiv.org/abs/{paper_id}",
            "authors": info.get("authors", "Author information unavailable"),
            "summary": info.get("summary", info.get("abstract", "")[:300] if info.get("abstract") else "Abstract unavailable"),
            "abstract": info.get("abstract", ""),
            "relevance": info.get("relevance", "From cache"),
            "score": info.get("score", 0),
            "date": str(info.get("date", ""))[:10],
            "categories": info.get("categories", []),
            "source": "paper_cache",
        }

    @staticmethod
    def _placeholder(paper_id: str) -> dict:
        return {
            "id": paper_id,
            "title": f"Paper {paper_id}",
            "link": f"https://arxiv.org/abs/{paper_id}",
            "authors": "Details unavailable",
            "summary": "Paper information not found in history or cache.",
            "abstract": "",
            "relevance": "View on arXiv",
            "score": 0,
            "date": "",
            "categories": [],
            "source": "placeholder",
        }
