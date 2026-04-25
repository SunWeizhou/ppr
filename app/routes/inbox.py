"""Inbox and contextual search page routes."""

from __future__ import annotations

from flask import Blueprint

bp = Blueprint("inbox", __name__)


@bp.get("/")
def index():
    import web_server

    return web_server.generate_page()


@bp.get("/date/<date>")
def view_date(date):
    import web_server

    return web_server.view_date(date)


@bp.get("/search")
def search_page():
    import web_server

    return web_server.search_page()


@bp.get("/search/<path:keywords>")
def search_keywords(keywords):
    import web_server

    return web_server.search_keywords(keywords)

