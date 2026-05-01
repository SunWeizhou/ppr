"""Keywords / Settings API routes (keywords CRUD, settings, scholars, onboarding)."""
import logging
import threading
from datetime import datetime

from flask import jsonify, request

from . import bp
from .helpers import (
    CACHE_DIR,
    HISTORY_DIR,
    PROJECT_ROOT,
    _current_state_store,
    _scholar_service,
    _settings_service,
    serialize_job,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Keywords CRUD
# ---------------------------------------------------------------------------


@bp.route("/api/keywords", methods=["GET", "POST", "DELETE"])
def manage_keywords():
    svc = _settings_service()
    if request.method == "GET":
        return jsonify({"success": True, "keywords": svc.load_keywords_config()})

    data = request.get_json() or {}
    keyword = str(data.get("keyword", "")).strip()
    kw_type = data.get("type", "core")

    if request.method == "POST":
        if not keyword:
            return jsonify({"success": False, "error": "Keyword cannot be empty"}), 400
        config = svc.load_keywords_config()
        if kw_type == "core":
            config.setdefault("core_topics", {})[keyword] = float(data.get("weight", 3.0))
        elif kw_type == "secondary":
            config.setdefault("secondary_topics", {})[keyword] = float(data.get("weight", 2.0))
        elif kw_type == "theory":
            config.setdefault("theory_keywords", [])
            if keyword not in config["theory_keywords"]:
                config["theory_keywords"].append(keyword)
        elif kw_type == "demote":
            config.setdefault("demote_topics", {})[keyword] = -1.0
        elif kw_type == "dislike":
            dislike = config.get("dislike_topics", {})
            if isinstance(dislike, list):
                dislike = dict.fromkeys(dislike, -1.0)
            dislike[keyword] = -1.0
            config["dislike_topics"] = dislike
        svc.save_keywords_config(config)
        return jsonify({"success": True, "message": f"Added keyword: {keyword}"})

    # DELETE
    if not keyword:
        return jsonify({"success": False, "error": "Keyword cannot be empty"}), 400
    config = svc.load_keywords_config()
    removed = False
    if kw_type == "core" and keyword in config.get("core_topics", {}):
        del config["core_topics"][keyword]
        removed = True
    elif kw_type == "secondary" and keyword in config.get("secondary_topics", {}):
        del config["secondary_topics"][keyword]
        removed = True
    elif kw_type == "theory" and keyword in config.get("theory_keywords", []):
        config["theory_keywords"].remove(keyword)
        removed = True
    elif kw_type == "demote" and keyword in config.get("demote_topics", {}):
        del config["demote_topics"][keyword]
        removed = True
    elif kw_type == "dislike":
        dislike = config.get("dislike_topics", {})
        if isinstance(dislike, dict) and keyword in dislike:
            del dislike[keyword]
            removed = True
    if removed:
        svc.save_keywords_config(config)
        return jsonify({"success": True, "message": f"Removed keyword: {keyword}"})
    return jsonify({"success": False, "error": "Keyword not found"}), 400


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


@bp.post("/api/search")
def api_search():
    """API endpoint for keyword search."""
    data = request.get_json()
    keywords = data.get("keywords", [])

    if not keywords:
        return jsonify({"success": False, "error": "No keywords provided"}), 400

    try:
        from arxiv_recommender_v5 import search_by_keywords

        papers = search_by_keywords(keywords, max_results=25, days_back=60)
        return jsonify({
            "success": True,
            "papers": papers,
            "count": len(papers),
        })
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


def _run_pipeline_bg(run_id, force_refresh):
    """Background task to run the recommendation pipeline."""
    try:
        from arxiv_recommender_v5 import run_pipeline

        _current_state_store().update_job(run_id, "running")
        papers = run_pipeline(force_refresh=force_refresh)
        _current_state_store().update_job(
            run_id,
            "succeeded",
            result={
                "paper_count": len(papers) if papers else 0,
                "mode": "background_generation",
                "force_refresh": force_refresh,
            },
        )
    except Exception as exc:
        _current_state_store().update_job(run_id, "failed", error_text=str(exc))


@bp.post("/api/settings")
def save_settings():
    """Save user settings and sync to user_profile.json (unified config)."""
    data = request.get_json() or {}

    try:
        from config_manager import get_config, reload_config

        cm = get_config()

        # Parse core topics
        core_topics = data.get("coreTopics", [])

        # If coreTopics is empty, try legacy format
        if not core_topics:
            priority_text = data.get("priorityTopics", "")
            core_topics = [t.strip() for t in priority_text.split(",") if t.strip()]

        # Clear existing keywords and set core topics
        cm._keywords.clear()

        core_weights = {
            "statistical learning theory": 4.5,
            "nonparametric estimation": 4.0,
            "conditional density estimation": 3.5,
            "in-context learning": 5.0,
            "conformal prediction": 5.0,
            "generalization": 4.0,
            "excess risk": 4.0,
            "minimax rates": 3.5,
            "sample complexity": 3.5,
            "finite-sample": 3.0,
            "transformer theory": 3.0,
        }
        for topic in core_topics:
            weight = core_weights.get(topic.lower(), 4.0)
            cm.set_keyword(topic, weight, "core", save=False)

        # Update settings
        cm._settings.papers_per_day = data.get("papersPerDay", 20)
        cm._sources.arxiv_enabled = bool(data.get("arxivEnabled", True))
        cm._sources.journal_enabled = bool(data.get("journalEnabled", True))
        cm._sources.scholar_enabled = bool(data.get("scholarEnabled", False))
        cm._sources.lookback_days = int(data.get("lookbackDays", cm._sources.lookback_days or 14))

        # Save to user_profile.json
        cm.save()

        # Reload config in recommender module
        reload_config()

        logger.info(
            "Saved %d core keywords",
            len(core_topics),
        )

        # Regenerate if requested
        regenerate = data.get("regenerate", False)
        regeneration_job = None
        if regenerate:
            try:
                regeneration_job = _current_state_store().create_job_if_no_active_job(
                    "daily_recommendation",
                    trigger_source="settings_save",
                    payload={"force_refresh": True, "reason": "settings_updated"},
                )
                if regeneration_job is None:
                    return jsonify({
                        "success": False,
                        "error": "已有刷新任务正在排队或运行",
                    }), 409

                thread = threading.Thread(
                    target=_run_pipeline_bg,
                    args=(regeneration_job["run_id"], True),
                    daemon=True,
                )
                thread.start()
            except Exception as exc:
                if regeneration_job:
                    _current_state_store().update_job(regeneration_job["run_id"], "failed", error_text=str(exc))
                logger.error("Error regenerating after settings save: %s", exc)

        return jsonify({
            "success": True,
            "message": f"Saved {len(core_topics)} core keywords",
            "core_count": len(core_topics),
            "job": serialize_job(regeneration_job) if regeneration_job else None,
        })

    except Exception as exc:
        logger.error("Error saving settings: %s", exc)
        return jsonify({"success": False, "error": str(exc)}), 500


@bp.post("/api/settings/ai")
def save_ai_settings():
    """Save AI analysis provider configuration to user_profile.json."""
    data = request.get_json() or {}
    try:
        from config_manager import get_config

        cm = get_config()
        cm._ai.provider = str(data.get("provider", cm._ai.provider)).strip() or "none"
        cm._ai.api_key = str(data.get("api_key", "")).strip()
        cm._ai.base_url = str(data.get("base_url", cm._ai.base_url)).strip() or "https://api.deepseek.com"
        cm._ai.model = str(data.get("model", cm._ai.model)).strip() or "deepseek-chat"
        cm._ai.enabled = bool(data.get("enabled", cm._ai.enabled))
        cm.save()
        return jsonify({"success": True})
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@bp.post("/api/settings/ai/test")
def test_ai_connection():
    """Test the AI provider connection with submitted config."""
    data = request.get_json() or {}
    provider_name = str(data.get("provider", "none")).strip().lower()
    api_key = str(data.get("api_key", "")).strip()
    base_url = str(data.get("base_url", "https://api.deepseek.com")).strip()
    model = str(data.get("model", "deepseek-chat")).strip()

    if provider_name == "none":
        return jsonify({"success": False, "error": "No provider selected"}), 400
    if not api_key:
        return jsonify({"success": False, "error": "API key is required"}), 400

    try:
        if provider_name == "deepseek":
            from app.services.ai_providers import DeepSeekProvider

            provider = DeepSeekProvider(
                api_key=api_key,
                base_url=base_url,
                model=model,
                timeout=15,
            )
            # Send a minimal test payload
            test_payload = {
                "model": model,
                "messages": [
                    {"role": "user", "content": "Respond with the single word: ok"},
                ],
                "max_tokens": 5,
            }
            response = provider._request(test_payload)
            content = provider._extract_message_content(response)
            if not content:
                return jsonify({"success": False, "error": "Provider returned empty response"}), 502
            return jsonify({"success": True, "message": f"Connection successful (model: {model})"})

        elif provider_name == "openai":
            return jsonify({
                "success": False,
                "error": "OpenAI-compatible provider is not yet implemented",
            }), 501
        else:
            return jsonify({"success": False, "error": f"Unknown provider: {provider_name}"}), 400

    except Exception as exc:
        import logging as _logging

        _logging.getLogger(__name__).warning(f"AI connection test failed: {exc}")
        return jsonify({"success": False, "error": str(exc)}), 502


# ---------------------------------------------------------------------------
# Scholars
# ---------------------------------------------------------------------------


@bp.post("/api/scholars/add")
def api_add_scholar():
    data = request.get_json() or {}
    name = str(data.get("name", "")).strip()
    if not name:
        return jsonify({"success": False, "error": "Missing scholar name"}), 400
    service = _scholar_service()
    success, result = service.add(
        name=name,
        affiliation=data.get("affiliation", ""),
        focus=data.get("focus", ""),
        arxiv_query=data.get("arxiv_query", ""),
        google_scholar=data.get("google_scholar", ""),
        website=data.get("website", ""),
        email=data.get("email", ""),
    )
    if success:
        return jsonify({"success": True, "scholar": result})
    return jsonify({"success": False, "error": result}), 400


@bp.post("/api/scholars/parse_gscholar")
def api_parse_gscholar():
    data = request.get_json() or {}
    url = str(data.get("url", "")).strip()
    if not url:
        return jsonify({"success": False, "error": "Missing Google Scholar URL"}), 400
    from app.services.scholar_service import ScholarService

    result = ScholarService.parse_google_scholar_url(url)
    return jsonify(result)


@bp.post("/api/scholars/remove")
def api_remove_scholar():
    data = request.get_json() or {}
    name = str(data.get("name", "")).strip()
    if not name:
        return jsonify({"success": False, "error": "Missing scholar name"}), 400
    service = _scholar_service()
    success, message = service.remove(name)
    return jsonify({"success": success, "message": message})


@bp.post("/api/scholars/update")
def api_update_scholar():
    data = request.get_json() or {}
    original_name = str(data.get("original_name", "")).strip()
    name = str(data.get("name", "")).strip()
    if not original_name:
        return jsonify({"success": False, "error": "Missing original_name"}), 400
    service = _scholar_service()
    success, result = service.update(
        original_name,
        name=name,
        affiliation=data.get("affiliation", ""),
        focus=data.get("focus", ""),
        arxiv_query=data.get("arxiv_query", ""),
        google_scholar=data.get("google_scholar", ""),
        website=data.get("website", ""),
        email=data.get("email", ""),
    )
    if success:
        return jsonify({"success": True, "scholar": result})
    return jsonify({"success": False, "error": result}), 400


# ---------------------------------------------------------------------------
# Onboarding
# ---------------------------------------------------------------------------


@bp.post("/api/onboarding/save")
def save_onboarding():
    """Save onboarding wizard results to user_profile.json and create first saved search."""
    data = request.get_json() or {}

    topics_raw = data.get("topics") or []
    areas = data.get("areas") or []
    papers_per_day = int(data.get("papers_per_day", 20) or 20)
    zotero_path = str(data.get("zotero_path", "") or "").strip()
    ai_provider = str(data.get("ai_provider", "") or "").strip()
    ai_api_key = str(data.get("ai_api_key", "") or "").strip()
    ai_base_url = str(data.get("ai_base_url", "") or "").strip()
    ai_model = str(data.get("ai_model", "") or "").strip()
    first_query = str(data.get("first_query", "") or "").strip()

    try:
        from config_manager import get_config

        cm = get_config()

        # Clear existing default keywords so the profile reflects the user's actual interests
        cm._keywords.clear()

        # Set research topics as core keywords (higher weights for explicitly entered topics)
        for topic in topics_raw:
            name = str(topic).strip().lower()
            if name:
                cm.set_keyword(name, weight=5.0, category="core", save=False)

        # Set research areas as secondary keywords (lower weights for broader areas)
        area_weights = {
            "statistics": 3.0,
            "machine learning": 3.5,
            "deep learning": 3.0,
            "natural language processing": 2.5,
            "computer vision": 2.0,
            "reinforcement learning": 2.5,
            "optimization": 3.0,
            "causal inference": 3.0,
            "information theory": 3.0,
            "graph neural networks": 2.5,
            "theoretical ml": 3.5,
            "high-dimensional statistics": 3.5,
            "bayesian methods": 3.0,
            "time series": 2.5,
            "fairness & ethics": 1.5,
        }
        for area in areas:
            name = str(area).strip().lower()
            if name:
                weight = area_weights.get(name, 2.5)
                cm.set_keyword(name, weight=weight, category="secondary", save=False)

        # Settings
        cm._settings.papers_per_day = max(5, min(papers_per_day, 50))

        # Zotero
        if zotero_path:
            cm._zotero.database_path = zotero_path

        # AI config
        if ai_provider and ai_provider in ("deepseek", "openai_compat"):
            ai_enabled = bool(ai_api_key)
            cm._ai.provider = ai_provider
            cm._ai.api_key = ai_api_key
            cm._ai.enabled = ai_enabled
            if ai_base_url:
                cm._ai.base_url = ai_base_url
            elif ai_provider == "deepseek":
                cm._ai.base_url = "https://api.deepseek.com/v1"
            if ai_model:
                cm._ai.model = ai_model
            elif ai_provider == "deepseek":
                cm._ai.model = "deepseek-chat"
        else:
            cm._ai.provider = "none"
            cm._ai.enabled = False

        # Save everything to user_profile.json
        cm.save()

        # Create the first saved search / query subscription for the research question
        saved_search_id = None
        if first_query:
            try:
                ss = _current_state_store().create_saved_search(
                    first_query,
                    first_query,
                    filters={"description": "Created during onboarding"},
                )
                saved_search_id = ss.get("id") if ss else None
                # Also create a subscription for unified model
                if saved_search_id:
                    _current_state_store().create_subscription(
                        type="query",
                        name=first_query,
                        query_text=first_query,
                        payload_json={"filters": {}, "description": "Created during onboarding", "legacy_id": saved_search_id},
                    )
            except Exception:
                pass  # Non-critical; the profile is already saved

        return jsonify({
            "success": True,
            "message": "Profile saved successfully",
            "saved_search_id": saved_search_id,
        })

    except Exception as exc:
        import logging as _logging

        _logging.getLogger(__name__).error(
            "Failed to save onboarding profile: %s", exc, exc_info=True
        )
        return jsonify({"success": False, "error": str(exc)}), 500


# ---------------------------------------------------------------------------
# Debug
# ---------------------------------------------------------------------------


@bp.get("/debug")
def debug_info():
    """Debug endpoint returning system state overview as JSON."""
    try:
        import os as _os

        hist_dir = str(HISTORY_DIR)
        dates = []
        if _os.path.exists(hist_dir):
            for f in sorted(_os.listdir(hist_dir)):
                if f.startswith("digest_") and f.endswith(".md"):
                    dates.append(f.replace("digest_", "").replace(".md", ""))
        dates.sort(reverse=True)

        latest_job = _current_state_store().get_latest_job("daily_recommendation")
        queue_count = len(_current_state_store().list_queue_items())

        return jsonify({
            "success": True,
            "available_dates": dates[:10],
            "latest_job": serialize_job(latest_job),
            "queue_item_count": queue_count,
            "state_db_path": str(CACHE_DIR / "app_state.db"),
        })
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500
