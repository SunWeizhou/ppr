"""Library page routes."""

from __future__ import annotations

from flask import Blueprint, request

bp = Blueprint("library", __name__)


@bp.get("/library")
def library_page():
    import web_server

    return web_server._render_library_research(
        request.args.get("tab", "collections"),
        request.args.get("collection_id", type=int),
        request.args.get("date", ""),
    )

