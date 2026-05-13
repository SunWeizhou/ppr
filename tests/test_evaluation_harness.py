"""Evaluation harness for recommendation quality.

Usage:
    python -m pytest tests/test_evaluation_harness.py -v --tb=short

Measures:
    - Top-5 / Top-10 precision against known-relevant papers
    - nDCG@5 and nDCG@10 (Normalized Discounted Cumulative Gain)
    - Coverage across workspace topics
    - Triage acceptance rates (paper added to reading after recommendation)
"""

from __future__ import annotations

import math
import pytest
import tempfile

from app.services.recommendation_workspace_service import RecommendationWorkspaceService


# ---------------------------------------------------------------------------
# Structured relevance labels (F-REC-2: manual labels dataset)
# ---------------------------------------------------------------------------
# Each entry defines a workspace query and graded relevance judgments for
# expected topic dimensions. Labels are 0=irrelevant, 1=related, 2=highly_relevant.

RELEVANCE_LABELS: dict[str, dict[str, int]] = {
    "federated learning privacy": {
        "federated": 2,
        "privacy": 2,
        "differential privacy": 2,
        "secure aggregation": 2,
    },
    "transformer attention mechanism": {
        "transformer": 2,
        "attention": 2,
        "self-attention": 2,
        "machine learning": 1,
    },
}


def _compute_ndcg(relevances: list[float], k: int) -> float:
    """Compute nDCG@k from a list of relevance scores."""
    dcg = sum(rel / math.log2(i + 2) for i, rel in enumerate(relevances[:k]))
    ideal = sorted(relevances, reverse=True)[:k]
    idcg = sum(rel / math.log2(i + 2) for i, rel in enumerate(ideal))
    return dcg / idcg if idcg > 0 else 0.0


def _grade_paper(paper: dict, query: str, labels: dict[str, int]) -> float:
    """Assign a graded relevance score to a paper for a given query."""
    text = (
        (paper.get("title") or "").lower() + " " +
        (paper.get("abstract") or paper.get("summary") or "")[:500].lower()
    )
    max_grade = 0
    for term, grade in labels.get(query, {}).items():
        if term.lower() in text:
            max_grade = max(max_grade, grade)
    return float(max_grade)


# ---------------------------------------------------------------------------
# Fixtures: lightweight test workspaces with manually-labeled relevance
# ---------------------------------------------------------------------------

SAMPLE_WORKSPACES = [
    {
        "id": 99901,
        "query_text": "federated learning privacy",
        "intent_statement": "Federated Learning Privacy",
        "relevant_terms": {"federated", "privacy", "differential privacy", "secure aggregation"},
        "expected_min_count": 3,
    },
    {
        "id": 99902,
        "query_text": "transformer attention mechanism",
        "intent_statement": "Transformer Architectures",
        "relevant_terms": {"transformer", "attention", "self-attention", "bert", "gpt"},
        "expected_min_count": 3,
    },
]


@pytest.fixture
def eval_store():
    """Create a test state store with sample workspaces."""
    from state_store import StateStore
    store = StateStore(db_path=tempfile.mktemp(suffix=".db"))
    for ws in SAMPLE_WORKSPACES:
        store.create_research_question(
            query_text=ws["query_text"],
            intent_statement=ws["intent_statement"],
        )
    return store


@pytest.fixture
def rec_service(eval_store):
    return RecommendationWorkspaceService(eval_store)


# ---------------------------------------------------------------------------
# Recommendation quality metrics
# ---------------------------------------------------------------------------


class TestRecommendationEvaluation:
    """Evaluate recommendation relevance using heuristic keyword matching.

    These are not pass/fail assertions per se — they measure quality and
    log results for manual review.
    """

    def _count_relevant(self, papers: list[dict], relevant_terms: set) -> int:
        """Count papers whose title/abstract match at least one relevant term."""
        count = 0
        for p in papers:
            text = (
                (p.get("title") or "").lower() + " " +
                (p.get("abstract") or p.get("summary") or "")[:500].lower()
            )
            if any(term.lower() in text for term in relevant_terms):
                count += 1
        return count

    def test_top_5_relevance(self, rec_service):
        """Measure top-5 recommendation relevance across workspaces."""
        for ws in SAMPLE_WORKSPACES:
            result = rec_service.run(
                mode="for_you",
                query=ws["query_text"],
                max_results=10,
            )
            papers = result.get("papers", [])
            top5 = papers[:5]
            relevant = self._count_relevant(top5, ws["relevant_terms"])
            _log_eval(
                f"Top-5 precision for '{ws['query_text']}': {relevant}/5 "
                f"({relevant / 5 * 100:.0f}%) — "
                f"{'good' if relevant >= ws['expected_min_count'] else 'needs improvement'}"
            )

    def test_top_10_coverage(self, rec_service):
        """Measure top-10 coverage across workspaces."""
        for ws in SAMPLE_WORKSPACES:
            result = rec_service.run(
                mode="for_you",
                query=ws["query_text"],
                max_results=10,
            )
            papers = result.get("papers", [])
            relevant = self._count_relevant(papers, ws["relevant_terms"])
            _log_eval(
                f"Top-10 coverage for '{ws['query_text']}': {relevant}/10 relevant"
            )

    def test_deduplication(self, rec_service):
        """Verify no duplicate paper_ids appear in recommendation results."""
        for ws in SAMPLE_WORKSPACES:
            result = rec_service.run(
                mode="for_you",
                query=ws["query_text"],
                max_results=10,
            )
            papers = result.get("papers", [])
            ids = [p.get("paper_id") or p.get("id", "") for p in papers]
            unique = set(ids)
            if len(ids) != len(unique):
                dupes = [pid for pid in ids if ids.count(pid) > 1]
                _log_eval(f"DUPLICATES in '{ws['query_text']}': {set(dupes)}")
            assert len(ids) == len(unique), f"Duplicates found: {ids}"

    def test_empty_query_returns_empty(self, rec_service):
        """Empty query with no personalization returns early with needs_profile."""
        result = rec_service.run(mode="for_you", query="", max_results=10)
        assert result.get("needs_profile") or result.get("count", 0) == 0

    def test_section_diversity(self, rec_service):
        """Check that multiple strategy sections are returned."""
        result = rec_service.run(
            mode="for_you",
            query="machine learning transformers",
            max_results=10,
        )
        sections = result.get("sections", [])
        _log_eval(f"Strategy sections returned: {len(sections)}")
        for s in sections:
            _log_eval(f"  - {s.get('strategy', 'unknown')}: {len(s.get('papers', []))} papers")

    def test_ndcg_at_5(self, rec_service):
        """Measure nDCG@5 across sample workspaces (F-REC-2)."""
        for ws in SAMPLE_WORKSPACES:
            result = rec_service.run(
                mode="for_you",
                query=ws["query_text"],
                max_results=10,
            )
            papers = result.get("papers", [])
            grades = [_grade_paper(p, ws["query_text"], RELEVANCE_LABELS) for p in papers[:5]]
            ndcg = _compute_ndcg(grades, 5)
            _log_eval(
                f"nDCG@5 for '{ws['query_text']}': {ndcg:.3f} "
                f"({'good' if ndcg >= 0.5 else 'needs improvement'})"
            )

    def test_ndcg_at_10(self, rec_service):
        """Measure nDCG@10 across sample workspaces (F-REC-2)."""
        for ws in SAMPLE_WORKSPACES:
            result = rec_service.run(
                mode="for_you",
                query=ws["query_text"],
                max_results=10,
            )
            papers = result.get("papers", [])
            grades = [_grade_paper(p, ws["query_text"], RELEVANCE_LABELS) for p in papers[:10]]
            ndcg = _compute_ndcg(grades, 10)
            _log_eval(f"nDCG@10 for '{ws['query_text']}': {ndcg:.3f}")


class TestTriageAcceptance:
    """Measure triage acceptance rates — paper added to reading after recommendation."""

    def _simulate_recommendation_and_triage(
        self, rec_service, query: str, store,
    ) -> dict:
        """Simulate a recommendation run and triage some results."""
        result = rec_service.run(mode="for_you", query=query, max_results=10)
        papers = result.get("papers", [])
        accepted = 0
        for i, p in enumerate(papers):
            if i < max(1, len(papers) // 3):
                store.upsert_queue_item(
                    p.get("paper_id") or p.get("id", ""),
                    "Inbox",
                    source="recommendation_eval",
                )
                accepted += 1
        return {"total": len(papers), "accepted": accepted, "rate": accepted / max(len(papers), 1)}

    def test_triage_acceptance_rate(self, eval_store):
        """Measure triage acceptance rate for recommendations."""
        service = RecommendationWorkspaceService(eval_store)
        for ws in SAMPLE_WORKSPACES:
            result = self._simulate_recommendation_and_triage(
                service, ws["query_text"], eval_store,
            )
            _log_eval(
                f"Triage acceptance for '{ws['query_text']}': "
                f"{result['accepted']}/{result['total']} "
                f"({result['rate'] * 100:.0f}%)"
            )


def _log_eval(message: str):
    """Log an evaluation message that is visible during test runs."""
    import logging
    logging.getLogger(__name__).info(message)
    print(f"[EVAL] {message}")
