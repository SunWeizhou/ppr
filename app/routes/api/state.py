"""State export/import and job status API routes."""
import json
import logging
from datetime import datetime
from io import BytesIO

from flask import jsonify, request, send_file

from . import bp
from .helpers import _build_state_snapshot_inline, _current_state_store, _get_snapshot_files, serialize_job
from utils import atomic_write_json

logger = logging.getLogger(__name__)


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
