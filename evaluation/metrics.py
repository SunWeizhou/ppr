"""Ranking metrics for recommendation evaluation."""

from __future__ import annotations

import math
from typing import Dict, Iterable, List

from state_store import _canonical_paper_id

from evaluation.labels import WeakLabel


POSITIVE_LABELS = {"relevant", "skim_later", "deep_read", "saved"}


def _paper_id(paper: dict) -> str:
    return _canonical_paper_id(paper.get("id") or paper.get("paper_id") or "")


def _top_labels(ranked_papers: List[dict], labels: Dict[str, WeakLabel], k: int) -> list[WeakLabel]:
    top = ranked_papers[:k]
    return [labels.get(_paper_id(paper), WeakLabel(_paper_id(paper), "neutral", 0.0, [])) for paper in top]


def _rate(items: Iterable[WeakLabel], predicate, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return sum(1 for item in items if predicate(item)) / denominator


def _dcg(gains: list[float]) -> float:
    return sum(gain / math.log2(index + 2) for index, gain in enumerate(gains))


def evaluate_ranked_papers(
    ranked_papers: List[dict],
    labels: Dict[str, WeakLabel],
    *,
    k_values: List[int],
) -> dict:
    """Evaluate one ranked list against weak labels."""
    metrics = {}
    paper_count = len(ranked_papers)

    for k in k_values:
        denominator = min(k, paper_count)
        top_labels = _top_labels(ranked_papers, labels, k)
        metrics[f"Relevant@{k}"] = _rate(top_labels, lambda item: item.label in POSITIVE_LABELS, denominator)
        metrics[f"DeepRead@{k}"] = _rate(top_labels, lambda item: item.label == "deep_read", denominator)
        metrics[f"Ignored@{k}"] = _rate(top_labels, lambda item: item.label == "ignored", denominator)

        gains = [max(item.weight, 0.0) for item in top_labels]
        ideal_gains = sorted(
            [max(labels.get(_paper_id(paper), WeakLabel("", "neutral", 0.0, [])).weight, 0.0) for paper in ranked_papers],
            reverse=True,
        )[:k]
        ideal = _dcg(ideal_gains)
        metrics[f"NDCG@{k}"] = (_dcg(gains) / ideal) if ideal > 0 else 0.0

    metrics["MRR"] = 0.0
    for index, paper in enumerate(ranked_papers, start=1):
        label = labels.get(_paper_id(paper))
        if label and label.label in POSITIVE_LABELS:
            metrics["MRR"] = 1.0 / index
            break

    return metrics

