"""API route ownership for the Flask app.

Routes are self-contained: each handler creates its own service or uses
STATE_STORE directly, avoiding import web_server wherever possible.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import threading
from datetime import datetime
from io import BytesIO

from flask import Blueprint, jsonify, request, send_file

from app.services.ai_analysis_service import AIAnalysisService
from app.services.ai_providers import build_ai_provider_from_env
from app.services.errors import AppError
from app.services.paper_utils import split_query_terms
from app.services.queue_service import QueueService
from app.viewmodels.shared import serialize_collection, serialize_saved_search, serialize_job
from app_paths import CACHE_DIR, HISTORY_DIR, PROJECT_ROOT
from state_store import QUEUE_STATUS_VALUES, _canonical_paper_id, get_state_store
from utils import atomic_write_json, safe_load_json

logger = logging.getLogger(__name__)

bp = Blueprint("api", __name__)
_own_state_store = get_state_store()
STATE_STORE = _own_state_store  # backward-compat for test patching
AI_ANALYSIS_PROVIDER = None

# File paths used by services (mirror web_server globals)
FEEDBACK_FILE = str(CACHE_DIR / "user_feedback.json")
FAVORITES_FILE = str(CACHE_DIR / "favorite_papers.json")
CACHE_FILE = str(CACHE_DIR / "paper_cache.json")
MY_SCHOLARS_FILE = str(PROJECT_ROOT / "my_scholars.json")


def _current_state_store():
    """Return the current StateStore, supporting test patching of web_server.STATE_STORE."""
    try:
        import web_server

        return web_server.STATE_STORE
    except Exception:
        return _own_state_store


def _ai_analysis_service():
    return AIAnalysisService(
        _current_state_store(),
        provider=AI_ANALYSIS_PROVIDER or build_ai_provider_from_env(),
    )


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


@bp.errorhandler(AppError)
def handle_app_error(error):
    return jsonify({"success": False, "error": str(error)}), error.status_code


# ---------------------------------------------------------------------------
# Helpers (formerly in web_server.py — now self-contained)
# ---------------------------------------------------------------------------

SNAPSHOT_FILES = {
    "user_profile": PROJECT_ROOT / "user_profile.json",
    "user_config": PROJECT_ROOT / "user_config.json",
    "keywords_config": PROJECT_ROOT / "keywords_config.json",
    "user_feedback": CACHE_DIR / "user_feedback.json",
    "favorite_papers": CACHE_DIR / "favorite_papers.json",
    "paper_cache": CACHE_DIR / "paper_cache.json",
    "journal_update_log": CACHE_DIR / "journal_update_log.json",
}


def _get_snapshot_files():
    """Return the snapshot file mapping, respecting web_server patches for tests."""
    try:
        import web_server
        return web_server.SNAPSHOT_FILES
    except Exception:
        return SNAPSHOT_FILES


def _build_state_snapshot_inline():
    """Build a full state snapshot for export (moved from web_server)."""
    files = {}
    for key, path in _get_snapshot_files().items():
        if path.exists():
            files[key] = safe_load_json(str(path), {})
    return {
        "schema_version": "local-product-state-v1",
        "exported_at": datetime.now().isoformat(),
        "files": files,
        "state_store": _current_state_store().export_state(),
    }


def _build_recommendation_health(cached_papers=None):
    """Build recommendation health diagnostics (moved from web_server)."""
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
    except Exception:
        logger.warning("Could not build recommendation health", exc_info=True)
        return {
            "core_keyword_count": 0,
            "secondary_keyword_count": 0,
            "theory_keyword_count": 0,
            "has_positive_profile": False,
            "zotero": {"enabled": False, "configured_path": "", "path_exists": False},
        }


def _load_history_paper_index():
    """Lightweight inline version of _load_history_paper_index for related-paper lookups."""
    all_papers = {}
    hist_dir = str(HISTORY_DIR)
    if not os.path.exists(hist_dir):
        return all_papers
    for fname in sorted(os.listdir(hist_dir)):
        if not (fname.startswith("digest_") and fname.endswith(".md")):
            continue
        filepath = os.path.join(hist_dir, fname)
        try:
            from utils import parse_markdown_digest_cached
            papers, _ = parse_markdown_digest_cached(filepath)
        except Exception:
            # If web_server is not available, skip history lookup
            continue
        for paper in papers:
            paper_id = paper.get("id")
            if not paper_id or paper_id in all_papers:
                continue
            item = dict(paper)
            item["date"] = fname.replace("digest_", "").replace(".md", "")
            all_papers[paper_id] = item
    return all_papers


# ---------------------------------------------------------------------------
# AI Analysis (already self-contained)
# ---------------------------------------------------------------------------


@bp.get("/api/papers/<paper_id>/analysis")
def get_paper_analysis(paper_id):
    analysis = _ai_analysis_service().get_analysis(paper_id)
    if not analysis:
        return jsonify({"success": False, "error": "analysis_not_found"}), 404
    return jsonify({"success": True, "analysis": analysis})


@bp.post("/api/papers/<paper_id>/analysis/generate")
def generate_paper_analysis(paper_id):
    service = _ai_analysis_service()
    data = request.get_json() or {}
    paper = dict(data.get("paper") or {})
    paper["id"] = paper_id

    # Build structured recommendation reason for the response
    recommendation_reason = None
    try:
        from app.services.scoring_service import build_recommendation_reason
        recommendation_reason = build_recommendation_reason(
            paper,
            user_profile=data.get("user_profile"),
            run_context=data.get("recommendation_context"),
        )
    except Exception:
        pass

    try:
        analysis = service.get_or_create_analysis(
            paper,
            user_profile=data.get("user_profile"),
            recommendation_context=data.get("recommendation_context"),
            force=bool(data.get("force", False)),
        )
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400

    result = {"success": True, "analysis": analysis}
    if recommendation_reason:
        result["recommendation_reason"] = recommendation_reason
    return jsonify(result)


# ---------------------------------------------------------------------------
# Queue (already self-contained via QueueService)
# ---------------------------------------------------------------------------


def _queue_service():
    return QueueService(_current_state_store())


@bp.route("/api/queue", methods=["GET", "POST"])
def manage_queue():
    service = _queue_service()
    if request.method == "GET":
        status = request.args.get("status")
        if status and status not in QUEUE_STATUS_VALUES:
            return jsonify({"success": False, "error": "Invalid status"}), 400
        return jsonify({"success": True, "items": service.list_items(status=status)})

    data = request.get_json() or {}
    paper_id = data.get("paper_id", "")
    status = data.get("status")
    if not paper_id:
        return jsonify({"success": False, "error": "Missing paper_id"}), 400
    if status is None:
        existing = _current_state_store().get_queue_item(paper_id)
        status = existing.get("status") if existing else None
    if status not in QUEUE_STATUS_VALUES:
        return jsonify({"success": False, "error": "Invalid status"}), 400

    item, event_id = service.update_status(
        paper_id,
        status,
        source=data.get("source", "queue_api"),
        note=data.get("note"),
        tags=data.get("tags"),
    )
    return jsonify({"success": True, "item": item, "event_id": event_id})


@bp.post("/api/queue/bulk")
def manage_queue_bulk():
    service = _queue_service()
    data = request.get_json() or {}
    try:
        updated = service.bulk_update_status(
            data.get("paper_ids", []),
            data.get("status"),
            source=data.get("source", "queue_bulk"),
            note=data.get("note", ""),
        )
    except ValueError as exc:
        message = str(exc)
        if "Invalid queue status" in message:
            message = "Invalid status"
        return jsonify({"success": False, "error": message}), 400

    return jsonify({"success": True, "items": updated, "count": len(updated)})


# ---------------------------------------------------------------------------
# Feedback (still bridges to web_server — complex handler)
# ---------------------------------------------------------------------------


def _resolve_path(attr: str, fallback: str) -> str:
    """Resolve a file path, preferring web_server's version for test compatibility."""
    try:
        import web_server
        return getattr(web_server, attr)
    except Exception:
        return fallback


def _settings_service():
    from app.services.settings_service import SettingsService
    return SettingsService()


def _feedback_service():
    from app.services.feedback_service import FeedbackService
    from app.services.scholar_service import ScholarService

    svc = _settings_service()
    return FeedbackService(
        _current_state_store(),
        feedback_file=_resolve_path("FEEDBACK_FILE", FEEDBACK_FILE),
        favorites_file=_resolve_path("FAVORITES_FILE", FAVORITES_FILE),
        cache_file=_resolve_path("CACHE_FILE", CACHE_FILE),
        history_dir=_resolve_path("HISTORY_DIR", str(HISTORY_DIR)),
        scholar_service=ScholarService(_resolve_path("MY_SCHOLARS_FILE", MY_SCHOLARS_FILE)),
        keywords_loader=svc.load_keywords_config,
        keywords_saver=svc.save_keywords_config,
    )


@bp.post("/api/feedback")
def handle_feedback():
    data = request.get_json() or {}
    result, status = _feedback_service().handle_feedback(data)
    return jsonify(result), status


@bp.get("/api/feedback/stats")
def feedback_stats():
    feedback = _feedback_service().load_feedback()
    return jsonify({
        "liked_count": len(feedback.get("liked", [])),
        "disliked_count": len(feedback.get("disliked", [])),
        "total_feedback": len(feedback.get("liked", [])) + len(feedback.get("disliked", [])),
    })


@bp.get("/api/pdf/<paper_id>")
def download_pdf(paper_id):
    import os
    import re
    from flask import send_file

    # Canonicalize and validate the paper_id to prevent path traversal
    paper_id = _canonical_paper_id(paper_id)
    if not re.match(r"^\d{4}\.\d{4,5}$", paper_id):
        return jsonify({"success": False, "error": "Invalid paper ID"}), 400

    pdf_dir = os.path.join(str(PROJECT_ROOT), "cache", "pdfs")
    pdf_path = os.path.join(pdf_dir, f"{paper_id}.pdf")

    # Resolve real paths to prevent path traversal via symlinks or .. segments
    real_pdf_path = os.path.realpath(pdf_path)
    real_pdf_dir = os.path.realpath(pdf_dir)
    if not real_pdf_path.startswith(real_pdf_dir + os.sep):
        return jsonify({"success": False, "error": "Forbidden"}), 403

    if os.path.exists(real_pdf_path):
        return send_file(real_pdf_path, as_attachment=True)
    return f'<script>window.location.href="https://arxiv.org/pdf/{paper_id}.pdf";</script>'


@bp.get("/api/dates")
def get_dates():
    import os, re

    dates = []
    hist_dir = str(HISTORY_DIR)
    if os.path.exists(hist_dir):
        for f in os.listdir(hist_dir):
            if f.startswith("digest_") and f.endswith(".md"):
                date = f.replace("digest_", "").replace(".md", "")
                dates.append(date)
    return jsonify(sorted(dates, reverse=True))


@bp.post("/api/feedback/learn")
def trigger_learning():
    """Trigger feedback learning to update topic weights."""
    try:
        from arxiv_recommender_v5 import FeedbackLearner

        learner = FeedbackLearner(FEEDBACK_FILE, str(CACHE_DIR))
        result = learner.learn_from_feedback(min_feedback=3)

        return jsonify({
            "success": True,
            "status": result.get("status"),
            "feedback_count": result.get("feedback_count", 0),
            "adjustments": result.get("adjustments", {}),
            "liked_topics": result.get("liked_topics", {}),
            "disliked_topics": result.get("disliked_topics", {}),
        })
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@bp.get("/api/citation/<paper_id>")
def get_citation(paper_id):
    """Get citation data for a paper."""
    try:
        from arxiv_recommender_v5 import CitationAnalyzer

        analyzer = CitationAnalyzer(str(CACHE_DIR))
        data = analyzer.fetch_citation_data(paper_id)

        return jsonify({
            "success": True,
            "paper_id": paper_id,
            "citations": data.get("citations", 0),
            "influential_citations": data.get("influential_citations", 0),
            "references": data.get("references", 0),
        })
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@bp.get("/api/fetch_paper/<paper_id>")
def fetch_paper_info(paper_id):
    """Fetch paper info from arXiv API and save to cache."""
    from app.services.arxiv_source import fetch_arxiv_metadata

    try:
        metadata = fetch_arxiv_metadata(paper_id)
        if metadata is None:
            return jsonify({"success": False, "error": "Paper not found"}), 404

        # Save to cache
        cache_path = str(CACHE_DIR / "paper_cache.json")
        paper_cache = safe_load_json(cache_path, {})

        paper_cache[paper_id] = {
            "title": metadata["title"],
            "abstract": metadata["abstract"][:500],
            "authors": ", ".join(metadata["authors"]),
            "date": datetime.now().strftime("%Y-%m-%d"),
            "score": 0,
            "relevance": "从 arXiv 获取",
        }

        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        atomic_write_json(cache_path, paper_cache)

        return jsonify({
            "success": True,
            "paper_id": paper_id,
            "title": metadata["title"],
            "abstract": metadata["abstract"][:500],
            "authors": ", ".join(metadata["authors"]),
        })
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@bp.get("/api/export/bibtex/<paper_id>")
def export_bibtex(paper_id):
    import re

    from app.services.arxiv_source import fetch_arxiv_metadata
    from flask import make_response

    # Canonicalize and validate the paper_id
    paper_id = _canonical_paper_id(paper_id)
    if not re.match(r"^\d{4}\.\d{4,5}$", paper_id):
        return jsonify({"success": False, "error": "Invalid paper ID"}), 400

    try:
        metadata = fetch_arxiv_metadata(paper_id)
        if metadata is None:
            return jsonify({"success": False, "error": "Paper not found"}), 404

        year = metadata.get("published", "")[:4] or str(datetime.now().year)
        author_field = " and ".join(metadata.get("authors", [])) or "Unknown"
        citation_key = re.sub(r"[^a-zA-Z0-9]+", "", paper_id)
        bibtex = (
            f"@article{{arxiv{citation_key},\n"
            f"  title = {{{metadata['title']}}},\n"
            f"  author = {{{author_field}}},\n"
            f"  journal = {{arXiv preprint arXiv:{paper_id}}},\n"
            f"  year = {{{year}}},\n"
            f"  url = {{{metadata['link']}}}\n"
            f"}}\n"
        )

        _current_state_store().record_event("export_to_zotero", paper_id, {"source": "bibtex_export"})

        response = make_response(bibtex, 200)
        response.headers["Content-Type"] = "application/x-bibtex; charset=utf-8"
        response.headers["Content-Disposition"] = f'attachment; filename="{paper_id}.bib"'
        return response
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@bp.get("/api/refresh")
def refresh_recommendations():
    """Force refresh today's recommendations via a background job."""
    force = request.args.get("force", "0") == "1"

    try:
        from arxiv_recommender_v5 import load_daily_recommendation, CONFIG as PIPELINE_CONFIG

        today = datetime.now().strftime("%Y-%m-%d")
        cached_papers, _ = load_daily_recommendation(PIPELINE_CONFIG["cache_dir"])

        if cached_papers and not force:
            return jsonify({
                "success": True,
                "message": "今日推荐已存在",
                "date": today,
                "paper_count": len(cached_papers),
                "job_id": None,
            })

        job = _current_state_store().create_job(
            "daily_recommendation",
            trigger_source="manual_refresh",
            payload={"force_refresh": True, "requested_force": force},
            status="queued",
        )

        def _run_pipeline_bg(run_id, force_refresh):
            try:
                from arxiv_recommender_v5 import run_pipeline

                _current_state_store().update_job(run_id, "running")
                papers = run_pipeline(force_refresh=force_refresh)
                _current_state_store().update_job(
                    run_id,
                    "succeeded",
                    result={
                        "paper_count": len(papers) if papers else 0,
                        "mode": "manual_refresh",
                    },
                )
            except Exception as exc:
                _current_state_store().update_job(run_id, "failed", error_text=str(exc))

        thread = threading.Thread(
            target=_run_pipeline_bg,
            args=(job["run_id"], True),
            daemon=True,
        )
        thread.start()

        return jsonify({
            "success": True,
            "message": "刷新任务已提交",
            "job_id": job["run_id"],
            "date": today,
        })
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@bp.get("/api/status")
def get_status():
    """Get recommendation status for today."""
    try:
        from arxiv_recommender_v5 import load_daily_recommendation, CONFIG as PIPELINE_CONFIG

        today = datetime.now().strftime("%Y-%m-%d")
        cached_papers, cached_themes = load_daily_recommendation(PIPELINE_CONFIG["cache_dir"])
        latest_job = _current_state_store().get_latest_job("daily_recommendation")
        recommendation_health = _build_recommendation_health(cached_papers)

        return jsonify({
            "date": today,
            "has_recommendation": cached_papers is not None,
            "paper_count": len(cached_papers) if cached_papers else 0,
            "themes": cached_themes or [],
            "generated_at": datetime.now().isoformat(),
            "job": serialize_job(latest_job),
            "recommendation_health": recommendation_health,
        })
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


# ---------------------------------------------------------------------------
# State export / import
# ---------------------------------------------------------------------------


@bp.get("/api/state/export")
def export_state_snapshot():
    snapshot = _build_state_snapshot_inline()
    payload = json.dumps(snapshot, ensure_ascii=False, indent=2).encode("utf-8")
    filename = f"arxiv_recommender_snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    return send_file(BytesIO(payload), mimetype="application/json", as_attachment=True, download_name=filename)


@bp.post("/api/state/import")
def import_state_snapshot():
    try:
        if "snapshot" in request.files:
            snapshot = json.load(request.files["snapshot"].stream)
        else:
            snapshot = request.get_json(force=True, silent=False)
        if not isinstance(snapshot, dict):
            return jsonify({"success": False, "error": "Invalid snapshot"}), 400
        if snapshot.get("schema_version") != "local-product-state-v1":
            return jsonify({"success": False, "error": "Unsupported snapshot schema"}), 400

        files = snapshot.get("files", {})
        if not isinstance(files, dict):
            return jsonify({"success": False, "error": "Invalid snapshot files"}), 400
        restored_files = []
        snapshot_file_map = _get_snapshot_files()
        for key, payload in files.items():
            path = snapshot_file_map.get(key)
            if path is None:
                continue
            atomic_write_json(str(path), payload)
            restored_files.append(key)

        state_payload = snapshot.get("state_store")
        if state_payload is not None:
            _current_state_store().import_state(state_payload)

        try:
            from config_manager import reload_config

            reload_config()
        except Exception as exc:
            logger.warning(f"Config reload after snapshot import failed: {exc}")

        return jsonify({
            "success": True,
            "restored_files": restored_files,
            "state_tables": sorted((state_payload or {}).keys()) if isinstance(state_payload, dict) else [],
        })
    except json.JSONDecodeError:
        return jsonify({"success": False, "error": "Snapshot is not valid JSON"}), 400
    except Exception as exc:
        logger.error(f"State import failed: {exc}")
        return jsonify({"success": False, "error": str(exc)}), 500


@bp.get("/api/job/status")
def get_job_status():
    run_id = request.args.get("run_id")
    job_type = request.args.get("job_type", "daily_recommendation")
    job = _current_state_store().get_job(run_id) if run_id else _current_state_store().get_latest_job(job_type)
    return jsonify({"success": True, "job": serialize_job(job)})


# ---------------------------------------------------------------------------
# Collections (self-contained)
# ---------------------------------------------------------------------------


@bp.route("/api/collections", methods=["GET", "POST", "PUT", "DELETE"])
def manage_collections():
    if request.method == "GET":
        collections = [serialize_collection(item) for item in _current_state_store().list_collections()]
        return jsonify({"success": True, "collections": collections})

    data = request.get_json() or {}

    if request.method == "POST":
        name = str(data.get("name", "")).strip()
        if not name:
            return jsonify({"success": False, "error": "Missing collection name"}), 400
        try:
            collection = _current_state_store().create_collection(
                name,
                description=data.get("description", ""),
                query_text=data.get("seed_query", data.get("query_text", "")),
            )
        except sqlite3.IntegrityError:
            return jsonify({"success": False, "error": "Collection name already exists"}), 409
        _current_state_store().record_event(
            "create_collection",
            payload={"collection_id": collection["id"], "name": collection["name"]},
        )
        return jsonify({"success": True, "collection": serialize_collection(collection)})

    if request.method == "PUT":
        collection_id = data.get("collection_id")
        if not collection_id:
            return jsonify({"success": False, "error": "Missing collection_id"}), 400
        try:
            collection = _current_state_store().update_collection(
                int(collection_id),
                name=data.get("name"),
                description=data.get("description"),
                query_text=data.get("seed_query", data.get("query_text")),
                is_active=data.get("is_active"),
            )
        except sqlite3.IntegrityError:
            return jsonify({"success": False, "error": "Collection name already exists"}), 409
        _current_state_store().record_event("update_collection", payload={"collection_id": int(collection_id)})
        return jsonify({"success": True, "collection": serialize_collection(collection)})

    # DELETE
    collection_id = data.get("collection_id")
    if not collection_id:
        return jsonify({"success": False, "error": "Missing collection_id"}), 400
    deleted = _current_state_store().delete_collection(int(collection_id))
    if deleted:
        _current_state_store().record_event("delete_collection", payload={"collection_id": int(collection_id)})
    return jsonify({"success": deleted})


@bp.get("/api/collections/<int:collection_id>")
def get_collection_detail(collection_id):
    collection = _current_state_store().get_collection(collection_id)
    if not collection:
        return jsonify({"success": False, "error": "Collection not found"}), 404
    return jsonify({
        "success": True,
        "collection": serialize_collection(collection),
        "papers": _current_state_store().list_collection_papers(collection_id),
    })


@bp.route("/api/collections/<int:collection_id>/papers", methods=["GET", "POST", "DELETE"])
def add_collection_paper(collection_id):
    if request.method == "GET":
        return jsonify({"success": True, "papers": _current_state_store().list_collection_papers(collection_id)})

    data = request.get_json() or {}
    paper_id = _canonical_paper_id(data.get("paper_id", ""))
    if not paper_id:
        return jsonify({"success": False, "error": "Missing paper_id"}), 400

    if request.method == "DELETE":
        deleted = _current_state_store().remove_paper_from_collection(collection_id, paper_id)
        if deleted:
            _current_state_store().record_event(
                "remove_from_collection",
                paper_id,
                {"collection_id": collection_id, "source": data.get("source", "web_collection")},
            )
        return jsonify({"success": deleted, "collection_id": collection_id, "paper_id": paper_id})

    added = _current_state_store().add_paper_to_collection(collection_id, paper_id, note=data.get("note", ""))
    if not added:
        return jsonify({
            "success": False,
            "error": "Collection not found",
            "collection_id": collection_id,
            "paper_id": paper_id,
        }), 404
    event_id = _current_state_store().record_event(
        "add_to_collection",
        paper_id,
        {"collection_id": collection_id, "note": data.get("note", ""), "source": data.get("source", "web_collection")},
    )
    return jsonify({"success": True, "collection_id": collection_id, "paper_id": paper_id, "event_id": event_id})


# ---------------------------------------------------------------------------
# Saved Searches (self-contained)
# ---------------------------------------------------------------------------


@bp.route("/api/saved-searches", methods=["GET", "POST", "PUT", "DELETE"])
def manage_saved_searches():
    if request.method == "GET":
        searches = [serialize_saved_search(item) for item in _current_state_store().list_saved_searches()]
        return jsonify({"success": True, "saved_searches": searches})

    data = request.get_json() or {}

    if request.method == "POST":
        name = str(data.get("name", "")).strip()
        query_text = str(data.get("query_text", "")).strip()
        if not name or not query_text:
            return jsonify({"success": False, "error": "Missing name or query_text"}), 400
        try:
            saved_search = _current_state_store().create_saved_search(
                name,
                query_text,
                filters={**(data.get("filters") or {}), "description": data.get("description", "")},
            )
        except sqlite3.IntegrityError:
            return jsonify({"success": False, "error": "Saved search name already exists"}), 409
        # Dual-write to unified subscriptions table
        try:
            _current_state_store().create_subscription(
                type="query",
                name=name,
                query_text=query_text,
                payload_json={"filters": data.get("filters") or {}, "description": data.get("description", ""), "legacy_id": saved_search["id"]},
            )
        except Exception:
            pass
        _current_state_store().record_event(
            "create_saved_search",
            payload={"saved_search_id": saved_search["id"], "name": saved_search["name"], "query_text": saved_search["query_text"]},
        )
        return jsonify({"success": True, "saved_search": serialize_saved_search(saved_search)})

    if request.method == "PUT":
        search_id = data.get("search_id")
        if not search_id:
            return jsonify({"success": False, "error": "Missing search_id"}), 400
        try:
            saved_search = _current_state_store().update_saved_search(
                int(search_id),
                name=data.get("name"),
                query_text=data.get("query_text"),
                filters={**(data.get("filters") or {}), "description": data.get("description", "")},
                is_active=data.get("is_active"),
            )
        except sqlite3.IntegrityError:
            return jsonify({"success": False, "error": "Saved search name already exists"}), 409
        _current_state_store().record_event("update_saved_search", payload={"saved_search_id": int(search_id)})
        return jsonify({"success": True, "saved_search": serialize_saved_search(saved_search)})

    # DELETE
    search_id = data.get("search_id")
    if not search_id:
        return jsonify({"success": False, "error": "Missing search_id"}), 400
    deleted = _current_state_store().delete_saved_search(int(search_id))
    if deleted:
        _current_state_store().record_event("delete_saved_search", payload={"saved_search_id": int(search_id)})
    return jsonify({"success": deleted})


@bp.get("/api/saved-searches/<int:search_id>/run")
def run_saved_search(search_id):
    saved_search = _current_state_store().get_saved_search(search_id)
    if not saved_search:
        return jsonify({"success": False, "error": "Saved search not found"}), 404
    try:
        from arxiv_recommender_v5 import search_by_keywords

        query_terms = split_query_terms(saved_search.get("query_text", ""))
        results = search_by_keywords(query_terms, max_results=10, days_back=90)
        _current_state_store().update_saved_search(
            search_id,
            filters={**(saved_search.get("filters_json") or {}), "latest_hit_count": len(results)},
        )
        saved_search = _current_state_store().get_saved_search(search_id)
        _current_state_store().record_event(
            "run_saved_search",
            payload={"saved_search_id": search_id, "query_text": saved_search.get("query_text", "")},
        )
        return jsonify({"success": True, "saved_search": serialize_saved_search(saved_search), "results": results})
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


# ---------------------------------------------------------------------------
# Unified Subscriptions
# ---------------------------------------------------------------------------


def _serialize_subscription(sub):
    item = dict(sub)
    payload = item.get("payload_json") or {}
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            payload = {}
    item["payload"] = payload
    item["filters"] = payload.get("filters", {})
    item["description"] = payload.get("description", "") or payload.get("focus", "")
    return item


@bp.route("/api/subscriptions", methods=["GET", "POST"])
def manage_subscriptions():
    if request.method == "GET":
        sub_type = request.args.get("type")
        subs = [_serialize_subscription(s) for s in _current_state_store().list_subscriptions(type=sub_type)]
        return jsonify({"success": True, "subscriptions": subs})

    data = request.get_json() or {}
    sub_type = str(data.get("type", "query")).strip()
    name = str(data.get("name", "")).strip()
    if not name:
        return jsonify({"success": False, "error": "Missing name"}), 400
    if sub_type not in ("query", "author", "venue"):
        return jsonify({"success": False, "error": "Invalid type"}), 400

    query_text = str(data.get("query_text", "")).strip()
    payload = data.get("payload_json", data.get("payload", {}))
    if isinstance(payload, dict):
        payload = json.dumps(payload, ensure_ascii=False)

    sub = _current_state_store().create_subscription(
        type=sub_type,
        name=name,
        query_text=query_text,
        payload_json=payload,
        enabled=data.get("enabled", True),
    )
    _current_state_store().record_event(
        "subscription_created",
        payload={"subscription_id": sub["id"], "type": sub_type, "name": name},
    )
    return jsonify({"success": True, "subscription": _serialize_subscription(sub)})


@bp.route("/api/subscriptions/<int:sub_id>", methods=["PUT", "DELETE"])
def manage_subscription_item(sub_id):
    if request.method == "DELETE":
        deleted = _current_state_store().delete_subscription(sub_id)
        if deleted:
            _current_state_store().record_event("delete_subscription", payload={"subscription_id": sub_id})
        return jsonify({"success": deleted})

    data = request.get_json() or {}
    kwargs = {}
    for field in ("type", "name", "query_text", "enabled", "latest_hit_count", "last_checked_at"):
        if field in data:
            kwargs[field] = data[field]
    if "payload_json" in data or "payload" in data:
        payload_val = data.get("payload_json", data.get("payload", {}))
        kwargs["payload_json"] = payload_val
    sub = _current_state_store().update_subscription(sub_id, **kwargs)
    if not sub:
        return jsonify({"success": False, "error": "Subscription not found"}), 404
    _current_state_store().record_event("update_subscription", payload={"subscription_id": sub_id})
    return jsonify({"success": True, "subscription": _serialize_subscription(sub)})


@bp.get("/api/subscriptions/<int:sub_id>/hits")
def list_subscription_hits(sub_id):
    sub = _current_state_store().get_subscription(sub_id)
    if not sub:
        return jsonify({"success": False, "error": "Subscription not found"}), 404
    status_filter = request.args.get("status")
    hits = _current_state_store().list_subscription_hits(subscription_id=sub_id, status=status_filter)
    return jsonify({"success": True, "subscription": _serialize_subscription(sub), "hits": hits})


@bp.post("/api/subscriptions/run/<int:sub_id>")
def run_subscription(sub_id):
    sub = _current_state_store().get_subscription(sub_id)
    if not sub:
        return jsonify({"success": False, "error": "Subscription not found"}), 404

    results = []
    sub_type = sub.get("type", "query")
    query_text = sub.get("query_text", "")
    name = sub.get("name", "")

    try:
        from arxiv_recommender_v5 import search_by_keywords
        from app.services.scholar_service import ScholarService

        if sub_type == "query":
            terms = split_query_terms(query_text or name)
            results = search_by_keywords(terms, max_results=10, days_back=90)

        elif sub_type == "author":
            svc = ScholarService(MY_SCHOLARS_FILE)
            papers = svc.fetch_papers(name, max_results=10)
            results = papers

        elif sub_type == "venue":
            # Venue subscriptions search by journal name in arXiv
            terms = split_query_terms(query_text or name)
            results = search_by_keywords(terms, max_results=10, days_back=90)

        now = datetime.now().isoformat()
        queued_count = 0
        for paper in results:
            paper_id = _canonical_paper_id(paper.get("id") or paper.get("arxiv_id") or "")
            if not paper_id:
                continue
            _current_state_store().upsert_subscription_hit(
                subscription_id=sub_id,
                paper_id=paper_id,
                matched_reason=sub_type,
                hit_date=now,
                status="new",
            )
            _current_state_store().record_event(
                "subscription_hit_queued",
                paper_id,
                {"subscription_id": sub_id, "type": sub_type, "hit_date": now},
            )
            queued_count += 1

        _current_state_store().update_subscription(
            sub_id,
            last_checked_at=now,
            latest_hit_count=len(results),
        )
        _current_state_store().record_event(
            "run_subscription",
            payload={"subscription_id": sub_id, "type": sub_type, "hit_count": len(results), "queued_count": queued_count},
        )
        sub = _current_state_store().get_subscription(sub_id)
        return jsonify({
            "success": True,
            "subscription": _serialize_subscription(sub),
            "results": results,
            "hit_count": len(results),
        })
    except ImportError:
        return jsonify({"success": False, "error": "Search module not available"}), 500
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@bp.post("/api/subscriptions/run-all")
def run_all_subscriptions():
    subs = _current_state_store().list_subscriptions()
    enabled_subs = [s for s in subs if s.get("enabled")]
    total_hits = 0
    errors = []

    for sub in enabled_subs:
        sub_id = sub["id"]
        sub_type = sub.get("type", "query")
        query_text = sub.get("query_text", "")
        name = sub.get("name", "")

        try:
            from arxiv_recommender_v5 import search_by_keywords
            from app.services.scholar_service import ScholarService

            results = []
            if sub_type == "query":
                terms = split_query_terms(query_text or name)
                results = search_by_keywords(terms, max_results=10, days_back=90)
            elif sub_type == "author":
                svc = ScholarService(MY_SCHOLARS_FILE)
                results = svc.fetch_papers(name, max_results=10)
            elif sub_type == "venue":
                terms = split_query_terms(query_text or name)
                results = search_by_keywords(terms, max_results=10, days_back=90)

            now = datetime.now().isoformat()
            for paper in results:
                paper_id = _canonical_paper_id(paper.get("id") or paper.get("arxiv_id") or "")
                if not paper_id:
                    continue
                _current_state_store().upsert_subscription_hit(
                    subscription_id=sub_id,
                    paper_id=paper_id,
                    matched_reason=sub_type,
                    hit_date=now,
                    status="new",
                )
                _current_state_store().record_event(
                    "subscription_hit_queued",
                    paper_id,
                    {"subscription_id": sub_id, "type": sub_type, "hit_date": now},
                )

            _current_state_store().update_subscription(
                sub_id,
                last_checked_at=now,
                latest_hit_count=len(results),
            )
            total_hits += len(results)
        except Exception as exc:
            errors.append({"subscription_id": sub_id, "name": name, "error": str(exc)})

    _current_state_store().record_event(
        "run_all_subscriptions",
        payload={"total_hits": total_hits, "subscriptions_checked": len(enabled_subs), "errors": len(errors)},
    )
    return jsonify({
        "success": True,
        "subscriptions_checked": len(enabled_subs),
        "total_hits": total_hits,
        "errors": errors,
    })


# ---------------------------------------------------------------------------
# Keywords / Settings
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
                dislike = {item: -1.0 for item in dislike}
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


@bp.post("/api/settings")
def save_settings():
    """Save user settings and sync to user_profile.json (unified config)."""
    data = request.get_json() or {}

    try:
        from config_manager import get_config, reload_config

        cm = get_config()

        # Parse topics from arrays (new format)
        core_topics = data.get("coreTopics", [])
        secondary_topics = data.get("secondaryTopics", [])
        demote_text = str(data.get("demoteTopics", ""))
        demote_topics = [t.strip() for t in demote_text.split(",") if t.strip()]
        theory_keywords = data.get("theoryKeywords", [])
        dislike_text = data.get("dislikeTopics", "")
        dislike_topics = [t.strip() for t in dislike_text.split(",") if t.strip()]

        # If coreTopics is empty, try legacy format
        if not core_topics:
            priority_text = data.get("priorityTopics", "")
            core_topics = [t.strip() for t in priority_text.split(",") if t.strip()]

        # Clear existing keywords first
        cm._keywords.clear()

        # Set core topics
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

        # Set secondary topics
        secondary_weights = {
            "uniform convergence": 3.0,
            "algorithmic stability": 2.5,
            "empirical risk minimization": 2.0,
            "concentration inequalities": 3.0,
            "learning theory": 2.5,
            "estimation": 0.5,
            "risk bounds": 2.5,
        }
        for topic in secondary_topics:
            weight = secondary_weights.get(topic.lower(), 2.5)
            cm.set_keyword(topic, weight, "secondary", save=False)

        for topic in demote_topics:
            cm.set_keyword(topic, -0.8, "demote", save=False)

        # Set theory keywords in config
        cm._config["theory_keywords"] = theory_keywords

        # Set dislike topics
        for topic in dislike_topics:
            cm.set_keyword(topic, -1.0, "dislike", save=False)

        # Update settings
        cm._settings.papers_per_day = data.get("papersPerDay", 20)
        cm._settings.prefer_theory = data.get("preferTheory", True)
        cm._settings.theory_enabled = data.get("theoryEnabled", True)
        cm._sources.arxiv_enabled = bool(data.get("arxivEnabled", True))
        cm._sources.journal_enabled = bool(data.get("journalEnabled", True))
        cm._sources.scholar_enabled = bool(data.get("scholarEnabled", False))
        cm._sources.lookback_days = int(data.get("lookbackDays", cm._sources.lookback_days or 14))
        cm._zotero.enabled = bool(data.get("zoteroEnabled", True))
        cm._zotero.auto_detect = bool(data.get("zoteroAutoDetect", True))
        cm._zotero.database_path = str(data.get("zoteroPath", cm._zotero.database_path or "")).strip()

        # Save to user_profile.json
        cm.save()

        # Reload config in recommender module
        reload_config()

        logger.info(
            "Saved %d core, %d secondary, %d theory keywords",
            len(core_topics), len(secondary_topics), len(theory_keywords),
        )

        # Regenerate if requested
        regenerate = data.get("regenerate", False)
        regeneration_job = None
        if regenerate:
            try:
                regeneration_job = _current_state_store().create_job(
                    "daily_recommendation",
                    trigger_source="settings_save",
                    payload={"force_refresh": True, "reason": "settings_updated"},
                    status="queued",
                )

                def _run_pipeline_bg(run_id, force_refresh):
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
            "message": f"Saved {len(core_topics)} core, {len(secondary_topics)} secondary, {len(theory_keywords)} theory keywords",
            "core_count": len(core_topics),
            "secondary_count": len(secondary_topics),
            "demote_count": len(demote_topics),
            "theory_count": len(theory_keywords),
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
        import logging
        logging.getLogger(__name__).warning(f"AI connection test failed: {exc}")
        return jsonify({"success": False, "error": str(exc)}), 502


@bp.get("/api/related/<paper_id>")
def get_related_papers(paper_id):
    """Get related papers based on a given paper."""
    from app.services.arxiv_source import fetch_arxiv_metadata

    try:
        # Try to resolve the paper from favorites, history, or arXiv
        paper_info = None
        favorites = _feedback_service().load_favorites()
        history_index = _load_history_paper_index()

        if paper_id in favorites:
            favorite = favorites[paper_id]
            paper_info = {
                "title": favorite.get("title", ""),
                "abstract": favorite.get("abstract", favorite.get("summary", "")),
            }
        elif paper_id in history_index:
            history_paper = history_index[paper_id]
            paper_info = {
                "title": history_paper.get("title", ""),
                "abstract": history_paper.get("abstract", history_paper.get("summary", "")),
            }
        else:
            metadata = fetch_arxiv_metadata(paper_id)
            if metadata is not None:
                paper_info = {
                    "title": metadata.get("title", ""),
                    "abstract": metadata.get("abstract", ""),
                }

        if not paper_info:
            return jsonify({"success": False, "error": "Paper not found", "related": []}), 404

        # Extract keywords from paper
        text = (paper_info.get("title", "") + " " + paper_info.get("abstract", "")).lower()

        # Find important terms
        words = re.findall(r"\b[a-z]+\b", text)
        word_freq = {}
        for w in words:
            if len(w) > 4:  # Skip short words
                word_freq[w] = word_freq.get(w, 0) + 1

        top_keywords = sorted(word_freq.items(), key=lambda x: -x[1])[:5]
        keywords = [k[0] for k in top_keywords]

        # Search for related papers
        from arxiv_recommender_v5 import search_by_keywords

        related = search_by_keywords(keywords, max_results=10, days_back=180)

        # Remove the original paper
        related = [p for p in related if p.get("id") != paper_id][:5]

        return jsonify({"success": True, "related": related, "keywords": keywords})

    except Exception as exc:
        return jsonify({"success": False, "error": str(exc), "related": []}), 500


def _scholar_service():
    from app.services.scholar_service import ScholarService

    return ScholarService(MY_SCHOLARS_FILE)


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
# Inbox Triage
# ---------------------------------------------------------------------------


@bp.get("/api/inbox/progress")
def inbox_progress():
    """Return today's triage progress stats.

    Query params:
        date  — YYYY-MM-DD (defaults to today)
        total — total papers shown on the page (defaults to handled count)
    """
    date_str = request.args.get("date") or datetime.now().strftime("%Y-%m-%d")
    progress = _current_state_store().get_inbox_progress(date_str)
    total_override = request.args.get("total", type=int)
    if total_override is not None and total_override > progress["handled"]:
        progress["total"] = total_override
        progress["untriaged"] = total_override - progress["handled"]
    return jsonify({"success": True, "data": progress})


@bp.post("/api/inbox/triage-complete")
def inbox_triage_complete():
    """Record that the user completed today's inbox triage session."""
    data = request.get_json() or {}
    date_str = data.get("date") or datetime.now().strftime("%Y-%m-%d")
    progress = _current_state_store().get_inbox_progress(date_str)
    total = data.get("total", progress["total"])

    summary = {
        "timestamp": datetime.now().isoformat(),
        "date": date_str,
        "papers_processed": progress["handled"],
        "papers_total": total,
        "papers_liked": progress["liked"],
        "papers_disliked": progress["disliked"],
        "papers_skimmed": progress["skimmed"],
        "papers_deep_read": progress["deep_read"],
        "papers_queued": progress["queued"],
    }

    _current_state_store().record_event(
        "inbox_triage_complete",
        payload=summary,
    )
    return jsonify({"success": True, "message": "Triage session recorded", "summary": summary})


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
        import logging
        logging.getLogger(__name__).error(
            "Failed to save onboarding profile: %s", exc, exc_info=True
        )
        return jsonify({"success": False, "error": str(exc)}), 500


@bp.get("/debug")
def debug_info():
    """Debug endpoint returning system state overview as JSON."""
    try:
        hist_dir = str(HISTORY_DIR)
        dates = []
        if os.path.exists(hist_dir):
            for f in sorted(os.listdir(hist_dir)):
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
