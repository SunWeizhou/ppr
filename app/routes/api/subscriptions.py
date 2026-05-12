"""Unified Subscriptions API routes (including hit management)."""
import json

from flask import jsonify, request

from . import bp
from .helpers import _current_state_store


def _serialize_subscription(sub):
    item = dict(sub)
    payload = item.get("payload_json") or {}
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            payload = {}
    item["payload"] = payload
    item["filters"] = item.get("filters_json") or {}
    if isinstance(item["filters"], str):
        try:
            item["filters"] = json.loads(item["filters"])
        except (json.JSONDecodeError, TypeError):
            item["filters"] = {}
    item["description"] = payload.get("description", "") or payload.get("focus", "")

    # Include linked entity data if present
    entity_id = item.get("entity_id")
    if entity_id:
        entity = _current_state_store().get_entity(entity_id)
        item["entity"] = dict(entity) if entity else None
    else:
        item["entity"] = None

    return item


def _optional_int(value):
    if value in (None, ""):
        return None
    return int(value)


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
    if sub_type not in ("query", "author", "venue", "field", "entity"):
        return jsonify({"success": False, "error": "Invalid type"}), 400

    query_text = str(data.get("query_text", "")).strip()
    payload = data.get("payload_json", data.get("payload", {}))
    if isinstance(payload, dict):
        payload = json.dumps(payload, ensure_ascii=False)

    # Entity and filter support
    entity_id = data.get("entity_id")
    filters = data.get("filters_json", data.get("filters"))
    filters_json = None
    if filters is not None:
        filters_json = filters if isinstance(filters, str) else json.dumps(filters, ensure_ascii=False)

    try:
        research_question_id = _optional_int(data.get("research_question_id"))
        sub = _current_state_store().create_subscription(
            type=sub_type,
            name=name,
            query_text=query_text,
            payload_json=payload,
            enabled=data.get("enabled", True),
            research_question_id=research_question_id,
            entity_id=entity_id,
            filters_json=filters_json,
        )
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    _current_state_store().record_event(
        "subscription_created",
        payload={"subscription_id": sub["id"], "type": sub_type, "name": name, "entity_id": entity_id},
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
    if "research_question_id" in data:
        try:
            kwargs["research_question_id"] = _optional_int(data.get("research_question_id"))
        except ValueError:
            return jsonify({"success": False, "error": "Invalid research_question_id"}), 400
    if "entity_id" in data:
        kwargs["entity_id"] = data["entity_id"]
    if "filters_json" in data or "filters" in data:
        filters = data.get("filters_json", data.get("filters", {}))
        kwargs["filters_json"] = filters if isinstance(filters, str) else json.dumps(filters, ensure_ascii=False)
    try:
        sub = _current_state_store().update_subscription(sub_id, **kwargs)
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
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
@bp.post("/api/subscriptions/<int:sub_id>/run")
def run_subscription(sub_id):
    from app.services.subscription_runner import SubscriptionRunner

    runner = SubscriptionRunner(_current_state_store())
    result = runner.run_subscription(sub_id)

    if not result.get("success"):
        error = result.get("error", "Unknown error")
        return jsonify({"success": False, "error": error}), 500

    sub = _current_state_store().get_subscription(sub_id)
    return jsonify({
        "success": True,
        "subscription": _serialize_subscription(sub) if sub else None,
        "hit_count": result.get("hit_count", 0),
    })


@bp.post("/api/subscriptions/run-all")
def run_all_subscriptions():
    from app.services.subscription_runner import SubscriptionRunner

    runner = SubscriptionRunner(_current_state_store())
    result = runner.run_all_subscriptions()

    return jsonify({
        "success": result.get("success", True),
        "subscriptions_checked": result.get("subscriptions_checked", 0),
        "total_hits": result.get("total_hits", 0),
        "errors": result.get("errors", []),
    })


# ---------------------------------------------------------------------------
# Subscription Hit Management
# ---------------------------------------------------------------------------


@bp.post("/api/subscription-hits/<int:hit_id>/send-to-inbox")
def send_hit_to_inbox(hit_id):
    """Send a subscription hit to the reading queue."""
    from app.services.subscription_runner import SubscriptionRunner

    runner = SubscriptionRunner(_current_state_store())
    ok = runner.send_hit_to_inbox(hit_id)
    return jsonify({"success": ok})


@bp.post("/api/subscription-hits/<int:hit_id>/ignore")
def ignore_hit(hit_id):
    """Ignore a subscription hit."""
    from app.services.subscription_runner import SubscriptionRunner

    runner = SubscriptionRunner(_current_state_store())
    ok = runner.ignore_hit(hit_id)
    return jsonify({"success": ok})
