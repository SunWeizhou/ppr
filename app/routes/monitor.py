"""Monitor page and legacy compatibility redirects."""

from __future__ import annotations

from flask import Blueprint, redirect

bp = Blueprint("monitor", __name__)


@bp.get("/monitor")
def monitor_page():
    import web_server

    return web_server.monitor_page()


@bp.get("/track")
def track_page():
    return redirect("/monitor", code=302)


@bp.get("/scholars")
def scholars_page():
    return redirect("/monitor?tab=authors", code=302)


@bp.get("/scholars/<category>")
def scholars_category(category):
    return redirect("/monitor?tab=authors", code=302)


@bp.get("/journal")
@bp.get("/journal/<journal_key>")
@bp.get("/journal/<journal_key>/v/<volume>")
@bp.get("/journal/<journal_key>/v/<volume>/i/<issue>")
def journal_page(journal_key="AoS", volume=None, issue=None):
    return redirect("/monitor?tab=venues", code=302)


@bp.get("/liked")
def view_liked():
    return redirect("/library?tab=saved", code=302)


@bp.get("/disliked")
def view_disliked():
    return redirect("/?filter=ignored", code=302)


@bp.get("/stats")
def reading_stats():
    return redirect("/settings?tab=system", code=302)

