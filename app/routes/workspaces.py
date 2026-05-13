"""Workspace overview page routes."""

from __future__ import annotations

from flask import Blueprint, redirect, render_template, request

from state_store import get_state_store

bp = Blueprint("workspaces", __name__)


@bp.get("/workspaces")
def workspace_list():
    """Redirect to home page which shows all workspaces."""
    return redirect("/")


@bp.get("/workspaces/<int:workspace_id>")
def workspace_overview(workspace_id):
    """Render the workspace overview page for a research question."""
    from app.viewmodels.workspace_viewmodel import WorkspaceOverviewViewModel

    store = get_state_store()
    vm = WorkspaceOverviewViewModel(store)
    context = vm.to_template_context(workspace_id)
    return render_template("workspace_overview.html", **context)


@bp.route("/workspaces/<int:workspace_id>/memo", methods=["GET", "POST"])
def workspace_memo(workspace_id):
    """View or edit a research memo for a workspace."""
    store = get_state_store()
    workspace = store.get_research_question(workspace_id) or {}
    if not workspace:
        return "Workspace not found", 404

    if request.method == "POST":
        content = request.form.get("content", "")
        store.save_memo(workspace_id, content)
        return redirect(f"/workspaces/{workspace_id}/memo")

    memo = store.get_memo(workspace_id)
    from app.viewmodels.shared import assemble_page_context

    base = assemble_page_context(store, active_tab="workspaces")
    context = {
        "title": f"Research Memo — {workspace.get('query_text', 'Untitled')} - Paper Agent",
        "active_tab": "workspaces",
        "workspace": workspace,
        "workspace_id": workspace_id,
        "memo": memo,
        "memo_content": (memo or {}).get("content", ""),
        "has_memo": memo is not None,
    }
    context.update(base)
    return render_template("workspace_memo.html", **context)


@bp.route("/workspaces/<int:workspace_id>/review", methods=["GET", "POST"])
def workspace_review(workspace_id):
    """View or generate a weekly review for a workspace."""
    store = get_state_store()
    workspace = store.get_research_question(workspace_id) or {}
    if not workspace:
        return "Workspace not found", 404

    from app.services.weekly_review_service import WeeklyReviewService

    review_service = WeeklyReviewService(store)

    if request.method == "POST":
        content = request.form.get("content", "")
        week_start = request.form.get("week_start", "")
        reflection_answers = {
            "changing_paper": request.form.get("reflection_changing_paper", ""),
            "remaining_uncertainty": request.form.get("reflection_remaining_uncertainty", ""),
            "next_investigation": request.form.get("reflection_next_investigation", ""),
        }
        if week_start:
            store.save_weekly_review(
                research_question_id=workspace_id,
                week_start=week_start,
                content=content,
                reflection_answers=reflection_answers,
            )
        return redirect(f"/workspaces/{workspace_id}/review")

    week_start = request.args.get("week_start", "")
    if not week_start:
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        monday = now - timedelta(days=now.weekday())
        week_start = monday.strftime("%Y-%m-%d")

    # Check if a saved review exists
    saved = store.get_weekly_review_by_week(week_start, research_question_id=workspace_id)

    if saved:
        generated = {
            "week_start": week_start,
            "content": saved.get("content", ""),
            "event_summary": saved.get("event_summary_json", {}),
        }
        if isinstance(generated["event_summary"], str):
            import json
            try:
                generated["event_summary"] = json.loads(generated["event_summary"])
            except (json.JSONDecodeError, TypeError):
                generated["event_summary"] = {}
        reflection_saved = saved.get("reflection_answers_json", {})
        if isinstance(reflection_saved, str):
            try:
                reflection_saved = json.loads(reflection_saved)
            except (json.JSONDecodeError, TypeError):
                reflection_saved = {}
    else:
        generated = review_service.generate_review(workspace_id, week_start=week_start)
        reflection_saved = {}

    from app.viewmodels.shared import assemble_page_context
    base = assemble_page_context(store, active_tab="workspaces")
    context = {
        "title": f"Weekly Review — {workspace.get('query_text', 'Untitled')} - Paper Agent",
        "active_tab": "workspaces",
        "workspace": workspace,
        "workspace_id": workspace_id,
        "week_start": week_start,
        "review_content": generated["content"],
        "event_summary": generated.get("event_summary", {}),
        "reflection_answers": reflection_saved,
        "is_saved": saved is not None,
    }
    context.update(base)
    return render_template("workspace_review.html", **context)
