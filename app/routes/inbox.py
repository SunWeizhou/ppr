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


def _request_research_question_id() -> int | None:
    raw = request.args.get("research_question_id") or request.args.get("question_id")
    if not raw:
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


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

    # Try SQLite first
    papers, themes = vm.load_papers_from_sqlite(date)

    if papers is not None:
        feedback = vm.load_feedback()
        prev_date, next_date = InboxViewModel.build_date_nav(date, dates)

        context = vm.to_template_context(
            date=date,
            papers=papers,
            keywords=themes,
            dates=dates,
            prev_date=prev_date,
            next_date=next_date,
            feedback=feedback,
        )
        return render_template("today.html", **context)

    # Fallback: markdown digest
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

    context = vm.to_template_context(
        date=date,
        papers=papers,
        keywords=keywords,
        dates=dates,
        prev_date=prev_date,
        next_date=next_date,
        feedback=feedback,
    )
    return render_template("today.html", **context)


@bp.get("/date/<date>")
def view_date(date):
    """Render the inbox page for a specific past date."""
    store = get_state_store()
    vm = InboxViewModel(store)

    # Try SQLite first
    papers, themes = vm.load_papers_from_sqlite(date)

    if papers is not None:
        dates = InboxViewModel.get_available_dates()
        feedback = vm.load_feedback()
        prev_date, next_date = InboxViewModel.build_date_nav(date, dates)

        context = vm.to_template_context(
            date=date,
            papers=papers,
            keywords=themes,
            dates=dates,
            prev_date=prev_date,
            next_date=next_date,
            feedback=feedback,
        )
        return render_template("today.html", **context)

    # Fallback: markdown digest
    filepath = os.path.join(HISTORY_DIR, f"digest_{date}.md")

    if not os.path.exists(filepath):
        return vm.to_no_data_html(date)

    dates = InboxViewModel.get_available_dates()
    papers, keywords = vm.parse_digest(filepath)
    feedback = vm.load_feedback()
    prev_date, next_date = InboxViewModel.build_date_nav(date, dates)

    context = vm.to_template_context(
        date=date,
        papers=papers,
        keywords=keywords,
        dates=dates,
        prev_date=prev_date,
        next_date=next_date,
        feedback=feedback,
    )
    return render_template("today.html", **context)


@bp.get("/papers/<paper_id>")
def paper_detail(paper_id):
    """Render the paper detail page."""
    from state_store import _canonical_paper_id
    paper_id = _canonical_paper_id(paper_id)
    from app.viewmodels.paper_viewmodel import PaperViewModel
    store = get_state_store()
    vm = PaperViewModel(store)
    context = vm.to_detail_context(paper_id)
    if "error" in context:
        return render_template("paper_detail.html", **context), 404
    return render_template("paper_detail.html", **context)


# ---------------------------------------------------------------------------
# Contextual search
# ---------------------------------------------------------------------------


@bp.get("/search")
def search_page():
    """Render an empty search page."""
    store = get_state_store()
    vm = SearchViewModel(store)
    return render_template(
        "search_research.html",
        **vm.to_template_context(
            [],
            [],
            research_question_id=_request_research_question_id(),
        ),
    )


@bp.get("/search/<path:keywords>")
def search_keywords(keywords):
    """Search papers by custom keywords and render results."""
    keyword_list = [k.strip() for k in keywords.replace("/", ",").split(",") if k.strip()]

    if not keyword_list:
        store = get_state_store()
        vm = SearchViewModel(store)
        return render_template(
            "search_research.html",
            **vm.to_template_context(
                [],
                [],
                research_question_id=_request_research_question_id(),
            ),
        )

    try:
        from arxiv_recommender_v5 import search_by_keywords

        papers = search_by_keywords(keyword_list, max_results=25, days_back=60)
    except Exception as e:
        logger.error("Search error: %s", e)
        safe_err = str(e).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return (
            '<html><body style="font-family:sans-serif;padding:40px;background:#1a1a2e;color:#fff;">'
            "<h1>Search Error</h1>"
            f"<p>Error: {safe_err}</p>"
            '<p><a href="/" style="color:#00d4ff">Return Home</a></p>'
            "</body></html>"
        )

    store = get_state_store()
    research_question_id = _request_research_question_id()
    source_run_id = (
        f"research-question-{research_question_id}"
        if research_question_id
        else "ad-hoc-search"
    )
    # Save search-result metadata so /papers/<id> can find these papers
    for paper in papers:
        pid = paper.get("paper_id") or paper.get("id") or ""
        if pid:
            store.save_paper_metadata(
                pid,
                {
                    "title": paper.get("title", ""),
                    "abstract": paper.get("abstract") or paper.get("summary", ""),
                    "authors": paper.get("authors", []),
                    "categories": paper.get("categories", []),
                    "published_at": paper.get("published_at") or paper.get("date", ""),
                },
                source="search_workspace" if research_question_id else "search",
                source_run_id=source_run_id,
            )
    vm = SearchViewModel(store)
    return render_template(
        "search_research.html",
        **vm.to_template_context(
            papers,
            keyword_list,
            research_question_id=research_question_id,
        ),
    )
