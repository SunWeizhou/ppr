"""Inbox and contextual search page routes."""

from __future__ import annotations

import os
from datetime import datetime

from flask import Blueprint, redirect, render_template, request

from app.viewmodels.inbox_viewmodel import InboxViewModel
from app.viewmodels.search_viewmodel import SearchViewModel
from app_paths import HISTORY_DIR
from logger_config import get_logger
from state_store import get_state_store

logger = get_logger(__name__)

bp = Blueprint("inbox", __name__)


# ---------------------------------------------------------------------------
# Inbox / home page
# ---------------------------------------------------------------------------


@bp.get("/")
def index():
    """Render the inbox home page, auto-generating if today has no data."""
    store = get_state_store()
    vm = InboxViewModel(store)

    # Onboarding guard
    if not request.args.get("skip_onboarding"):
        from config_manager import CONFIG_FILE

        if not CONFIG_FILE.exists():
            return redirect("/onboarding")

    dates = InboxViewModel.get_available_dates()
    today = datetime.now().strftime("%Y-%m-%d")
    date = dates[0] if dates else today

    filepath = os.path.join(HISTORY_DIR, f"digest_{date}.md")

    # Auto-generate when today's digest is missing
    if not os.path.exists(filepath) and date == today:
        vm.start_background_generation()
        return render_template("generating.html", **vm.to_generating_context())

    if not os.path.exists(filepath):
        return vm.to_no_data_html(date)

    papers, keywords = vm.parse_digest(filepath)
    feedback = vm.load_feedback()
    prev_date, next_date = InboxViewModel.build_date_nav(date, dates)

    selected_filter = request.args.get("filter", "all").strip().lower()
    if selected_filter not in {"all", "untriaged", "queued", "relevant", "ignored"}:
        selected_filter = "all"

    context = vm.to_template_context(
        date=date,
        papers=papers,
        keywords=keywords,
        dates=dates,
        prev_date=prev_date,
        next_date=next_date,
        feedback=feedback,
        selected_filter=selected_filter,
    )
    return render_template("home_research.html", **context)


@bp.get("/date/<date>")
def view_date(date):
    """Render the inbox page for a specific past date."""
    store = get_state_store()
    vm = InboxViewModel(store)

    filepath = os.path.join(HISTORY_DIR, f"digest_{date}.md")

    if not os.path.exists(filepath):
        return vm.to_no_data_html(date)

    dates = InboxViewModel.get_available_dates()
    papers, keywords = vm.parse_digest(filepath)
    feedback = vm.load_feedback()
    prev_date, next_date = InboxViewModel.build_date_nav(date, dates)

    selected_filter = request.args.get("filter", "all").strip().lower()
    if selected_filter not in {"all", "untriaged", "queued", "relevant", "ignored"}:
        selected_filter = "all"

    context = vm.to_template_context(
        date=date,
        papers=papers,
        keywords=keywords,
        dates=dates,
        prev_date=prev_date,
        next_date=next_date,
        feedback=feedback,
        selected_filter=selected_filter,
    )
    return render_template("home_research.html", **context)


# ---------------------------------------------------------------------------
# Contextual search
# ---------------------------------------------------------------------------


@bp.get("/search")
def search_page():
    """Render an empty search page."""
    store = get_state_store()
    vm = SearchViewModel(store)
    return render_template("search_research.html", **vm.to_template_context([], []))


@bp.get("/search/<path:keywords>")
def search_keywords(keywords):
    """Search papers by custom keywords and render results."""
    keyword_list = [k.strip() for k in keywords.replace("/", ",").split(",") if k.strip()]

    if not keyword_list:
        store = get_state_store()
        vm = SearchViewModel(store)
        return render_template("search_research.html", **vm.to_template_context([], []))

    try:
        from arxiv_recommender_v5 import search_by_keywords

        papers = search_by_keywords(keyword_list, max_results=25, days_back=60)
    except Exception as e:
        logger.error(f"Search error: {e}")
        return (
            '<html><body style="font-family:sans-serif;padding:40px;background:#1a1a2e;color:#fff;">'
            "<h1>Search Error</h1>"
            f"<p>Error: {str(e)}</p>"
            '<p><a href="/" style="color:#00d4ff">Return Home</a></p>'
            "</body></html>"
        )

    store = get_state_store()
    vm = SearchViewModel(store)
    return render_template("search_research.html", **vm.to_template_context(papers, keyword_list))
