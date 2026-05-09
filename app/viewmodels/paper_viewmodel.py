"""Paper detail viewmodel — builds context for the paper detail page."""
from __future__ import annotations
import json
from datetime import datetime
from typing import Optional
from logger_config import get_logger
from app_paths import CACHE_DIR, HISTORY_DIR
from app.services.paper_utils import format_author_text, extract_primary_author
from utils import CATEGORY_NAMES

logger = get_logger(__name__)


def _format_event(event: dict) -> dict:
    """Convert a raw interaction_event row into a dict with display_* keys."""
    event_type = event.get("event_type", "")
    payload = event.get("payload_json", {})
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except (TypeError, json.JSONDecodeError):
            payload = {}

    created_at = event.get("created_at", "")
    display_time = ""
    if created_at:
        try:
            dt = datetime.fromisoformat(created_at)
            display_time = dt.strftime("%b %d, %H:%M")
        except (ValueError, TypeError):
            display_time = created_at

    label_map = {
        "queue_status_changed": {
            "Deep Read": "Marked for Deep Reading",
            "Skim Later": "Marked to Skim",
            "Saved": "Saved",
        },
        "feedback_relevant": "Marked as Relevant",
        "feedback_ignored": "Ignored",
        "paper_opened": "Opened on arXiv",
        "export_to_zotero": "Exported to Zotero",
    }

    if event_type == "queue_status_changed":
        status = payload.get("status", "")
        label = label_map["queue_status_changed"].get(status, f"Status: {status}")
    else:
        label = label_map.get(event_type, event_type)

    return {
        "display_label": label,
        "display_detail": "",
        "display_time": display_time,
    }


class PaperViewModel:
    """Build template context for the paper detail page."""

    def __init__(self, state_store):
        self._store = state_store

    # TODO: Extract data-enrichment blocks (related papers, subscription matches,
    # interaction history, queue status, collections) into a PaperDetailService
    # once the viewmodel grows more complex or needs reuse beyond this view.

    def to_detail_context(self, paper_id: str, research_question_id: int | None = None) -> dict:
        """Build the full detail context for a paper."""
        from state_store import _canonical_paper_id
        paper_id = _canonical_paper_id(paper_id)

        # Build page context first — needed by both the error and success paths
        from app.viewmodels.shared import assemble_page_context
        from state_store import QUEUE_STATUS_VALUES

        page_ctx = assemble_page_context(self._store, active_tab="inbox")
        try:
            queue_counts = {status: 0 for status in QUEUE_STATUS_VALUES}
            for item in self._store.list_queue_items():
                status = item.get("status")
                if status in queue_counts:
                    queue_counts[status] += 1
        except Exception:
            queue_counts = {}
        page_ctx.setdefault("queue_counts", queue_counts)
        page_ctx.setdefault("queue_status_values", QUEUE_STATUS_VALUES)

        paper_data = self._find_paper_data(paper_id)
        if not paper_data:
            return {"title": "Paper Not Found - arXiv Recommender", "error": "Paper not found", "paper_id": paper_id, **page_ctx}

        paper = dict(paper_data)
        paper["id"] = paper_id

        # Basic formatting
        paper["author_text"] = format_author_text(paper.get("authors"), limit=6)
        paper["first_author"] = extract_primary_author(paper.get("authors"))
        paper["category_labels"] = [
            CATEGORY_NAMES.get(cat, cat) for cat in paper.get("categories", [])[:6]
        ]

        # AI analysis
        analysis = self._store.get_paper_ai_analysis(paper_id) if hasattr(self._store, 'get_paper_ai_analysis') else None

        # Workspace context & evidence claims
        queue_item = self._store.get_queue_item(paper_id)
        active_question_id = self._resolve_active_research_question_id(
            research_question_id,
            queue_item,
            analysis,
        )
        active_question = (
            self._store.get_research_question(active_question_id)
            if active_question_id is not None
            else None
        )
        evidence_claims = self._load_evidence_claims(
            paper_id,
            analysis=analysis,
            research_question_id=active_question_id,
        )
        paper["ai_analysis"] = analysis
        paper["evidence_claims"] = evidence_claims
        paper["evidence_summary"] = self._build_evidence_summary(evidence_claims)
        paper["active_research_question"] = active_question
        paper["active_research_question_id"] = active_question_id
        paper["decision_context"] = (queue_item or {}).get("decision_context", "")
        paper["workspace_context"] = {
            "active_research_question_id": active_question_id,
            "active_research_question": active_question,
            "decision_context": paper["decision_context"],
            "source": "url" if research_question_id is not None else ("queue" if queue_item else ""),
        }

        # Related papers — find papers with similar categories from recent runs
        try:
            related = []
            runs = self._store.list_recommendation_runs(limit=5)
            paper_cats = set(paper.get("categories", []))
            for run in runs:
                items = self._store.get_recommendation_items(run["run_id"])
                for item in items:
                    if item.get("paper_id") == paper_id:
                        continue
                    item_cats = set(item.get("categories", []))
                    if paper_cats & item_cats:
                        related.append(item)
                    if len(related) >= 8:
                        break
                if len(related) >= 8:
                    break
            paper["related_papers"] = related[:8]
        except Exception:
            paper["related_papers"] = []

        # Subscription matches — which subscriptions match this paper
        try:
            matches = []
            for sub in self._store.list_subscriptions():
                sub_text = sub.get("query_text", "").lower()
                title_text = (paper.get("title", "") or "").lower()
                abstract_text = (paper.get("abstract", "") or "").lower()
                if sub_text and (sub_text in title_text or sub_text in abstract_text):
                    matches.append({"name": sub.get("name", ""), "type": sub.get("type", "")})
            paper["subscription_matches"] = matches[:10]
        except Exception:
            paper["subscription_matches"] = []

        # Interaction history from interaction_events table
        try:
            if hasattr(self._store, 'list_interaction_events'):
                raw_events = self._store.list_interaction_events(paper_id=paper_id, limit=20)
                paper["interaction_history"] = [_format_event(e) for e in raw_events[:20]]
            else:
                paper["interaction_history"] = []
        except Exception:
            paper["interaction_history"] = []

        # Queue status
        queue_items = self._store.list_queue_items()
        queue_status = None
        for item in queue_items:
            if item.get("paper_id") == paper_id:
                queue_status = item.get("status")
                break
        paper["queue_status"] = queue_status

        # Collections — only show collections that actually contain this paper
        all_collections = self._store.list_collections()
        if isinstance(all_collections, list) and hasattr(self._store, 'list_collection_papers'):
            from state_store import _canonical_paper_id
            canonical_id = _canonical_paper_id(paper_id)
            filtered = []
            for col in all_collections:
                try:
                    col_id = col.get("id") or col.get("collection_id")
                    cpapers = self._store.list_collection_papers(col_id)
                    if any(_canonical_paper_id(cp.get("paper_id", "")) == canonical_id for cp in cpapers):
                        filtered.append(col)
                except Exception:
                    continue
            paper["collections"] = filtered
        else:
            paper["collections"] = all_collections if isinstance(all_collections, list) else []

        # Score details
        details = paper.get("score_details") or paper.get("score_details_json") or {}
        if isinstance(details, str):
            try:
                details = json.loads(details)
            except (TypeError, json.JSONDecodeError):
                details = {}
        paper["score_details"] = details

        context = {
            "title": f"{paper.get('title', 'Paper Detail')[:60]} - arXiv Recommender",
            "paper": paper,
        }
        context.update(page_ctx)
        return context

    def _resolve_active_research_question_id(self, explicit_id, queue_item, analysis):
        if explicit_id is not None and self._store.get_research_question(explicit_id):
            return explicit_id
        if queue_item and queue_item.get("research_question_id") is not None:
            return queue_item.get("research_question_id")
        claim_ids = []
        if isinstance(analysis, dict):
            claim_ids = analysis.get("evidence_claim_ids") or []
        if claim_ids:
            claims = self._store.list_evidence_claims()
            claim_by_id = {claim.get("id"): claim for claim in claims}
            for claim_id in claim_ids:
                question_id = (claim_by_id.get(claim_id) or {}).get("research_question_id")
                if question_id is not None and self._store.get_research_question(question_id):
                    return question_id
        return None

    def _load_evidence_claims(self, paper_id, *, analysis=None, research_question_id=None):
        claims = self._store.list_evidence_claims(paper_id=paper_id)
        if research_question_id is not None:
            claims = [
                claim for claim in claims
                if claim.get("research_question_id") in (None, research_question_id)
            ]

        ordered_ids = []
        if isinstance(analysis, dict):
            ordered_ids = analysis.get("evidence_claim_ids") or []
        if not ordered_ids:
            return claims

        by_id = {claim.get("id"): claim for claim in claims}
        ordered = [by_id[claim_id] for claim_id in ordered_ids if claim_id in by_id]
        remaining = [claim for claim in claims if claim.get("id") not in set(ordered_ids)]
        return ordered + remaining

    def _build_evidence_summary(self, claims):
        by_type = {"factual": 0, "interpretive": 0, "caveat": 0, "gap": 0}
        by_source = {}
        for claim in claims:
            claim_type = claim.get("claim_type") or "factual"
            if claim_type not in by_type:
                by_type[claim_type] = 0
            by_type[claim_type] += 1
            source = claim.get("evidence_source") or "other"
            by_source[source] = by_source.get(source, 0) + 1
        return {
            "total": len(claims),
            "by_type": by_type,
            "by_source": by_source,
            "has_claims": bool(claims),
        }

    def _find_paper_data(self, paper_id: str) -> Optional[dict]:
        """Find paper data from any available source.

        Lookup order:
        1. SQLite recommendation runs.
        2. History markdown digest files.
        3. SQLite paper_metadata table.
        4. cache/paper_cache.json on disk.
        5. Graceful detail shell with arXiv link (minimal fallback).
        """
        from state_store import _canonical_paper_id

        # 1. Try recommendation runs in SQLite first
        try:
            recent_runs = self._store.list_recommendation_runs(limit=5)
            for run in recent_runs:
                items = self._store.get_recommendation_items(run["run_id"])
                for item in items:
                    stored_id = _canonical_paper_id(item.get("paper_id") or item.get("id") or "")
                    if stored_id == paper_id:
                        return item
        except Exception:
            pass

        # 2. Try reading from history markdown files
        import os
        if os.path.exists(str(HISTORY_DIR)):
            for fname in sorted(os.listdir(str(HISTORY_DIR)), reverse=True):
                if not fname.startswith("digest_") or not fname.endswith(".md"):
                    continue
                filepath = os.path.join(str(HISTORY_DIR), fname)
                try:
                    from app.viewmodels.inbox_viewmodel import InboxViewModel
                    papers, _ = InboxViewModel.parse_digest(filepath, use_cache=False)
                    for p in papers:
                        if _canonical_paper_id(p.get("id") or "") == paper_id:
                            return p
                except Exception:
                    continue

        # 3. Try SQLite paper_metadata table
        try:
            meta = self._store.get_paper_metadata(paper_id)
            if meta:
                return meta
        except Exception:
            pass

        # 4. Try cache/paper_cache.json
        try:
            cache_path = Path(str(CACHE_DIR)) / "paper_cache.json"
            if cache_path.exists():
                cache = json.loads(cache_path.read_text(encoding="utf-8"))
                if paper_id in cache:
                    return cache[paper_id]
        except Exception:
            pass

        # 5. Graceful detail shell — show arXiv link even when data is sparse
        return {
            "paper_id": paper_id,
            "id": paper_id,
            "title": f"Paper {paper_id}",
            "authors": [],
            "abstract": "Details for this paper are not available in the local cache. "
                         "You can view it directly on arXiv.",
            "categories": [],
        }
