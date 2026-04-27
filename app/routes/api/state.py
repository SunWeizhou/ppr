"""State export/import, backup/restore, health, and job status API routes."""
import io
import json
import logging
import os
import zipfile
from datetime import datetime
from io import BytesIO

from flask import jsonify, request, send_file

from app_paths import PROJECT_ROOT, STATE_DB_PATH
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


@bp.post("/api/state/backup")
def backup_state():
    """Create a full backup zip containing all state files."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        # user config files
        for fname in ['user_profile.json', 'user_config.json', 'keywords_config.json', 'my_scholars.json']:
            path = os.path.join(str(PROJECT_ROOT), fname)
            if os.path.exists(path):
                zf.write(path, fname)

        # SQLite database
        db_path = str(STATE_DB_PATH)
        if os.path.exists(db_path):
            zf.write(db_path, 'cache/app_state.db')

        # reports
        reports_dir = os.path.join(str(PROJECT_ROOT), 'reports')
        if os.path.exists(reports_dir):
            for root, _dirs, files in os.walk(reports_dir):
                for f in files:
                    full = os.path.join(root, f)
                    arcname = os.path.join('reports', os.path.relpath(full, reports_dir))
                    zf.write(full, arcname)

        # history
        history_dir = os.path.join(str(PROJECT_ROOT), 'history')
        if os.path.exists(history_dir):
            for root, _dirs, files in os.walk(history_dir):
                for f in files:
                    full = os.path.join(root, f)
                    arcname = os.path.join('history', os.path.relpath(full, history_dir))
                    zf.write(full, arcname)

    buf.seek(0)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return send_file(
        buf,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f'ppr_backup_{timestamp}.zip'
    )


@bp.post("/api/state/restore")
def restore_state_from_backup():
    """Restore state from a backup zip file."""
    if 'backup' not in request.files:
        return jsonify({"success": False, "error": "No backup file provided"}), 400

    file = request.files['backup']
    try:
        with zipfile.ZipFile(io.BytesIO(file.read())) as zf:
            for member in zf.namelist():
                target = os.path.join(str(PROJECT_ROOT), member)
                if member.startswith('cache/'):
                    target = os.path.join(str(PROJECT_ROOT), member)
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with zf.open(member) as src, open(target, 'wb') as dst:
                    dst.write(src.read())
    except zipfile.BadZipFile:
        return jsonify({"success": False, "error": "Invalid backup file"}), 400

    return jsonify({"success": True, "message": "State restored. Please restart the application."})


@bp.get("/api/state/health")
def system_health():
    """Return system health information."""
    store = _current_state_store()
    db_path = str(STATE_DB_PATH)
    db_size = os.path.getsize(db_path) if os.path.exists(db_path) else 0

    counts = {}
    with store._lock, store._connect() as conn:
        for table in ['recommendation_runs', 'recommendation_items', 'reading_queue_items',
                       'research_collections', 'subscriptions', 'interaction_events',
                       'paper_ai_analyses']:
            try:
                row = conn.execute(f"SELECT COUNT(*) as cnt FROM {table}").fetchone()
                counts[table] = row['cnt'] if row else 0
            except Exception:
                counts[table] = -1

        schema_row = conn.execute("SELECT value FROM schema_meta WHERE key='schema_version'").fetchone()
        schema_version = schema_row['value'] if schema_row else 'unknown'

    last_run = store.get_latest_job("daily_recommendation")
    last_run_time = last_run.get('created_at') if last_run else None

    return jsonify({
        "success": True,
        "health": {
            "db_path": db_path,
            "db_size_bytes": db_size,
            "db_size_mb": round(db_size / (1024 * 1024), 2) if db_size else 0,
            "schema_version": schema_version,
            "table_counts": counts,
            "last_recommendation_run": last_run_time,
        }
    })


@bp.post("/api/state/vacuum")
def vacuum_database():
    """Run VACUUM on the SQLite database."""
    store = _current_state_store()
    with store._lock, store._connect() as conn:
        conn.execute("VACUUM")
    return jsonify({"success": True, "message": "Database vacuumed successfully."})


@bp.get("/api/state/data-folder")
def get_data_folder():
    return jsonify({"success": True, "path": str(PROJECT_ROOT)})
