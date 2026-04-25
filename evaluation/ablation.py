"""Ablation runner for current recommendation snapshots."""

from __future__ import annotations

from typing import Dict, List

from app.services.scoring_service import ScoringVariant, score_papers_for_evaluation
from evaluation.labels import WeakLabel
from evaluation.metrics import evaluate_ranked_papers


VARIANTS = [
    ScoringVariant.KEYWORDS_ONLY,
    ScoringVariant.KEYWORDS_SEMANTIC,
    ScoringVariant.KEYWORDS_SEMANTIC_FEEDBACK,
    ScoringVariant.FULL_SCORER,
]


def _empty_metrics(k_values: list[int]) -> dict:
    metrics = {"MRR": 0.0}
    for k in k_values:
        metrics[f"Relevant@{k}"] = 0.0
        metrics[f"DeepRead@{k}"] = 0.0
        metrics[f"Ignored@{k}"] = 0.0
        metrics[f"NDCG@{k}"] = 0.0
    return metrics


def _average(metric_sets: list[dict], k_values: list[int]) -> dict:
    if not metric_sets:
        return _empty_metrics(k_values)
    keys = sorted(metric_sets[0])
    return {
        key: sum(metrics.get(key, 0.0) for metrics in metric_sets) / len(metric_sets)
        for key in keys
    }


def run_ablation(
    recommendation_runs: List[dict],
    labels: Dict[str, WeakLabel],
    *,
    k_values: list[int],
) -> dict:
    """Evaluate all scoring variants over recommendation runs."""
    results = {}
    for variant in VARIANTS:
        per_run_metrics = []
        paper_count = 0
        for run in recommendation_runs:
            papers = run.get("papers", [])
            if not papers:
                continue
            ranked = score_papers_for_evaluation(papers, variant, labels=labels)
            per_run_metrics.append(evaluate_ranked_papers(ranked, labels, k_values=k_values))
            paper_count += len(papers)

        results[variant.value] = {
            "run_count": len(per_run_metrics),
            "paper_count": paper_count,
            "metrics": _average(per_run_metrics, k_values),
        }

    return results

