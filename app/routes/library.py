"""Library page routes."""

from __future__ import annotations

from flask import Blueprint, render_template, request

from app.viewmodels.library_viewmodel import LibraryViewModel
from state_store import get_state_store

bp = Blueprint("library", __name__)


@bp.get("/library")
def library_page():
    store = get_state_store()
    vm = LibraryViewModel(store)
    return render_template(
        "library_research.html",
        **vm.to_template_context(
            tab=request.args.get("tab", "collections"),
            collection_id=request.args.get("collection_id", type=int),
            selected_date=request.args.get("date", ""),
        ),
    )
