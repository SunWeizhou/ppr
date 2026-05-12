"""Paper Agent assistant API."""

from __future__ import annotations

from flask import jsonify, request

from . import bp
from .helpers import _current_state_store
from app.services.agent_service import AgentService
from app.services.ai_providers import build_ai_provider_from_env


@bp.post("/api/agent/messages")
def agent_message():
    """Plan and execute a Paper Agent message from current page context."""
    data = request.get_json() or {}
    service = AgentService(
        _current_state_store(),
        provider_factory=build_ai_provider_from_env,
    )
    return jsonify(service.handle_message(
        str(data.get("message", "") or "").strip(),
        data.get("page_context") or {},
    ))
