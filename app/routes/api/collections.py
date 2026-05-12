"""Collection CRUD API routes."""
import sqlite3

from flask import jsonify, request

from . import bp
from .helpers import _current_state_store, serialize_collection
from state_store import _canonical_paper_id


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


@bp.get("/api/collections/<int:collection_id>/export/bibtex")
def export_collection_bibtex(collection_id):
    store = _current_state_store()
    papers = store.list_collection_papers(collection_id)
    if not papers:
        return jsonify({"success": False, "error": "Collection not found or empty"}), 404

    paper_ids = [p["paper_id"] for p in papers if p.get("paper_id")]
    metadata_map = {}
    if hasattr(store, "list_papers_by_ids") and paper_ids:
        try:
            metadata_map = {m["paper_id"]: m for m in store.list_papers_by_ids(paper_ids)}
        except Exception:
            pass

    collection = store.get_collection(collection_id)
    name = collection.get("name", "collection") if collection else "collection"
    entries = []
    for p in papers:
        pid = p.get("paper_id", "")
        meta = metadata_map.get(pid, {})
        title = meta.get("title") or pid
        authors = meta.get("authors") or "Unknown"
        year = (meta.get("published_at") or meta.get("published") or "2025")[:4]
        entries.append(
            f"@article{{{pid},\n"
            f"  title = {{{title}}},\n"
            f"  author = {{{authors}}},\n"
            f"  year = {{{year}}},\n"
            f"  note = {{Exported from Paper Agent collection: {name}}}\n"
            f"}}"
        )
    bibtex = "\n\n".join(entries)
    return bibtex, 200, {"Content-Type": "text/plain; charset=utf-8",
                          "Content-Disposition": f"attachment; filename={name}.bib"}
