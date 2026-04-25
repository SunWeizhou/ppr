"""CLI for local recommendation evaluation."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from app_paths import CACHE_DIR, HISTORY_DIR, STATE_DB_PATH
from evaluation.ablation import run_ablation
from evaluation.datasets import load_recommendation_runs
from evaluation.labels import build_weak_labels, count_labels
from evaluation.reporting import write_reports
from state_store import StateStore


def _parse_k_values(raw: str) -> list[int]:
    values = []
    for part in str(raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        value = int(part)
        if value <= 0:
            raise ValueError("K values must be positive integers")
        values.append(value)
    return values or [5, 10, 20]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate local recommendation snapshots.")
    parser.add_argument("--state-db", default=str(STATE_DB_PATH), help="Path to SQLite app state database.")
    parser.add_argument("--cache-dir", default=str(CACHE_DIR), help="Path to recommendation cache directory.")
    parser.add_argument("--history-dir", default=str(HISTORY_DIR), help="Path to markdown digest history directory.")
    parser.add_argument("--output-dir", default="reports", help="Directory for JSON and Markdown reports.")
    parser.add_argument("--k", default="5,10,20", help="Comma-separated K values, e.g. 5,10,20.")
    return parser


def build_evaluation_payload(args) -> dict:
    k_values = _parse_k_values(args.k)
    cache_dir = Path(args.cache_dir)
    history_dir = Path(args.history_dir)
    state_store = StateStore(str(args.state_db))
    labels = build_weak_labels(state_store, feedback_path=cache_dir / "user_feedback.json")
    runs = load_recommendation_runs(cache_dir=cache_dir, history_dir=history_dir)
    variants = run_ablation(runs, labels, k_values=k_values)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "input_runs": len(runs),
        "label_counts": count_labels(labels),
        "k_values": k_values,
        "variants": variants,
    }


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        payload = build_evaluation_payload(args)
    except ValueError as exc:
        parser.error(str(exc))
    json_path, markdown_path = write_reports(payload, args.output_dir)
    print(json.dumps({"json_report": str(json_path), "markdown_report": str(markdown_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
