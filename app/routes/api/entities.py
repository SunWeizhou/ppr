"""Entity REST API endpoints."""
import json

from flask import jsonify, request

from . import bp
from .helpers import _current_state_store


def _serialize_entity(entity):
    """Serialize an entity dict for JSON response."""
    item = dict(entity)
    for key in ("aliases", "external_ids", "metadata_json", "stats_json"):
        val = item.get(key)
        if isinstance(val, str):
            try:
                item[key] = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                item[key] = [] if key == "aliases" else {}
    return item


@bp.route("/api/entities", methods=["GET"])
def list_entities():
    """List entities, optionally filtered by type or search query."""
    entity_type = request.args.get("type")
    search = request.args.get("search", "").strip()
    limit = int(request.args.get("limit", 100))

    store = _current_state_store()
    if search:
        entities = store.list_entities(entity_type=entity_type, search=search, limit=limit)
    else:
        entities = store.list_entities(entity_type=entity_type, limit=limit)

    return jsonify({
        "success": True,
        "entities": [_serialize_entity(e) for e in entities],
    })


@bp.route("/api/entities", methods=["POST"])
def create_entity():
    """Create or update an entity."""
    data = request.get_json() or {}

    entity_type = str(data.get("type", "")).strip()
    name = str(data.get("name", "")).strip()
    if not entity_type or not name:
        return jsonify({"success": False, "error": "Missing type or name"}), 400

    from app.services.entity_service import EntityService
    svc = EntityService(_current_state_store())

    try:
        entity = svc.get_or_create(
            entity_type=entity_type,
            name=name,
            external_ids=data.get("external_ids"),
            metadata_json=data.get("metadata"),
            aliases=data.get("aliases"),
        )
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400

    _current_state_store().record_event(
        "entity_created",
        payload={"entity_id": entity["id"], "type": entity_type, "name": name},
    )
    return jsonify({"success": True, "entity": _serialize_entity(entity)})


@bp.route("/api/entities/<path:entity_id>", methods=["GET"])
def get_entity(entity_id):
    """Get a single entity by ID."""
    entity = _current_state_store().get_entity(entity_id)
    if not entity:
        return jsonify({"success": False, "error": "Entity not found"}), 404

    from app.services.entity_service import EntityService
    svc = EntityService(_current_state_store())
    related = svc.get_related_entities(entity_id, limit=10)

    return jsonify({
        "success": True,
        "entity": _serialize_entity(entity),
        "related_entities": [_serialize_entity(r) for r in related],
    })


@bp.route("/api/entities/<path:entity_id>", methods=["PUT"])
def update_entity(entity_id):
    """Update an entity's metadata."""
    data = request.get_json() or {}
    store = _current_state_store()

    kwargs = {}
    if "name" in data:
        kwargs["name"] = data["name"]
    if "aliases" in data:
        kwargs["aliases"] = data["aliases"]
    if "external_ids" in data:
        kwargs["external_ids"] = data["external_ids"]
    if "metadata" in data:
        kwargs["metadata_json"] = data["metadata"]
    if "stats" in data:
        kwargs["stats_json"] = data["stats"]

    entity = store.update_entity(entity_id, **kwargs)
    if not entity:
        return jsonify({"success": False, "error": "Entity not found"}), 404

    return jsonify({"success": True, "entity": _serialize_entity(entity)})


@bp.route("/api/entities/<path:entity_id>", methods=["DELETE"])
def delete_entity(entity_id):
    """Delete an entity."""
    store = _current_state_store()
    deleted = store.delete_entity(entity_id)
    if deleted:
        store.record_event("entity_deleted", payload={"entity_id": entity_id})
    return jsonify({"success": deleted})


@bp.route("/api/entities/<path:entity_id>/sync", methods=["POST"])
def sync_entity_metadata(entity_id):
    """Trigger metadata sync from external APIs."""
    from app.services.entity_service import EntityService
    svc = EntityService(_current_state_store())

    entity = svc.sync_metadata(entity_id)
    if not entity:
        return jsonify({"success": False, "error": "Entity not found"}), 404

    return jsonify({"success": True, "entity": _serialize_entity(entity)})


@bp.route("/api/entities/<path:entity_id>/subscribe", methods=["POST"])
def subscribe_to_entity(entity_id):
    """Create a subscription linked to this entity."""
    data = request.get_json() or {}

    from app.services.entity_service import EntityService
    svc = EntityService(_current_state_store())

    try:
        sub = svc.subscribe(
            entity_id=entity_id,
            filters=data.get("filters"),
            research_question_id=data.get("research_question_id"),
        )
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400

    _current_state_store().record_event(
        "entity_subscribed",
        payload={"entity_id": entity_id, "subscription_id": sub["id"]},
    )
    return jsonify({"success": True, "subscription": sub})


@bp.route("/api/entities/<path:entity_id>/relations", methods=["GET"])
def list_entity_relations(entity_id):
    """List relations for an entity."""
    direction = request.args.get("direction", "both")
    relation_type = request.args.get("relation_type")

    relations = _current_state_store().list_entity_relations(
        entity_id, direction=direction, relation_type=relation_type
    )
    return jsonify({"success": True, "relations": relations})
