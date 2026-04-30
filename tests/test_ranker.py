"""Tests for app/services/ranker.py."""

import unittest
from unittest.mock import patch, MagicMock

import numpy as np

from app.services.ranker import (
    keyword_score,
    author_score,
    semantic_score,
    feedback_score,
    subscription_score,
    score_paper,
    explain,
    matched_keywords,
)


def _make_paper(
    title: str = "Some Title",
    abstract: str = "Some abstract here.",
    authors: list[str] | None = None,
    comment: str = "",
    paper_id: str = "2401.99999",
) -> dict:
    return {
        "id": paper_id,
        "title": title,
        "abstract": abstract,
        "authors": authors or ["Jane Doe"],
        "comment": comment,
        "categories": ["cs.LG"],
        "published": "2024-01-15T00:00:00Z",
    }


class TestKeywordScore(unittest.TestCase):
    def test_title_match(self) -> None:
        """Keyword in title scores strictly above zero."""
        paper = _make_paper(title="Deep Learning for NLP")
        score = keyword_score(paper, ["deep learning"])
        self.assertGreater(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_no_match(self) -> None:
        """No keyword match returns 0.0."""
        paper = _make_paper(title="Something Else", abstract="Unrelated content.")
        score = keyword_score(paper, ["quantum"])
        self.assertEqual(score, 0.0)

    def test_multiple_hits(self) -> None:
        """Multiple keywords produce a higher score than a single hit."""
        paper = _make_paper(
            title="Deep Learning Advances",
            abstract="NLP methods with transformers.",
        )
        single = keyword_score(paper, ["deep learning"])
        multi = keyword_score(paper, ["deep learning", "nlp", "transformers"])
        self.assertGreater(multi, single)
        self.assertLessEqual(multi, 1.0)


class TestAuthorScore(unittest.TestCase):
    def setUp(self) -> None:
        self._patcher = patch("state_store.get_state_store")
        self._mock_get_store = self._patcher.start()
        self._mock_store = MagicMock()
        self._mock_store.list_subscriptions.return_value = []
        self._mock_get_store.return_value = self._mock_store

    def tearDown(self) -> None:
        self._patcher.stop()

    def test_known_author(self) -> None:
        """Known author contributes 0.4."""
        paper = _make_paper(authors=["Peter Bartlett"])
        score = author_score(paper)
        self.assertGreaterEqual(score, 0.4)

    def test_top_venue(self) -> None:
        """Top venue in comment contributes 0.3."""
        paper = _make_paper(comment="Published at NeurIPS 2024")
        score = author_score(paper)
        self.assertGreaterEqual(score, 0.3)

    def test_top_institution(self) -> None:
        """Top institution in affiliation contributes 0.3."""
        paper = _make_paper(comment="Stanford University research")
        score = author_score(paper)
        self.assertGreaterEqual(score, 0.3)

    def test_no_match(self) -> None:
        """No author/institution/venue match returns 0.0."""
        paper = _make_paper(
            authors=["John Doe"],
            comment="",
        )
        score = author_score(paper)
        self.assertEqual(score, 0.0)


class TestSemanticScore(unittest.TestCase):
    def test_no_embeddings(self) -> None:
        """Returns 0.0 when library_embeddings is None or empty."""
        self.assertEqual(semantic_score({}, None), 0.0)
        self.assertEqual(semantic_score({}, []), 0.0)

    @patch("app.services.embedding_service.EmbeddingService")
    def test_empty_paper_returns_zero(self, mock_emb_svc_cls: MagicMock) -> None:
        """Paper without id/embedding returns 0.0 even with embeddings."""
        mock_svc = MagicMock()
        mock_svc.embed_paper.return_value = []
        mock_emb_svc_cls.return_value = mock_svc
        self.assertEqual(semantic_score({}, [[0.1, 0.2]]), 0.0)

    @patch("app.services.embedding_service.EmbeddingService")
    def test_with_embeddings(self, mock_emb_svc_cls: MagicMock) -> None:
        """Real cosine similarity with library embeddings."""
        mock_svc = MagicMock()
        mock_svc.embed_paper.return_value = [1.0, 0.0, 0.0]
        mock_emb_svc_cls.return_value = mock_svc

        paper = {"id": "2401.10000", "title": "Test", "abstract": "Test."}
        score = semantic_score(paper, [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
        self.assertGreater(score, 0.0)
        self.assertLessEqual(score, 1.0)


class TestFeedbackScore(unittest.TestCase):
    def test_no_model(self) -> None:
        """Returns 0.0 when model is None."""
        self.assertEqual(feedback_score({}, None), 0.0)

    @patch("app.services.embedding_service.EmbeddingService")
    def test_with_model_real(self, mock_emb_svc_cls: MagicMock) -> None:
        """Real feedback_score uses predict_proba with paper embedding."""
        mock_svc = MagicMock()
        mock_svc.embed_paper.return_value = [0.5, 0.5, 0.5]
        mock_emb_svc_cls.return_value = mock_svc

        mock_model = MagicMock()
        mock_model.predict_proba.return_value = np.array([[0.3, 0.7]])

        paper = {"id": "2401.10001", "title": "Test"}
        score = feedback_score(paper, mock_model)
        self.assertAlmostEqual(score, 0.7)


class TestSubscriptionScore(unittest.TestCase):
    def test_hit(self) -> None:
        """Matching subscription query adds 0.3."""
        paper = _make_paper(title="Graph Neural Networks", abstract="GNN research.")
        subs = [{"query_text": "graph neural"}]
        score = subscription_score(paper, subs)
        self.assertAlmostEqual(score, 0.3)

    def test_no_match(self) -> None:
        """Empty or None subscriptions returns 0.0."""
        paper = _make_paper()
        self.assertEqual(subscription_score(paper, None), 0.0)
        self.assertEqual(subscription_score(paper, []), 0.0)

    def test_multiple_hits_capped(self) -> None:
        """Multiple matching subscriptions cap at 1.0."""
        paper = _make_paper(
            title="ABC DEF GHI JKL",
            abstract="MNO PQR STU VWX",
        )
        subs = [
            {"query_text": "abc"},
            {"query_text": "ghi"},
            {"query_text": "mno"},
            {"query_text": "vwx"},
        ]
        score = subscription_score(paper, subs)
        self.assertAlmostEqual(score, 1.0)


class TestScorePaper(unittest.TestCase):
    def setUp(self) -> None:
        self._patcher = patch("state_store.get_state_store")
        self._mock_get_store = self._patcher.start()
        self._mock_store = MagicMock()
        self._mock_store.list_subscriptions.return_value = []
        self._mock_get_store.return_value = self._mock_store

        self._emb_patcher = patch("app.services.embedding_service.EmbeddingService")
        self._mock_emb_svc_cls = self._emb_patcher.start()
        self._mock_emb_svc = MagicMock()
        self._mock_emb_svc.embed_paper.return_value = [0.5, 0.5, 0.5]
        self._mock_emb_svc_cls.return_value = self._mock_emb_svc

    def tearDown(self) -> None:
        self._emb_patcher.stop()
        self._patcher.stop()

    def test_keyword_only(self) -> None:
        """Only keywords available — score based solely on keyword signal."""
        paper = _make_paper(title="Reinforcement Learning", abstract="RL methods.")
        ctx = {"keywords": ["reinforcement learning"]}
        score, explanation = score_paper(paper, ctx)
        self.assertGreater(score, 0.0)
        self.assertIn("关键词", explanation)

    def test_empty_ctx(self) -> None:
        """Empty context still works — falls back to author signals."""
        paper = _make_paper(authors=["John Doe"])
        score, explanation = score_paper(paper, {})
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)
        self.assertIsInstance(explanation, str)

    def test_with_subscriptions(self) -> None:
        """Subscriptions in ctx contribute to the score."""
        paper = _make_paper(title="Quantum Computing", abstract="Quantum theory.")
        ctx = {
            "keywords": [],
            "subscriptions": [{"query_text": "quantum"}],
        }
        score, explanation = score_paper(paper, ctx)
        self.assertGreater(score, 0.0)
        self.assertIn("订阅", explanation)

    def test_with_library_embeddings(self) -> None:
        """library_embeddings in ctx produces a real semantic signal."""
        paper = _make_paper(title="ML Paper", abstract="Machine learning.")
        ctx = {
            "keywords": ["machine learning"],
            "library_embeddings": [[0.5, 0.5, 0.5]],
        }
        score, explanation = score_paper(paper, ctx)
        self.assertGreater(score, 0.0)
        # Library signal is higher than keyword signal for this config
        self.assertIn("论文库", explanation)

    def test_with_feedback_model(self) -> None:
        """feedback_model + high AUC in ctx produces a real feedback signal."""
        mock_model = MagicMock()
        mock_model.predict_proba.return_value = np.array([[0.2, 0.8]])

        paper = _make_paper(title="Deep Learning", abstract="Neural networks.")
        ctx = {
            "keywords": ["deep learning"],
            "feedback_model": mock_model,
            "feedback_model_auc": 0.6,
        }
        score, explanation = score_paper(paper, ctx)
        self.assertGreater(score, 0.0)
        # Feedback signal is higher than keyword signal for this config
        self.assertIn("标记相关", explanation)


class TestExplain(unittest.TestCase):
    def test_keyword(self) -> None:
        """Strongest signal is keyword — returns keyword explanation."""
        signals = [("keyword", 0.9)]
        paper = _make_paper(title="Deep Learning")
        ctx = {"keywords": ["deep learning"]}
        result = explain(signals, paper, ctx)
        self.assertIn("关键词", result)
        self.assertLessEqual(len(result), 35)

    def test_no_signals(self) -> None:
        """No signals returns default explanation."""
        result = explain([], {}, {})
        self.assertEqual(result, "基于你的研究领域")
        self.assertLessEqual(len(result), 35)


class TestMatchedKeywords(unittest.TestCase):
    def test_title_match(self) -> None:
        """Keyword in title is returned."""
        paper = _make_paper(title="Deep Learning Advances")
        result = matched_keywords(paper, ["deep learning", "nlp"])
        self.assertEqual(result, ["deep learning"])

    def test_abstract_match(self) -> None:
        """Keyword in abstract is returned."""
        paper = _make_paper(title="Advances", abstract="NLP methods.")
        result = matched_keywords(paper, ["nlp", "transformers"])
        self.assertEqual(result, ["nlp"])

    def test_no_match(self) -> None:
        """No keywords match returns empty list."""
        paper = _make_paper(title="Something")
        result = matched_keywords(paper, ["quantum"])
        self.assertEqual(result, [])

    def test_empty_keywords(self) -> None:
        """Empty keywords list returns empty list."""
        paper = _make_paper(title="Anything")
        result = matched_keywords(paper, [])
        self.assertEqual(result, [])
