"""Library page route — redirects to Reading (canonical surface)."""
from __future__ import annotations

from flask import Blueprint, redirect, request

bp = Blueprint("library", __name__, url_prefix="")


@bp.route("/library")
def library_redirect():
    """Redirect /library to /reading, preserving query parameters."""
    tab = request.args.get("tab", "collections")
    qs = "&".join(f"{k}={v}" for k, v in request.args.items() if k != "tab")
    if qs:
        return redirect(f"/reading?tab={tab}&{qs}")
    return redirect(f"/reading?tab={tab}")
