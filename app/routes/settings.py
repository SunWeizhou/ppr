"""Settings page routes."""

from __future__ import annotations

from flask import Blueprint

bp = Blueprint("settings", __name__)


@bp.get("/settings")
def settings_page():
    import web_server

    return web_server.settings_page()

