"""Evaluation dashboard viewmodel — runs evaluation and builds context."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from app_paths import CACHE_DIR, HISTORY_DIR, PROJECT_ROOT
from logger_config import get_logger

logger = get_logger(__name__)


class EvalViewModel:
    """Build template context for the evaluation dashboard."""

    def __init__(self, state_store):
        self._store = state_store

    def run_evaluation(self, k_values: str = "5,10,20") -> dict:
        """Run the evaluation CLI and parse the JSON report."""
        try:
            import tempfile
            output_dir = Path(tempfile.mkdtemp(prefix="eval_reports_"))

            result = subprocess.run(
                [
                    sys.executable, "-m", "evaluation.run_evaluation",
                    "--state-db", self._store.db_path,
                    "--cache-dir", str(CACHE_DIR),
                    "--history-dir", str(HISTORY_DIR),
                    "--output-dir", str(output_dir),
                    "--k", k_values,
                ],
                capture_output=True, text=True, timeout=120,
            )

            if result.returncode != 0:
                return {"success": False, "error": result.stderr or result.stdout}

            for line in result.stdout.strip().splitlines():
                try:
                    data = json.loads(line)
                    report_path = data.get("json_report")
                    if report_path:
                        report = json.loads(Path(report_path).read_text(encoding="utf-8"))
                        # Persist report to project reports/ directory
                        self._persist_report(report)
                        return {"success": True, "report": report}
                except (json.JSONDecodeError, OSError):
                    continue

            return {"success": False, "error": "No report found in output"}
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Evaluation timed out"}
        except Exception as e:
            logger.warning(f"Evaluation failed: {e}")
            return {"success": False, "error": str(e)}

    def _persist_report(self, report: dict) -> None:
        """Copy report to PROJECT_ROOT/reports/ for dashboard access."""
        from datetime import datetime
        reports_dir = Path(PROJECT_ROOT) / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = reports_dir / f"eval_report_{timestamp}.json"
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    def list_reports(self) -> list:
        """List evaluation reports from the reports directory."""
        reports_dir = Path(PROJECT_ROOT) / "reports"
        if not reports_dir.exists():
            return []
        reports = []
        for f in sorted(reports_dir.glob("*.json"), reverse=True)[:20]:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                data["_path"] = str(f)
                data["_filename"] = f.name
                reports.append(data)
            except (OSError, json.JSONDecodeError):
                continue
        return reports

    def to_dashboard_context(self) -> dict:
        """Build evaluation dashboard context."""
        from app.viewmodels.shared import assemble_page_context
        from state_store import QUEUE_STATUS_VALUES

        page_ctx = assemble_page_context(self._store, active_tab="settings")

        # Add queue_counts required by base_research.html
        try:
            queue_counts = dict.fromkeys(QUEUE_STATUS_VALUES, 0)
            for item in self._store.list_queue_items():
                status = item.get("status")
                if status in queue_counts:
                    queue_counts[status] += 1
        except Exception:
            queue_counts = {}
        page_ctx.setdefault("queue_counts", queue_counts)
        page_ctx.setdefault("queue_status_values", QUEUE_STATUS_VALUES)

        reports = self.list_reports()
        feedback_auc = self._store.get_feedback_model_auc()
        return {
            "title": "Evaluation Dashboard - arXiv Recommender",
            "reports": reports,
            "has_reports": len(reports) > 0,
            "latest_report": reports[0] if reports else None,
            "feedback_auc": feedback_auc,
            **page_ctx,
        }
