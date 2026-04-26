"""arXiv Paper Recommender — web server entry point.

Thin Flask application shell. Page rendering, business logic, and API
handling live in app/viewmodels/, app/services/, and app/routes/.
"""

from __future__ import annotations

import os
import subprocess  # noqa: F401 — test compat (mocked via web_server.subprocess)
import threading
import time
from datetime import datetime, timezone

from flask import Flask, redirect, render_template, request
from flask_cors import CORS

from app_paths import CACHE_DIR, HISTORY_DIR, PROJECT_ROOT, STATE_DB_PATH, ensure_runtime_dirs
from logger_config import get_logger
from state_store import get_state_store

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------

app = Flask(__name__)
CORS(app)


@app.before_request
def _log_request():
    request._start_time = time.time()


@app.after_request
def _log_response(response):
    duration = time.time() - getattr(request, "_start_time", time.time())
    logger.info("%s %s %s (%.3fs)", request.method, request.path, response.status_code, duration)
    return response


# ---------------------------------------------------------------------------
# Module-level state (mutable — tests patch these)
# ---------------------------------------------------------------------------

STATE_STORE = get_state_store()
STATE_DB_FILE = str(STATE_DB_PATH)
FEEDBACK_FILE = str(CACHE_DIR / "user_feedback.json")
FAVORITES_FILE = str(CACHE_DIR / "favorite_papers.json")
CACHE_FILE = str(CACHE_DIR / "paper_cache.json")

SNAPSHOT_FILES = {
    "user_profile": PROJECT_ROOT / "user_profile.json",
    "user_config": PROJECT_ROOT / "user_config.json",
    "keywords_config": PROJECT_ROOT / "keywords_config.json",
    "user_feedback": CACHE_DIR / "user_feedback.json",
    "favorite_papers": CACHE_DIR / "favorite_papers.json",
    "paper_cache": CACHE_DIR / "paper_cache.json",
    "journal_update_log": CACHE_DIR / "journal_update_log.json",
}

_generation_status: dict = {"running": False, "started_at": None, "error": None, "run_id": None}


# ---------------------------------------------------------------------------
# Background recommendation pipeline
# ---------------------------------------------------------------------------


def _run_pipeline_background(run_id=None, force_refresh=False):
    """Run the recommendation pipeline in a background thread."""
    global _generation_status
    try:
        import sys

        sys.path.insert(0, str(PROJECT_ROOT))
        from arxiv_recommender_v5 import run_pipeline

        if run_id:
            STATE_STORE.update_job(run_id, "running")
        papers = run_pipeline(force_refresh=force_refresh)
        _generation_status["running"] = False
        if run_id:
            STATE_STORE.update_job(
                run_id,
                "succeeded",
                result={
                    "paper_count": len(papers) if papers else 0,
                    "mode": "background_generation",
                    "force_refresh": force_refresh,
                },
            )
        _generation_status["error"] = None
        logger.info("Background pipeline completed successfully")
    except Exception as e:
        _generation_status["running"] = False
        _generation_status["error"] = str(e)
        if run_id:
            STATE_STORE.update_job(run_id, "failed", error_text=str(e))
        logger.error("Background pipeline error: %s", e)


def _start_background_generation():
    """Start background recommendation generation; returns the job *run_id*.

    No-op if a generation is already running.
    """
    global _generation_status

    if _generation_status.get("running"):
        return _generation_status.get("run_id")

    job = STATE_STORE.create_job(
        "daily_recommendation",
        trigger_source="auto_homepage",
        payload={"force_refresh": False, "mode": "background_generation"},
        status="queued",
    )

    _generation_status = {
        "running": True,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "error": None,
        "run_id": job["run_id"],
    }

    thread = threading.Thread(
        target=_run_pipeline_background,
        args=(job["run_id"], False),
        daemon=True,
    )
    thread.start()
    logger.info("Started background pipeline generation")
    return job["run_id"]


# ---------------------------------------------------------------------------
# Page generation
# ---------------------------------------------------------------------------


def generate_page(date=None, auto_generate=True):
    """Generate the inbox/home page for a given date."""
    from app.viewmodels.inbox_viewmodel import InboxViewModel

    if not request.args.get("skip_onboarding"):
        from config_manager import CONFIG_FILE

        if not CONFIG_FILE.exists():
            return redirect("/onboarding")

    vm = InboxViewModel(STATE_STORE)
    dates = InboxViewModel.get_available_dates()
    today = datetime.now().strftime("%Y-%m-%d")

    if not date:
        date = dates[0] if dates else today

    filepath = os.path.join(HISTORY_DIR, f"digest_{date}.md")

    if not os.path.exists(filepath) and auto_generate and date == today:
        logger.info(
            "No recommendation found for today (%s), starting background generation...", today
        )
        _start_background_generation()
        return render_template("generating.html", **vm.to_generating_context())

    if not os.path.exists(filepath):
        return vm.to_no_data_html(date)

    papers, keywords = vm.parse_digest(filepath)
    feedback = vm.load_feedback()
    prev_date, next_date = InboxViewModel.build_date_nav(date, dates)

    selected_filter = request.args.get("filter", "all").strip().lower()
    if selected_filter not in {"all", "untriaged", "queued", "relevant", "ignored"}:
        selected_filter = "all"

    return render_template(
        "home_research.html",
        **vm.to_template_context(
            date=date,
            papers=papers,
            keywords=keywords,
            dates=dates,
            prev_date=prev_date,
            next_date=next_date,
            feedback=feedback,
            selected_filter=selected_filter,
        ),
    )


# ---------------------------------------------------------------------------
# Blueprint registration (module-level — required for test clients)
# ---------------------------------------------------------------------------


from app.routes import register_blueprints  # noqa: E402
from app.viewmodels.shared import NAV_ITEM_CONFIG  # noqa: E402 — test compat re-export

register_blueprints(app)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    ensure_runtime_dirs()

    if os.getenv("USE_DEV_SERVER"):
        logger.info("Starting Flask dev server on http://localhost:5555")
        app.run(host="localhost", port=5555, debug=True)
    else:
        from waitress import serve

        logger.info("Starting waitress on http://localhost:5555")
        serve(app, host="localhost", port=5555)


if __name__ == "__main__":
    main()
