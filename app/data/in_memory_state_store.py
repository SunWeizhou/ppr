"""In-memory implementation of StateStoreProtocol for testing.

Backed by Python dicts instead of SQLite. Fast to instantiate,
no file I/O. Does NOT replicate SQL semantics (transactions,
thread safety, type coercion) — use SqliteStateStore when
those matter.
"""

from __future__ import annotations

import copy
import json
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.data._constants import QUEUE_STATUS_VALUES, canonical_paper_id


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat() + "Z"


def _next_id(state: dict[str, Any], table: str) -> int:
    state["_next_ids"][table] = state["_next_ids"].get(table, 0) + 1
    return state["_next_ids"][table]


def _table(state: dict[str, Any], name: str) -> list[dict]:
    if name not in state["_tables"]:
        state["_tables"][name] = []
    return state["_tables"][name]


def _get_by(state: dict[str, Any], table: str, key: str, value: Any) -> Optional[dict]:
    for row in _table(state, table):
        if row.get(key) == value:
            return row
    return None


def _list_by(state: dict[str, Any], table: str, key: str, value: Any) -> list[dict]:
    return [row for row in _table(state, table) if row.get(key) == value]


def _delete_by(state: dict[str, Any], table: str, key: str, value: Any) -> int:
    before = len(_table(state, table))
    state["_tables"][table] = [row for row in _table(state, table) if row.get(key) != value]
    return before - len(state["_tables"][table])


def _json_copy(val: Any) -> Any:
    """Deep-copy via JSON round-trip (mimics SQLite column type coercion)."""
    return json.loads(json.dumps(val))


class InMemoryStateStore:
    """Dict-backed state store for fast, isolated tests."""

    def __init__(self, db_path: str = ""):  # noqa: F811
        self._state: dict[str, Any] = {
            "_tables": {},
            "_next_ids": {},
            "_kv_store": {},
        }
        self._lock = threading.Lock()

    # ── Helpers ──

    def _t(self, name: str) -> list[dict]:
        return _table(self._state, name)

    def _get(self, table: str, key: str, value: Any) -> Optional[dict]:
        return _get_by(self._state, table, key, value)

    def _list(self, table: str, key: str, value: Any) -> list[dict]:
        return _list_by(self._state, table, key, value)

    def _del(self, table: str, key: str, value: Any) -> int:
        return _delete_by(self._state, table, key, value)

    def _next(self, table: str) -> int:
        return _next_id(self._state, table)

    # ── Key-value store ──

    def save(self, key: str, value: str) -> None:
        self._state["_kv_store"][key] = value

    def get(self, key: str) -> Optional[str]:
        return self._state["_kv_store"].get(key)

    # ── Queue / reading queue items ──

    def upsert_queue_item(
        self,
        paper_id: str,
        status: str,
        source: str = "",
        note: str = "",
        tags=None,
        research_question_id=None,
        decision_context: str = "",
    ) -> Dict:
        cid = canonical_paper_id(paper_id)
        existing = self._get("reading_queue_items", "paper_id", cid)
        now = _utc_now()
        if existing:
            existing["status"] = status
            existing["source"] = source
            existing["note"] = note
            existing["tags_json"] = tags
            existing["research_question_id"] = research_question_id
            existing["decision_context"] = decision_context
            existing["updated_at"] = now
            return dict(existing)
        row = {
            "id": self._next("reading_queue_items"),
            "paper_id": cid,
            "status": status,
            "source": source,
            "note": note,
            "tags_json": _json_copy(tags) if tags is not None else [],
            "research_question_id": research_question_id,
            "decision_context": decision_context,
            "created_at": now,
            "updated_at": now,
        }
        self._t("reading_queue_items").append(row)
        return dict(row)

    def get_queue_item(self, paper_id: str) -> Optional[Dict]:
        cid = canonical_paper_id(paper_id)
        row = self._get("reading_queue_items", "paper_id", cid)
        return dict(row) if row else None

    def list_queue_items(self, status: str | None = None) -> List[Dict]:
        if status:
            return [dict(r) for r in self._t("reading_queue_items") if r.get("status") == status]
        return [dict(r) for r in self._t("reading_queue_items")]

    def mark_as_completed(self, paper_id: str, source: str = "reading_page") -> Dict:
        cid = canonical_paper_id(paper_id)
        existing = self._get("reading_queue_items", "paper_id", cid)
        now = _utc_now()
        if existing:
            existing["status"] = "Completed"
            existing["updated_at"] = now
        else:
            existing = {
                "id": self._next("reading_queue_items"),
                "paper_id": cid,
                "status": "Completed",
                "source": source,
                "note": "",
                "tags_json": [],
                "research_question_id": None,
                "decision_context": "",
                "created_at": now,
                "updated_at": now,
            }
            self._t("reading_queue_items").append(existing)
        # Auto-record event
        self.record_event("queue_status_changed", cid, {"status": "Completed", "source": source})
        return dict(existing)

    # ── Paper metadata ──

    def save_paper_metadata(
        self,
        paper_id: str,
        metadata: dict,
        source: str = "",
        source_run_id: str = "",
        first_seen_at: str | None = None,
        workspace_status: str = "active",
    ) -> None:
        cid = canonical_paper_id(paper_id)
        existing = self._get("paper_metadata", "paper_id", cid)
        now = _utc_now()
        row = {
            "paper_id": cid,
            "title": metadata.get("title", ""),
            "abstract": metadata.get("abstract", ""),
            "authors": metadata.get("authors", []),
            "categories": metadata.get("categories", []),
            "published_at": metadata.get("published_at", ""),
            "link": metadata.get("link", ""),
            "score": metadata.get("score", 0),
            "relevance_reason": metadata.get("relevance_reason", ""),
            "source": source,
            "source_run_id": source_run_id,
            "metadata_json": _json_copy(metadata),
            "first_seen_at": first_seen_at or now,
            "workspace_status": workspace_status,
            "created_at": now if not existing else existing.get("created_at", now),
            "updated_at": now,
        }
        if existing:
            existing.update(row)
        else:
            self._t("paper_metadata").append(row)

    def get_paper_metadata(self, paper_id: str) -> Optional[dict]:
        cid = canonical_paper_id(paper_id)
        row = self._get("paper_metadata", "paper_id", cid)
        if row:
            result = dict(row)
            meta = result.get("metadata_json") or {}
            if isinstance(meta, dict):
                for k, v in meta.items():
                    if k not in ("paper_id", "metadata_json", "created_at", "updated_at", "source", "source_run_id", "first_seen_at", "workspace_status"):
                        result.setdefault(k, v)
            return result
        return None

    def get_paper_ai_analysis(self, paper_id: str) -> Optional[Dict]:
        cid = canonical_paper_id(paper_id)
        row = self._get("paper_ai_analyses", "paper_id", cid)
        return dict(row) if row else None

    def upsert_paper_ai_analysis(
        self,
        paper_id: str,
        analysis: dict,
        model_name: str,
        prompt_version: str,
        status: str = "ok",
        error_text: str = "",
        evidence_claim_ids=None,
        confidence=None,
    ) -> Dict:
        cid = canonical_paper_id(paper_id)
        existing = self._get("paper_ai_analyses", "paper_id", cid)
        now = _utc_now()
        row = {
            "paper_id": cid,
            "analysis_json": _json_copy(analysis),
            "model_name": model_name,
            "prompt_version": prompt_version,
            "status": status,
            "error_text": error_text,
            "evidence_claim_ids": _json_copy(evidence_claim_ids) if evidence_claim_ids else [],
            "confidence": confidence,
            "created_at": existing.get("created_at", now) if existing else now,
            "updated_at": now,
        }
        if existing:
            existing.update(row)
        else:
            self._t("paper_ai_analyses").append(row)
        return dict(row)

    def save_paper_embedding(self, paper_id: str, embedding_bytes: bytes, model_name: str) -> None:
        pass  # embeddings not supported in memory

    def get_paper_embedding(self, paper_id: str):
        return None

    def get_all_embeddings_for_model(self, model_name: str):
        return []

    # ── Research questions ──

    def create_research_question(
        self,
        query_text: str,
        intent_statement: str = "",
        status: str = "active",
        source: str = "manual",
    ) -> Dict:
        now = _utc_now()
        row = {
            "id": self._next("research_questions"),
            "query_text": query_text,
            "intent_statement": intent_statement,
            "status": status,
            "source": source,
            "created_at": now,
            "updated_at": now,
        }
        self._t("research_questions").append(row)
        return dict(row)

    def get_research_question(self, question_id: int) -> Optional[Dict]:
        row = self._get("research_questions", "id", question_id)
        return dict(row) if row else None

    def list_research_questions(self, status: str | None = None, limit: int = 100) -> List[Dict]:
        items = self._t("research_questions")
        if status:
            items = [r for r in items if r.get("status") == status]
        return [dict(r) for r in items[:limit]]

    def update_research_question(
        self,
        question_id: int,
        query_text=None,
        intent_statement=None,
        status=None,
        source=None,
    ) -> Optional[Dict]:
        row = self._get("research_questions", "id", question_id)
        if not row:
            return None
        if query_text is not None:
            row["query_text"] = query_text
        if intent_statement is not None:
            row["intent_statement"] = intent_statement
        if status is not None:
            row["status"] = status
        if source is not None:
            row["source"] = source
        row["updated_at"] = _utc_now()
        return dict(row)

    def seed_research_questions_from_keywords(self, keywords: list[str]) -> int:
        count = 0
        for kw in keywords:
            existing = [r for r in self._t("research_questions") if r.get("query_text") == kw]
            if not existing:
                self.create_research_question(kw, source="keyword")
                count += 1
        return count

    # ── Evidence claims ──

    def create_evidence_claim(
        self,
        paper_id: str,
        claim: str,
        evidence_text: str = "",
        evidence_source: str = "abstract",
        claim_type: str = "factual",
        analyst: str = "rule",
        research_question_id=None,
        claim_id=None,
    ) -> Dict:
        cid = canonical_paper_id(paper_id)
        row = {
            "id": claim_id or self._next("evidence_claims"),
            "paper_id": cid,
            "research_question_id": research_question_id,
            "claim": claim,
            "evidence_text": evidence_text,
            "evidence_source": evidence_source,
            "claim_type": claim_type,
            "analyst": analyst,
            "created_at": _utc_now(),
        }
        self._t("evidence_claims").append(row)
        return dict(row)

    def list_evidence_claims(
        self,
        paper_id: str | None = None,
        research_question_id: int | None = None,
        analyst: str | None = None,
    ) -> List[Dict]:
        items = self._t("evidence_claims")
        if paper_id:
            cid = canonical_paper_id(paper_id)
            items = [r for r in items if r.get("paper_id") == cid]
        if research_question_id is not None:
            items = [r for r in items if r.get("research_question_id") == research_question_id]
        if analyst is not None:
            items = [r for r in items if r.get("analyst") == analyst]
        return [dict(r) for r in items]

    def delete_evidence_claims(
        self,
        paper_id: str | None = None,
        research_question_id: int | None = None,
    ) -> int:
        count = 0
        remaining = []
        for r in self._t("evidence_claims"):
            if paper_id and canonical_paper_id(r.get("paper_id", "")) == canonical_paper_id(paper_id):
                count += 1
                continue
            if research_question_id is not None and r.get("research_question_id") == research_question_id:
                count += 1
                continue
            remaining.append(r)
        self._state["_tables"]["evidence_claims"] = remaining
        return count

    # ── Interaction events ──

    def record_event(self, event_type: str, paper_id: str = "", payload=None) -> int:
        if payload is None:
            payload = {}
        cid = canonical_paper_id(paper_id) if paper_id else ""
        event_id = self._next("interaction_events")
        row = {
            "id": event_id,
            "event_type": event_type,
            "paper_id": cid,
            "payload_json": _json_copy(payload),
            "created_at": _utc_now(),
        }
        self._t("interaction_events").append(row)
        return event_id

    def list_interaction_events(self, paper_id: str | None = None, limit: int = 100) -> List[Dict]:
        items = self._t("interaction_events")
        if paper_id:
            cid = canonical_paper_id(paper_id)
            items = [r for r in items if r.get("paper_id") == cid]
        return [dict(r) for r in items[-limit:]]

    # ── User profile & topic affinity ──

    def get_user_profile(self) -> Dict:
        rows = self._t("user_profile")
        if rows:
            return dict(rows[0])
        return {"interest_vector": None, "topic_weights": None, "entity_affinities": None, "reading_pace": None}

    def upsert_user_profile(
        self,
        interest_vector=None,
        topic_weights=None,
        entity_affinities=None,
        reading_pace=None,
    ) -> None:
        rows = self._t("user_profile")
        if rows:
            row = rows[0]
            if interest_vector is not None:
                row["interest_vector"] = interest_vector
            if topic_weights is not None:
                row["topic_weights"] = topic_weights
            if entity_affinities is not None:
                row["entity_affinities"] = entity_affinities
            if reading_pace is not None:
                row["reading_pace"] = reading_pace
        else:
            self._t("user_profile").append({
                "interest_vector": interest_vector or [],
                "topic_weights": topic_weights or {},
                "entity_affinities": entity_affinities or [],
                "reading_pace": reading_pace or {},
            })

    def update_profile_from_behavior(self) -> None:
        pass  # No-op in memory

    def get_user_topic_affinities(self) -> List[Dict]:
        return [dict(r) for r in self._t("user_topic_affinity")]

    def upsert_user_topic_affinity(self, topic: str, positive_score: float, negative_score: float) -> bool:
        existing = self._get("user_topic_affinity", "topic", topic)
        if existing:
            existing["positive_score"] = positive_score
            existing["negative_score"] = negative_score
        else:
            self._t("user_topic_affinity").append({
                "topic": topic,
                "positive_score": positive_score,
                "negative_score": negative_score,
                "created_at": _utc_now(),
            })
        return True

    def update_affinity_from_event(self, event_type: str, paper_categories: list, paper_keywords: list) -> bool:
        return True

    # ── Collections ──

    def create_collection(self, name: str, description: str = "", query_text: str = "") -> Dict:
        row = {
            "id": self._next("research_collections"),
            "name": name,
            "description": description,
            "query_text": query_text,
            "is_active": True,
            "created_at": _utc_now(),
            "updated_at": _utc_now(),
        }
        self._t("research_collections").append(row)
        return dict(row)

    def get_collection(self, collection_id: int) -> Optional[Dict]:
        row = self._get("research_collections", "id", collection_id)
        return dict(row) if row else None

    def list_collections(self) -> List[Dict]:
        return [dict(r) for r in self._t("research_collections")]

    def update_collection(self, collection_id: int, name=None, description=None, query_text=None, is_active=None) -> Optional[Dict]:
        row = self._get("research_collections", "id", collection_id)
        if not row:
            return None
        if name is not None:
            row["name"] = name
        if description is not None:
            row["description"] = description
        if query_text is not None:
            row["query_text"] = query_text
        if is_active is not None:
            row["is_active"] = is_active
        row["updated_at"] = _utc_now()
        return dict(row)

    def delete_collection(self, collection_id: int) -> bool:
        return self._del("research_collections", "id", collection_id) > 0

    def add_paper_to_collection(self, collection_id: int, paper_id: str, note: str = "") -> bool:
        cid = canonical_paper_id(paper_id)
        existing = [r for r in self._t("collection_papers") if r.get("collection_id") == collection_id and r.get("paper_id") == cid]
        if not existing:
            self._t("collection_papers").append({
                "collection_id": collection_id,
                "paper_id": cid,
                "note": note,
                "added_at": _utc_now(),
            })
            return True
        return False

    def list_collection_papers(self, collection_id: int) -> List[Dict]:
        return [dict(r) for r in self._t("collection_papers") if r.get("collection_id") == collection_id]

    def remove_paper_from_collection(self, collection_id: int, paper_id: str) -> bool:
        cid = canonical_paper_id(paper_id)
        before = len([r for r in self._t("collection_papers") if r.get("collection_id") == collection_id and r.get("paper_id") == cid])
        self._state["_tables"]["collection_papers"] = [
            r for r in self._t("collection_papers")
            if not (r.get("collection_id") == collection_id and r.get("paper_id") == cid)
        ]
        return before > 0

    # ── Subscriptions & subscription hits ──

    def create_subscription(self, type, name, query_text="", payload_json="{}", enabled=True, research_question_id=None, entity_id=None, filters_json=None) -> Dict:
        row = {
            "id": self._next("subscriptions"),
            "type": type,
            "name": name,
            "query_text": query_text,
            "payload_json": payload_json,
            "enabled": enabled,
            "research_question_id": research_question_id,
            "entity_id": entity_id,
            "filters_json": filters_json,
            "created_at": _utc_now(),
            "updated_at": _utc_now(),
        }
        self._t("subscriptions").append(row)
        return dict(row)

    def get_subscription(self, subscription_id: int) -> Optional[Dict]:
        row = self._get("subscriptions", "id", subscription_id)
        return dict(row) if row else None

    def list_subscriptions(self, type=None) -> List[Dict]:
        if type:
            return [dict(r) for r in self._t("subscriptions") if r.get("type") == type]
        return [dict(r) for r in self._t("subscriptions")]

    def update_subscription(self, subscription_id: int, **kwargs) -> Optional[Dict]:
        row = self._get("subscriptions", "id", subscription_id)
        if not row:
            return None
        for k, v in kwargs.items():
            row[k] = v
        row["updated_at"] = _utc_now()
        return dict(row)

    def delete_subscription(self, subscription_id: int) -> bool:
        return self._del("subscriptions", "id", subscription_id) > 0

    def upsert_subscription_hit(self, subscription_id: int, paper_id: str, matched_reason: str = "", hit_date: str | None = None, status: str = "new") -> Dict:
        cid = canonical_paper_id(paper_id)
        row = {
            "subscription_id": subscription_id,
            "paper_id": cid,
            "matched_reason": matched_reason,
            "hit_date": hit_date or "",
            "status": status,
            "created_at": _utc_now(),
        }
        self._t("subscription_hits").append(row)
        return dict(row)

    def list_subscription_hits(self, subscription_id: int | None = None, status: str | None = None, limit: int = 50) -> List[Dict]:
        items = self._t("subscription_hits")
        if subscription_id is not None:
            items = [r for r in items if r.get("subscription_id") == subscription_id]
        if status is not None:
            items = [r for r in items if r.get("status") == status]
        return [dict(r) for r in items[-limit:]]

    # ── Saved searches & search history ──

    def create_saved_search(self, name: str, query_text: str, filters=None) -> Dict:
        row = {
            "id": self._next("saved_searches"),
            "name": name,
            "query_text": query_text,
            "filters_json": _json_copy(filters) if filters else {},
            "is_active": True,
            "created_at": _utc_now(),
            "updated_at": _utc_now(),
        }
        self._t("saved_searches").append(row)
        return dict(row)

    def get_saved_search(self, search_id: int) -> Optional[Dict]:
        row = self._get("saved_searches", "id", search_id)
        return dict(row) if row else None

    def list_saved_searches(self) -> List[Dict]:
        return [dict(r) for r in self._t("saved_searches")]

    def update_saved_search(self, search_id: int, name=None, query_text=None, filters=None, is_active=None) -> Optional[Dict]:
        row = self._get("saved_searches", "id", search_id)
        if not row:
            return None
        if name is not None:
            row["name"] = name
        if query_text is not None:
            row["query_text"] = query_text
        if filters is not None:
            row["filters_json"] = _json_copy(filters)
        if is_active is not None:
            row["is_active"] = is_active
        row["updated_at"] = _utc_now()
        return dict(row)

    def delete_saved_search(self, search_id: int) -> bool:
        return self._del("saved_searches", "id", search_id) > 0

    def record_search(self, query: str, rewritten=None, result_count: int = 0, sources=None) -> Dict:
        row = {
            "id": self._next("search_history"),
            "query_text": query,
            "rewritten_query": rewritten or "",
            "result_count": result_count,
            "sources_json": _json_copy(sources) if sources else [],
            "created_at": _utc_now(),
        }
        self._t("search_history").append(row)
        return dict(row)

    def list_recent_searches(self, limit: int = 10) -> List[Dict]:
        return [dict(r) for r in self._t("search_history")[-limit:]]

    def record_search_click(self, search_id: int, paper_id: str) -> Dict:
        cid = canonical_paper_id(paper_id)
        row = {
            "search_id": search_id,
            "paper_id": cid,
            "clicked_at": _utc_now(),
        }
        self._t("search_clicks").append(row)
        return dict(row)

    def get_suggested_searches(self, limit: int = 5) -> List[Dict]:
        return []

    # ── Jobs / recommendation runs ──

    def create_job(self, job_type: str, trigger_source: str = "unknown", payload=None, status: str = "queued") -> Dict:
        run_id = f"{job_type}-{self._next('job_runs')}"
        row = {
            "run_id": run_id,
            "job_type": job_type,
            "trigger_source": trigger_source,
            "payload_json": _json_copy(payload) if payload else {},
            "status": status,
            "result_json": {},
            "error_text": "",
            "created_at": _utc_now(),
            "updated_at": _utc_now(),
        }
        self._t("job_runs").append(row)
        return dict(row)

    def get_job(self, run_id: str) -> Optional[Dict]:
        row = self._get("job_runs", "run_id", run_id)
        return dict(row) if row else None

    def get_latest_job(self, job_type: str | None = None) -> Optional[Dict]:
        items = self._t("job_runs")
        if job_type:
            items = [r for r in items if r.get("job_type") == job_type]
        if not items:
            return None
        return dict(items[-1])

    def update_job(self, run_id: str, status: str, result=None, error_text=None) -> Optional[Dict]:
        row = self._get("job_runs", "run_id", run_id)
        if not row:
            return None
        row["status"] = status
        if result is not None:
            row["result_json"] = _json_copy(result)
        if error_text is not None:
            row["error_text"] = error_text
        row["updated_at"] = _utc_now()
        return dict(row)

    def has_running_job(self, job_type: str) -> bool:
        return any(
            r.get("job_type") == job_type and r.get("status") in ("queued", "running")
            for r in self._t("job_runs")
        )

    def create_job_if_no_active_job(self, job_type: str, trigger_source: str = "unknown", payload=None) -> Optional[Dict]:
        if self.has_running_job(job_type):
            return None
        return self.create_job(job_type, trigger_source, payload)

    def recover_stale_jobs(self, stale_after_minutes: int = 120) -> int:
        return 0

    def save_recommendation_run(self, run_date: str, trigger_source: str = "auto_homepage", papers=None, themes=None) -> str:
        import hashlib
        run_id = f"rec-{run_date}-{hashlib.md5(run_date.encode()).hexdigest()[:8]}"
        payload = {"papers": _json_copy(papers) if papers else [], "themes": _json_copy(themes) if themes else []}
        self.create_job("daily_recommendation", trigger_source, payload=payload, status="succeeded")
        return run_id

    def list_recommendation_runs(self, limit: int = 10) -> List[Dict]:
        return [dict(r) for r in self._t("job_runs")[-limit:] if r.get("job_type") == "daily_recommendation"]

    def list_recommendation_dates(self, limit: int = 30, trigger_source=None) -> List[str]:
        return []

    def get_recommendation_run_by_date(self, date: str, trigger_source=None) -> Optional[Dict]:
        return None

    def get_recommendation_items(self, run_id: str) -> List[Dict]:
        return []

    # ── Agent sessions & messages ──

    def create_agent_session(self, title: str = "New Session") -> Dict:
        session_id = f"session-{self._next('agent_sessions')}"
        row = {
            "session_id": session_id,
            "title": title,
            "summary": "",
            "is_pinned": False,
            "is_archived": False,
            "created_at": _utc_now(),
            "updated_at": _utc_now(),
        }
        self._t("agent_sessions").append(row)
        return dict(row)

    def get_agent_session(self, session_id: str) -> Optional[Dict]:
        row = self._get("agent_sessions", "session_id", session_id)
        return dict(row) if row else None

    def update_agent_session(self, session_id: str, title=None, summary=None, is_pinned=None, is_archived=None) -> Optional[Dict]:
        row = self._get("agent_sessions", "session_id", session_id)
        if not row:
            return None
        if title is not None:
            row["title"] = title
        if summary is not None:
            row["summary"] = summary
        if is_pinned is not None:
            row["is_pinned"] = is_pinned
        if is_archived is not None:
            row["is_archived"] = is_archived
        row["updated_at"] = _utc_now()
        return dict(row)

    def list_agent_sessions(self, archived: bool | None = None, limit: int = 50) -> List[Dict]:
        items = self._t("agent_sessions")
        if archived is not None:
            items = [r for r in items if r.get("is_archived") == archived]
        return [dict(r) for r in items[-limit:]]

    def delete_agent_session(self, session_id: str) -> bool:
        return self._del("agent_sessions", "session_id", session_id) > 0

    def add_agent_message(self, session_id: str, role: str, content: str, metadata=None) -> Dict:
        row = {
            "session_id": session_id,
            "role": role,
            "content": content,
            "metadata_json": _json_copy(metadata) if metadata else {},
            "created_at": _utc_now(),
        }
        self._t("agent_messages").append(row)
        return dict(row)

    def get_session_messages(self, session_id: str, limit: int = 50) -> List[Dict]:
        return [dict(r) for r in self._t("agent_messages") if r.get("session_id") == session_id][-limit:]

    def create_agent_pending_confirmation(self, session_id: str, message: str, plan_json: dict, page_context_json: dict, ttl_minutes: int = 15) -> Dict:
        import uuid as _uuid
        token = str(_uuid.uuid4())
        row = {
            "token": token,
            "session_id": session_id,
            "message": message,
            "plan_json": _json_copy(plan_json),
            "page_context_json": _json_copy(page_context_json),
            "status": "pending",
            "created_at": _utc_now(),
            "expires_at": _utc_now(),
        }
        self._t("agent_pending_confirmations").append(row)
        return dict(row)

    def get_agent_pending_confirmation(self, token: str) -> Optional[Dict]:
        row = self._get("agent_pending_confirmations", "token", token)
        return dict(row) if row else None

    def consume_agent_pending_confirmation(self, token: str) -> bool:
        row = self._get("agent_pending_confirmations", "token", token)
        if row:
            row["status"] = "consumed"
            return True
        return False

    def clean_expired_agent_confirmations(self) -> int:
        return 0

    # ── Entities ──

    def create_entity(self, entity_id, entity_type, name, aliases=None, external_ids=None, metadata_json=None, stats_json=None) -> Dict:
        row = {
            "entity_id": entity_id,
            "type": entity_type,
            "name": name,
            "aliases_json": _json_copy(aliases) if aliases else [],
            "external_ids_json": _json_copy(external_ids) if external_ids else {},
            "metadata_json": _json_copy(metadata_json) if metadata_json else {},
            "stats_json": _json_copy(stats_json) if stats_json else {},
            "created_at": _utc_now(),
            "updated_at": _utc_now(),
        }
        self._t("entities").append(row)
        return dict(row)

    def get_entity(self, entity_id) -> Optional[Dict]:
        row = self._get("entities", "entity_id", entity_id)
        return dict(row) if row else None

    def list_entities(self, entity_type=None, limit=100, search=None) -> List[Dict]:
        items = self._t("entities")
        if entity_type:
            items = [r for r in items if r.get("type") == entity_type]
        if search:
            items = [r for r in items if search.lower() in str(r.get("name", "")).lower()]
        return [dict(r) for r in items[:limit]]

    def update_entity(self, entity_id, name=None, aliases=None, external_ids=None, metadata_json=None, stats_json=None, last_synced=None) -> Optional[Dict]:
        row = self._get("entities", "entity_id", entity_id)
        if not row:
            return None
        if name is not None:
            row["name"] = name
        if aliases is not None:
            row["aliases_json"] = _json_copy(aliases)
        if external_ids is not None:
            row["external_ids_json"] = _json_copy(external_ids)
        if metadata_json is not None:
            row["metadata_json"] = _json_copy(metadata_json)
        if stats_json is not None:
            row["stats_json"] = _json_copy(stats_json)
        if last_synced is not None:
            row["last_synced"] = last_synced
        row["updated_at"] = _utc_now()
        return dict(row)

    def delete_entity(self, entity_id) -> bool:
        return self._del("entities", "entity_id", entity_id) > 0

    def create_entity_relation(self, source_id, target_id, relation_type, weight=1.0) -> Dict:
        row = {
            "id": self._next("entity_relations"),
            "source_id": source_id,
            "target_id": target_id,
            "relation_type": relation_type,
            "weight": weight,
            "created_at": _utc_now(),
        }
        self._t("entity_relations").append(row)
        return dict(row)

    def list_entity_relations(self, entity_id, direction="both", relation_type=None) -> List[Dict]:
        items = self._t("entity_relations")
        if direction == "both":
            items = [r for r in items if r.get("source_id") == entity_id or r.get("target_id") == entity_id]
        elif direction == "outgoing":
            items = [r for r in items if r.get("source_id") == entity_id]
        else:
            items = [r for r in items if r.get("target_id") == entity_id]
        if relation_type:
            items = [r for r in items if r.get("relation_type") == relation_type]
        return [dict(r) for r in items]

    # ── Inbox progress ──

    def get_inbox_progress(self, date_str: str) -> Dict:
        liked = 0
        disliked = 0
        queued = 0
        handled = 0
        for event in self._t("interaction_events"):
            # In a real implementation this would check date bounds
            if event.get("event_type") in ("like", "dislike", "queue_status_changed"):
                handled += 1
            if event.get("event_type") == "like":
                liked += 1
            elif event.get("event_type") == "dislike":
                disliked += 1
            elif event.get("event_type") == "queue_status_changed":
                queued += 1
        return {
            "handled": handled,
            "total": handled,
            "untriaged": 0,
            "liked": liked,
            "disliked": disliked,
            "queued": queued,
        }

    # ── Feedback model ──

    def get_feedback_model_auc(self) -> Optional[float]:
        rows = self._t("feedback_models")
        if rows:
            return rows[-1].get("auc")
        return None

    def get_latest_feedback_model(self) -> Optional[Dict]:
        rows = self._t("feedback_models")
        if rows:
            return dict(rows[-1])
        return None

    def save_feedback_model(self, sample_count: int, auc: float, model_json: dict) -> int:
        mid = self._next("feedback_models")
        self._t("feedback_models").append({
            "id": mid,
            "sample_count": sample_count,
            "auc": auc,
            "model_json": _json_copy(model_json),
            "created_at": _utc_now(),
        })
        return mid

    # ── Serialization ──

    def export_state(self) -> Dict[str, List[Dict]]:
        return {
            table: [dict(r) for r in rows]
            for table, rows in self._state.get("_tables", {}).items()
        }

    def import_state(self, snapshot: Dict[str, List[Dict]]) -> None:
        self._state["_tables"] = snapshot

    # ── Migration helpers ──

    def migrate_from_saved_searches(self) -> int:
        return 0

    def migrate_from_scholars_json(self) -> int:
        return 0
