"""Paper Agent assistant API — session-based conversation endpoints."""

from __future__ import annotations

from flask import jsonify, request

from . import bp
from .helpers import _current_state_store
from app.services.agent_service import AgentService
from app.services.ai_providers import build_ai_provider_from_env


def _agent_service():
    return AgentService(
        _current_state_store(),
        provider_factory=build_ai_provider_from_env,
    )


# ------------------------------------------------------------------
# Session CRUD
# ------------------------------------------------------------------

@bp.post("/api/agent/sessions")
def create_agent_session():
    """Create a new agent session."""
    data = request.get_json() or {}
    title = str(data.get("title", "New Session") or "New Session").strip()
    store = _current_state_store()
    session = store.create_agent_session(title=title)
    return jsonify({"success": True, "session": session})


@bp.get("/api/agent/sessions")
def list_agent_sessions():
    """List agent sessions. Query params: archived (0|1), limit (int)."""
    store = _current_state_store()
    archived_param = request.args.get("archived")
    archived = None
    if archived_param is not None:
        archived = archived_param in ("1", "true", "True")
    limit = int(request.args.get("limit", 20))
    sessions = store.list_agent_sessions(archived=archived, limit=limit)
    return jsonify({"success": True, "sessions": sessions})


@bp.get("/api/agent/sessions/<session_id>")
def get_agent_session(session_id: str):
    """Get a session with its message history."""
    store = _current_state_store()
    session = store.get_agent_session(session_id)
    if not session:
        return jsonify({"success": False, "error": "Session not found"}), 404
    limit = int(request.args.get("limit", 50))
    messages = store.get_session_messages(session_id, limit=limit)
    return jsonify({"success": True, "session": session, "messages": messages})


@bp.put("/api/agent/sessions/<session_id>")
def update_agent_session(session_id: str):
    """Update session title, pin, or archive status."""
    store = _current_state_store()
    data = request.get_json() or {}

    kwargs = {}
    if "title" in data:
        kwargs["title"] = str(data["title"] or "").strip()
    if "is_pinned" in data:
        kwargs["is_pinned"] = bool(data["is_pinned"])
    if "is_archived" in data:
        kwargs["is_archived"] = bool(data["is_archived"])
    if "summary" in data:
        kwargs["summary"] = str(data["summary"] or "").strip()

    session = store.update_agent_session(session_id, **kwargs)
    if not session:
        return jsonify({"success": False, "error": "Session not found"}), 404
    return jsonify({"success": True, "session": session})


@bp.delete("/api/agent/sessions/<session_id>")
def delete_agent_session(session_id: str):
    """Delete a session and its messages."""
    store = _current_state_store()
    deleted = store.delete_agent_session(session_id)
    if not deleted:
        return jsonify({"success": False, "error": "Session not found"}), 404
    return jsonify({"success": True})


# ------------------------------------------------------------------
# Messages
# ------------------------------------------------------------------

@bp.post("/api/agent/sessions/<session_id>/messages")
def send_agent_message(session_id: str):
    """Send a message in a session. Use session_id='new' to auto-create."""
    data = request.get_json() or {}
    message = str(data.get("message", "") or "").strip()
    page_context = data.get("page_context") or {}
    confirmation_token = data.get("confirmation_token")

    effective_session_id = None if session_id in ("new", "auto") else session_id

    service = _agent_service()
    result = service.handle_message(
        message,
        session_id=effective_session_id,
        page_context=page_context,
        confirmation_token=confirmation_token,
    )
    return jsonify(result)


# ------------------------------------------------------------------
# Legacy compatibility endpoint
# ------------------------------------------------------------------

@bp.post("/api/agent/messages")
def agent_message_legacy():
    """Legacy single-message endpoint. Creates a persisted session."""
    data = request.get_json() or {}
    service = _agent_service()
    return jsonify(service.handle_message(
        str(data.get("message", "") or "").strip(),
        page_context=data.get("page_context") or {},
    ))


# ------------------------------------------------------------------
# Search History
# ------------------------------------------------------------------

@bp.get("/api/search/history")
def search_history():
    """List recent searches for the dropdown."""
    store = _current_state_store()
    limit = int(request.args.get("limit", 10))
    recent = store.list_recent_searches(limit=limit)
    return jsonify({"success": True, "searches": recent})


@bp.post("/api/search/history")
def record_search():
    """Record a search execution."""
    data = request.get_json() or {}
    store = _current_state_store()
    entry = store.record_search(
        str(data.get("query", "") or "").strip(),
        rewritten=data.get("rewritten"),
        result_count=int(data.get("result_count", 0)),
        sources=data.get("sources"),
    )
    return jsonify({"success": True, "entry": entry})


@bp.get("/api/search/suggestions")
def search_suggestions():
    """Get suggested searches based on history frequency."""
    store = _current_state_store()
    limit = int(request.args.get("limit", 5))
    suggestions = store.get_suggested_searches(limit=limit)
    return jsonify({"success": True, "suggestions": suggestions})


@bp.post("/api/search/rewrite")
def rewrite_query():
    """Rewrite a search query using QueryRewriter."""
    from app.services.query_rewriter import QueryRewriter
    data = request.get_json() or {}
    query = str(data.get("query", "") or "").strip()
    if not query:
        return jsonify({"success": False, "error": "No query provided"}), 400

    rewriter = QueryRewriter(provider_factory=build_ai_provider_from_env)
    result = rewriter.rewrite(query, context=data.get("context") or {})
    return jsonify({
        "success": True,
        "original": result.original,
        "rewritten": result.rewritten,
        "was_rewritten": result.was_rewritten,
        "explanation": result.explanation,
        "expanded_terms": result.expanded_terms,
    })
