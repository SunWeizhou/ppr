"""Recommendations workspace routes."""

from __future__ import annotations

from flask import Blueprint, render_template, request

from app.viewmodels.recommendations_viewmodel import RecommendationsViewModel
from state_store import get_state_store

bp = Blueprint("recommendations", __name__)


@bp.get("/recommendations")
def recommendations_page():
    store = get_state_store()
    vm = RecommendationsViewModel(store)
    return render_template(
        "recommendations.html",
        **vm.to_template_context(
            mode=request.args.get("mode", "for_you"),
            query=request.args.get("q", ""),
        ),
    )
