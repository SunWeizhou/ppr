"""Entity profile page routes."""
from flask import Blueprint, render_template, abort

bp = Blueprint("entities", __name__)


@bp.route("/entities/<path:entity_id>")
def entity_profile(entity_id):
    """Render entity profile page with type-specific content."""
    from state_store import get_state_store
    from app.services.entity_service import EntityService

    store = get_state_store()
    svc = EntityService(store)

    entity = store.get_entity(entity_id)
    if not entity:
        abort(404)

    # Get related entities
    related = svc.get_related_entities(entity_id, limit=10)

    # Get subscriptions linked to this entity
    all_subs = store.list_subscriptions()
    entity_subs = [s for s in all_subs if s.get("entity_id") == entity_id]

    # Get recent papers from subscription hits
    recent_papers = []
    for sub in entity_subs:
        hits = store.list_subscription_hits(subscription_id=sub["id"], limit=10)
        for hit in hits:
            paper_meta = store.get_paper_metadata(hit.get("paper_id", ""))
            recent_papers.append({
                "paper_id": hit.get("paper_id", ""),
                "title": (paper_meta or {}).get("title", hit.get("paper_id", "")),
                "authors": (paper_meta or {}).get("authors", []),
                "year": (paper_meta or {}).get("year"),
                "hit_date": hit.get("hit_date", ""),
                "matched_reason": hit.get("matched_reason", ""),
            })

    metadata = entity.get("metadata_json") or {}
    if isinstance(metadata, str):
        import json
        try:
            metadata = json.loads(metadata)
        except (json.JSONDecodeError, TypeError):
            metadata = {}

    return render_template(
        "entity_profile.html",
        entity=entity,
        entity_type=entity["type"],
        metadata=metadata,
        related_entities=related,
        entity_subs=entity_subs,
        recent_papers=recent_papers[:20],
        is_subscribed=len(entity_subs) > 0,
    )
