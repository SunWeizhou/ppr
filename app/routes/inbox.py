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
    """Render the Paper Agent home workspace."""
    # Onboarding guard
    if not request.args.get("skip_onboarding"):
        from config_manager import CONFIG_FILE
        if not CONFIG_FILE.exists():
            return redirect("/onboarding")
            
    from app.viewmodels.home_viewmodel import HomeViewModel
    store = get_state_store()
    vm = HomeViewModel(store)
    context = vm.to_template_context()
    return render_template("home_workspace.html", **context)


@bp.get("/daily")
def daily_page():
    """Legacy daily triage page (moved from / for workspace-first nav)."""
    store = get_state_store()
    vm = InboxViewModel(store)

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
    from app.data._constants import canonical_paper_id as _canonical_paper_id
    paper_id = _canonical_paper_id(paper_id)
    from app.viewmodels.paper_viewmodel import PaperViewModel
    store = get_state_store()
    vm = PaperViewModel(store)
    context = vm.to_detail_context(
        paper_id,
        research_question_id=_request_research_question_id(),
    )
    if "error" in context:
        return render_template("paper_detail.html", **context), 404
    return render_template("paper_detail.html", **context)


# ---------------------------------------------------------------------------
# Contextual search
# ---------------------------------------------------------------------------


@bp.get("/search")
def search_page():
    """Render the search workspace."""
    return _render_search_workspace()


def _save_search_metadata(store, papers: list[dict], *, research_question_id: int | None, source_run_id: str) -> None:
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
                    "year": paper.get("year", ""),
                    "venue": paper.get("venue", ""),
                    "link": paper.get("link") or paper.get("url", ""),
                    "url": paper.get("url") or paper.get("link", ""),
                    "pdf_url": paper.get("pdf_url", ""),
                    "score": paper.get("score", 0),
                    "citation_count": paper.get("citation_count"),
                    "reference_count": paper.get("reference_count"),
                    "external_ids": paper.get("external_ids", {}),
                    "source": paper.get("source", ""),
                    "relevance_reason": paper.get("relevance_reason", paper.get("relevance", "")),
                },
                source="search_workspace" if research_question_id else "search",
                source_run_id=source_run_id,
            )


def _render_search_workspace(
    raw_query: str | None = None,
    papers: list[dict] | None = None,
    *,
    search_sources: dict | None = None,
    search_warnings: list[str] | None = None,
    search_errors: list[str] | None = None,
):
    store = get_state_store()
    research_question_id = _request_research_question_id()
    query = (raw_query if raw_query is not None else request.args.get("q") or "").strip()
    warnings: list[str] = list(search_warnings or [])
    errors: list[str] = list(search_errors or [])
    sources: dict = dict(search_sources or {})
    if papers is None:
        papers = []
        if query:
            try:
                from app.services.unified_search_service import search_papers

                result = search_papers(query, max_results=25)
                papers = result["papers"]
                warnings = result.get("warnings", [])
                errors = result.get("errors", [])
                sources = result.get("sources", {})
            except Exception as exc:
                warnings = [f"Search is temporarily unavailable: {exc}"]
    source_run_id = f"research-question-{research_question_id}" if research_question_id else "ad-hoc-search"
    _save_search_metadata(
        store,
        papers,
        research_question_id=research_question_id,
        source_run_id=source_run_id,
    )
    vm = SearchViewModel(store)
    context = vm.to_template_context(
        papers,
        [part for part in query.split() if part],
        research_question_id=research_question_id,
        raw_query=query,
        search_sources=sources,
        search_warnings=warnings,
        search_errors=errors,
    )
    return render_template("search_research.html", **context)


@bp.get("/search/<path:keywords>")
def search_keywords(keywords):
    """Search papers by custom keywords and render results."""
    raw = keywords.replace("/", ",")
    keyword_list = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        keyword_list.extend(k.strip() for k in part.split() if k.strip())

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
        from app.services.unified_search_service import search_papers

        result = search_papers(" ".join(keyword_list), max_results=25)
        papers = result["papers"]
        warnings = result.get("warnings", [])
        errors = result.get("errors", [])
        sources = result.get("sources", {})
    except Exception as e:
        logger.error("Search error: %s", e)
        safe_err = str(e).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return (
            '<html><body style="font-family:sans-serif;padding:40px;background:#1a1a2e;color:#fff;">'
            "<h1>Search Error</h1>"
            f"<p>Error: {safe_err}</p>"
            '<p><a href="/" style="color:#00d4ff">Return to Search</a></p>'
            "</body></html>"
        )

    store = get_state_store()
    research_question_id = _request_research_question_id()
    source_run_id = (
        f"research-question-{research_question_id}"
        if research_question_id
        else "ad-hoc-search"
    )
    return _render_search_workspace(
        raw_query=keywords,
        papers=papers,
        search_sources=sources,
        search_warnings=warnings,
        search_errors=errors,
    )
