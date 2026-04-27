"""Unified Subscriptions API routes (including hit management)."""
import json
from datetime import datetime

from flask import jsonify, request

from . import bp
from .helpers import _current_state_store, MY_SCHOLARS_FILE
from app.services.paper_utils import split_query_terms
from state_store import _canonical_paper_id


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
# Subscription Hit Management
# ---------------------------------------------------------------------------


@bp.post("/api/subscription-hits/<int:hit_id>/send-to-inbox")
def send_hit_to_inbox(hit_id):
    """Send a subscription hit to the reading queue."""
    from app.services.subscription_service import SubscriptionService

    svc = SubscriptionService(_current_state_store())
    ok = svc.send_hit_to_inbox(hit_id)
    return jsonify({"success": ok})


@bp.post("/api/subscription-hits/<int:hit_id>/ignore")
def ignore_hit(hit_id):
    """Ignore a subscription hit."""
    from app.services.subscription_service import SubscriptionService

    svc = SubscriptionService(_current_state_store())
    ok = svc.ignore_hit(hit_id)
    return jsonify({"success": ok})
