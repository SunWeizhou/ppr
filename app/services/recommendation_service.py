"""Recommendation orchestration service boundary."""

from __future__ import annotations

import os
from datetime import datetime


class RecommendationService:
    def daily_page(self, date=None, *, auto_generate: bool = True):
        import os as _os
        from datetime import datetime as _datetime
        from flask import redirect, render_template, request

        from app.viewmodels.inbox_viewmodel import InboxViewModel
        from app_paths import HISTORY_DIR
        from state_store import get_state_store

        # Onboarding check: redirect new users without a profile
        if not request.args.get("skip_onboarding"):
            from config_manager import CONFIG_FILE

            if not CONFIG_FILE.exists():
                return redirect("/onboarding")

        store = get_state_store()
        vm = InboxViewModel(store)

        dates = InboxViewModel.get_available_dates()
        today = _datetime.now().strftime("%Y-%m-%d")

        if not date:
            date = dates[0] if dates else today

        filepath = _os.path.join(HISTORY_DIR, f"digest_{date}.md")

        # If today's file doesn't exist and auto_generate is enabled, start background generation
        if not _os.path.exists(filepath) and auto_generate and date == today:
            vm.start_background_generation()
            return render_template("generating.html", **vm.to_generating_context())

        if not _os.path.exists(filepath):
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

    def status(self):
        from flask import jsonify

        from app.viewmodels.shared import serialize_job
        from app_paths import STATE_DB_PATH
        from state_store import get_state_store

        try:
            from arxiv_recommender_v5 import (
                CONFIG as PIPELINE_CONFIG,
                load_daily_recommendation,
            )

            today = datetime.now().strftime("%Y-%m-%d")
            cached_papers, cached_themes = load_daily_recommendation(PIPELINE_CONFIG["cache_dir"])
            store = get_state_store()
            latest_job = store.get_latest_job("daily_recommendation")
            recommendation_health = _build_recommendation_health(cached_papers)

            # Derive generation status from the latest job record
            gen_status = {
                "running": latest_job is not None and latest_job.get("status") == "running",
                "error": latest_job.get("error_text") if latest_job else None,
            }

            return jsonify(
                {
                    "date": today,
                    "has_recommendation": cached_papers is not None,
                    "paper_count": len(cached_papers) if cached_papers else 0,
                    "themes": cached_themes or [],
                    "generated_at": datetime.now().isoformat(),
                    "generation": gen_status,
                    "job": serialize_job(latest_job),
                    "state_db": str(STATE_DB_PATH),
                    "recommendation_health": recommendation_health,
                }
            )
        except Exception as e:
            import logging

            logging.getLogger(__name__).error(f"Status error: {e}")
            return jsonify({"error": str(e)}), 500

    def export_state(self):
        from app_paths import CACHE_DIR, PROJECT_ROOT

        from state_store import get_state_store
        from utils import safe_load_json

        snapshot_files = {
            "user_profile": PROJECT_ROOT / "user_profile.json",
            "user_config": PROJECT_ROOT / "user_config.json",
            "keywords_config": PROJECT_ROOT / "keywords_config.json",
            "user_feedback": CACHE_DIR / "user_feedback.json",
            "favorite_papers": CACHE_DIR / "favorite_papers.json",
            "paper_cache": CACHE_DIR / "paper_cache.json",
            "journal_update_log": CACHE_DIR / "journal_update_log.json",
        }

        files = {}
        for key, path in snapshot_files.items():
            if path.exists():
                files[key] = safe_load_json(str(path), {})
        return {
            "schema_version": "local-product-state-v1",
            "exported_at": datetime.now().isoformat(),
            "files": files,
            "state_store": get_state_store().export_state(),
        }

    def import_state(self, snapshot):
        from state_store import get_state_store

        return get_state_store().import_state(snapshot)


def _build_recommendation_health(cached_papers=None):
    try:
        from config_manager import get_config

        config = get_config()
        core_count = len(config.core_keywords)
        secondary_count = len(config.get_keywords_by_category("secondary"))
        theory_count = len(config.theory_keywords)
        zotero_path = os.path.expanduser(config._zotero.database_path or "")
        zotero_exists = bool(zotero_path and os.path.exists(zotero_path))
        scores = [float(paper.get("score", 0) or 0) for paper in (cached_papers or [])]
        max_score = max(scores, default=0.0)
        low_signal_count = sum(1 for score in scores if score <= 0.7)
        return {
            "core_keyword_count": core_count,
            "secondary_keyword_count": secondary_count,
            "theory_keyword_count": theory_count,
            "has_positive_profile": (core_count + secondary_count) > 0,
            "max_score": max_score,
            "low_signal_count": low_signal_count,
            "zotero": {
                "enabled": bool(config._zotero.enabled),
                "configured_path": config._zotero.database_path,
                "path_exists": zotero_exists,
                "auto_detect": bool(config._zotero.auto_detect),
            },
        }
    except Exception as exc:
        import logging

        logging.getLogger(__name__).warning(f"Could not build recommendation health: {exc}")
        return {
            "core_keyword_count": 0,
            "secondary_keyword_count": 0,
            "theory_keyword_count": 0,
            "has_positive_profile": False,
            "zotero": {"enabled": False, "configured_path": "", "path_exists": False},
        }
