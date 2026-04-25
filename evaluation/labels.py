"""Weak-label construction from local-first state sources."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

from state_store import _canonical_paper_id


@dataclass
class WeakLabel:
    paper_id: str
    label: str
    weight: float
    sources: list[str] = field(default_factory=list)


POSITIVE_WEIGHTS = {
    "relevant": 1.0,
    "skim_later": 1.25,
    "saved": 1.75,
    "deep_read": 2.0,
}
NEGATIVE_WEIGHT = -1.0
PROTECTED_POSITIVES = {"deep_read", "saved"}


def _event_label(event_type: str) -> Optional[tuple[str, float]]:
    normalized = str(event_type or "").strip().lower()
    if normalized in {"like", "relevant"}:
        return "relevant", POSITIVE_WEIGHTS["relevant"]
    if normalized in {"dislike", "ignored", "ignore", "ignore_topic"}:
        return "ignored", NEGATIVE_WEIGHT
    if normalized == "save_for_later":
        return "skim_later", POSITIVE_WEIGHTS["skim_later"]
    if normalized == "deep_read":
        return "deep_read", POSITIVE_WEIGHTS["deep_read"]
    if normalized == "save":
        return "saved", POSITIVE_WEIGHTS["saved"]
    return None


def _queue_label(status: str) -> tuple[str, float]:
    if status == "Skim Later":
        return "skim_later", POSITIVE_WEIGHTS["skim_later"]
    if status == "Deep Read":
        return "deep_read", POSITIVE_WEIGHTS["deep_read"]
    if status == "Saved":
        return "saved", POSITIVE_WEIGHTS["saved"]
    if status == "Archived":
        return "neutral", 0.0
    if status == "Inbox":
        return "neutral", 0.0
    return "neutral", 0.0


def _merge_label(labels: Dict[str, WeakLabel], paper_id: str, label: str, weight: float, source: str) -> None:
    canonical_id = _canonical_paper_id(paper_id)
    if not canonical_id:
        return

    current = labels.get(canonical_id)
    if current is None:
        labels[canonical_id] = WeakLabel(canonical_id, label, weight, [source])
        return

    current.sources.append(source)
    if label == "neutral":
        return
    if label == "ignored":
        if current.label not in PROTECTED_POSITIVES:
            current.label = label
            current.weight = weight
        return
    if current.label == "ignored" and label not in PROTECTED_POSITIVES:
        return
    if weight > current.weight:
        current.label = label
        current.weight = weight


def _load_legacy_feedback(feedback_path: Optional[Path]) -> dict:
    if not feedback_path:
        return {}
    path = Path(feedback_path)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def build_weak_labels(state_store, feedback_path: Optional[Path] = None) -> Dict[str, WeakLabel]:
    """Build per-paper weak labels from SQLite state and legacy feedback JSON."""
    labels: Dict[str, WeakLabel] = {}
    snapshot = state_store.export_state()

    for item in snapshot.get("reading_queue_items", []):
        paper_id = item.get("paper_id", "")
        label, weight = _queue_label(item.get("status", ""))
        _merge_label(labels, paper_id, label, weight, f"queue:{item.get('status', '')}")

    for event in snapshot.get("interaction_events", []):
        paper_id = event.get("paper_id", "")
        event_type = event.get("event_type", "")
        mapped = _event_label(event_type)
        if mapped:
            label, weight = mapped
            _merge_label(labels, paper_id, label, weight, f"event:{event_type}")

    feedback = _load_legacy_feedback(feedback_path)
    for paper_id in feedback.get("liked", []):
        _merge_label(labels, paper_id, "relevant", POSITIVE_WEIGHTS["relevant"], "feedback:liked")
    for paper_id in feedback.get("disliked", []):
        _merge_label(labels, paper_id, "ignored", NEGATIVE_WEIGHT, "feedback:disliked")

    return labels


def count_labels(labels: Dict[str, WeakLabel]) -> dict:
    counts = {"relevant": 0, "skim_later": 0, "deep_read": 0, "saved": 0, "ignored": 0, "neutral": 0}
    for label in labels.values():
        counts[label.label] = counts.get(label.label, 0) + 1
    return counts

