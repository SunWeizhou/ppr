"""Saved Searches API routes."""
import json
import sqlite3

from flask import jsonify, request

from app.services.paper_utils import split_query_terms

from . import bp
from .helpers import _current_state_store, serialize_saved_search


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
        # Dual-write: keep matching subscription in sync
        try:
            saved_search_id = int(search_id)
            subs = _current_state_store().list_subscriptions(type="query")
            for sub in subs:
                payload = sub.get("payload_json") or {}
                if isinstance(payload, str):
                    try:
                        payload = json.loads(payload)
                    except (TypeError, json.JSONDecodeError):
                        payload = {}
                if payload.get("legacy_id") == saved_search_id:
                    name = data.get("name")
                    query_text = data.get("query_text")
                    _current_state_store().update_subscription(
                        sub["id"],
                        name=name or saved_search.get("name", ""),
                        query_text=query_text,
                    )
                    break
        except Exception:
            pass
        return jsonify({"success": True, "saved_search": serialize_saved_search(saved_search)})

    # DELETE
    search_id = data.get("search_id")
    if not search_id:
        return jsonify({"success": False, "error": "Missing search_id"}), 400
    saved_search_id = int(search_id)
    # Delete matching subscription BEFORE saved_search to avoid orphan subscriptions
    try:
        subs = _current_state_store().list_subscriptions(type="query")
        for sub in subs:
            payload = sub.get("payload_json") or {}
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except (TypeError, json.JSONDecodeError):
                    payload = {}
            if payload.get("legacy_id") == saved_search_id:
                _current_state_store().delete_subscription(sub["id"])
                break
    except Exception:
        return jsonify({"success": False, "error": "Failed to sync subscription deletion"}), 500
    deleted = _current_state_store().delete_saved_search(saved_search_id)
    if deleted:
        _current_state_store().record_event("delete_saved_search", payload={"saved_search_id": saved_search_id})
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
