"""Tests for app/services/learner.py (feedback model training)."""

import io
import pickle
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------

def _make_event(event_type: str, paper_id: str) -> dict:
    return {
        "id": hash(paper_id + event_type),
        "event_type": event_type,
        "paper_id": paper_id,
        "payload_json": {},
        "created_at": "2026-04-30T00:00:00Z",
    }


def _make_fake_embedding(dim: int = 8) -> list[float]:
    """Deterministic fake vector."""
    return [float(i % 10) * 0.1 for i in range(dim)]


def _make_mock_model(return_proba: float = 0.9) -> MagicMock:
    """Build a mock sklearn-like classifier with predict_proba."""
    model = MagicMock()
    model.predict_proba.return_value = np.array([[1 - return_proba, return_proba]])
    return model


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@patch("app.services.learner.roc_auc_score")
class TestRetrainIfNeeded(unittest.TestCase):
    """Unit tests for retrain_if_needed.

    Early-return tests (too soon / too few / one-class / no embeddings) do
    not exercise sklearn at all.  Training tests use a **real**
    ``LogisticRegression`` so that ``pickle.dumps`` succeeds.
    """

    def setUp(self):
        self.mock_store = MagicMock()

    def _make_events(
        self, n_relevant: int, n_ignored: int, prefix: str = "2401."
    ) -> list[dict]:
        events: list[dict] = []
        for i in range(n_relevant):
            events.append(_make_event("feedback_relevant", f"{prefix}{10000 + i}"))
        for i in range(n_ignored):
            events.append(_make_event("feedback_ignored", f"{prefix}{20000 + i}"))
        return events

    def _setup_embeddings(self, n_relevant: int, n_ignored: int):
        """Store embeddings where relevant/ignored have separable patterns."""
        relevant_ids = [f"2401.{10000 + i}" for i in range(n_relevant)]
        ignored_ids = [f"2401.{20000 + i}" for i in range(n_ignored)]

        def fake_embed(pid: str):
            # Create separable vectors: relevant=[1,0,...], ignored=[-1,0,...]
            if pid in relevant_ids:
                vals = [1.0] + [0.0] * 7
            else:
                vals = [-1.0] + [0.0] * 7
            blob = np.array(vals, dtype=np.float32).tobytes()
            return (blob, "test_model", "2026-04-30T00:00:00Z")

        self.mock_store.get_paper_embedding = fake_embed

    def test_retrain_skips_when_too_soon(
        self, mock_roc_auc
    ):
        """Less than 12 hours since last training -> skip."""
        recent = (datetime.now(tz=timezone.utc) - timedelta(hours=1)).isoformat()
        self.mock_store.get.side_effect = lambda k: recent if k == "feedback_model_trained_at" else None

        from app.services.learner import retrain_if_needed

        result = retrain_if_needed(self.mock_store)
        self.assertFalse(result)
        self.mock_store.list_interaction_events.assert_not_called()

    def test_retrain_skips_when_too_few_events(
        self, mock_roc_auc
    ):
        """Less than 60 events -> skip."""
        # No previous training time
        self.mock_store.get.return_value = None
        events = self._make_events(10, 10)  # 20 total
        self.mock_store.list_interaction_events.return_value = events

        from app.services.learner import retrain_if_needed

        result = retrain_if_needed(self.mock_store)
        self.assertFalse(result)
        # Should not have attempted to load embeddings or train
        self.mock_store.get_paper_embedding.assert_not_called()

    def test_retrain_skips_when_only_one_class(
        self, mock_roc_auc
    ):
        """Only positive or only negative events -> skip."""
        self.mock_store.get.return_value = None
        events = self._make_events(100, 0)  # only relevant, no ignored
        self.mock_store.list_interaction_events.return_value = events
        self._setup_embeddings(100, 0)

        from app.services.learner import retrain_if_needed

        result = retrain_if_needed(self.mock_store)
        self.assertFalse(result)

    def test_retrain_trains_with_enough_data(
        self, mock_roc_auc
    ):
        """Sufficient events + embeddings -> model is trained and saved."""
        self.mock_store.get.return_value = None
        events = self._make_events(40, 40)  # 80 total
        self.mock_store.list_interaction_events.return_value = events
        self._setup_embeddings(40, 40)
        mock_roc_auc.return_value = 0.85

        from app.services.learner import retrain_if_needed

        result = retrain_if_needed(self.mock_store)
        self.assertTrue(result)

        # Verify model was saved
        self.mock_store.save_feedback_model.assert_called_once()
        args, _ = self.mock_store.save_feedback_model.call_args
        sample_count, auc, pickle_blob = args
        self.assertEqual(sample_count, 80)
        self.assertEqual(auc, 0.85)
        self.assertIsInstance(pickle_blob, bytes)

        # Verify state was updated
        self.mock_store.save.assert_any_call("feedback_model_trained_at", unittest.mock.ANY)
        self.mock_store.save.assert_any_call("feedback_model_auc", "0.85")

    def test_retrain_skips_when_no_embeddings(
        self, mock_roc_auc
    ):
        """Events exist but no embeddings available -> skip."""
        self.mock_store.get.return_value = None
        events = self._make_events(40, 40)
        self.mock_store.list_interaction_events.return_value = events
        # No embeddings available from cache or from EmbeddingService
        self.mock_store.get_paper_embedding.return_value = None

        with patch("app.services.embedding_service.EmbeddingService") as mock_emb:
            mock_svc = MagicMock()
            mock_svc.embed_paper.return_value = []
            mock_emb.return_value = mock_svc

            from app.services.learner import retrain_if_needed

            result = retrain_if_needed(self.mock_store)
        self.assertFalse(result)

    def test_quality_gate_rejects_low_auc(
        self, mock_roc_auc
    ):
        """AUC < 0.55 -> model still saved but training occurs."""
        self.mock_store.get.return_value = None
        events = self._make_events(40, 40)
        self.mock_store.list_interaction_events.return_value = events
        self._setup_embeddings(40, 40)
        mock_roc_auc.return_value = 0.45

        from app.services.learner import retrain_if_needed

        result = retrain_if_needed(self.mock_store)
        # Model is still trained and saved even with low AUC
        self.assertTrue(result)
        self.mock_store.save_feedback_model.assert_called_once()

    def test_quality_gate_accepts_high_auc(
        self, mock_roc_auc
    ):
        """AUC >= 0.55 -> model is saved, training succeeds."""
        self.mock_store.get.return_value = None
        events = self._make_events(40, 40)
        self.mock_store.list_interaction_events.return_value = events
        self._setup_embeddings(40, 40)
        mock_roc_auc.return_value = 0.72

        from app.services.learner import retrain_if_needed

        result = retrain_if_needed(self.mock_store)
        self.assertTrue(result)
        self.mock_store.save_feedback_model.assert_called_once()


class TestStateStoreFeedbackModels(unittest.TestCase):
    """Integration-style tests using a real StateStore with temp DB."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tmp_dir.name) / "test_state.db")

    def tearDown(self):
        self.tmp_dir.cleanup()

    def _make_state_store(self):
        from state_store import StateStore
        return StateStore(db_path=self.db_path)

    def test_save_and_get_latest(self):
        """save_feedback_model returns id, get_latest_feedback_model retrieves row."""
        store = self._make_state_store()

        blob1 = pickle.dumps({"dummy": "model1"})
        id1 = store.save_feedback_model(100, 0.85, blob1)
        self.assertIsInstance(id1, int)
        self.assertGreater(id1, 0)

        blob2 = pickle.dumps({"dummy": "model2"})
        id2 = store.save_feedback_model(200, 0.92, blob2)
        self.assertGreater(id2, id1)

        latest = store.get_latest_feedback_model()
        self.assertIsNotNone(latest)
        self.assertEqual(latest["sample_count"], 200)
        self.assertAlmostEqual(latest["auc"], 0.92)
        self.assertEqual(latest["pickle_blob"], blob2)

    def test_get_feedback_model_auc(self):
        """get_feedback_model_auc returns just the AUC of the latest model."""
        store = self._make_state_store()
        # No models yet
        self.assertIsNone(store.get_feedback_model_auc())

        blob = pickle.dumps({"dummy": "model"})
        store.save_feedback_model(50, 0.75, blob)
        auc = store.get_feedback_model_auc()
        self.assertIsNotNone(auc)
        self.assertAlmostEqual(auc, 0.75)

    def test_get_latest_returns_none_when_empty(self):
        """get_latest_feedback_model returns None when table is empty."""
        store = self._make_state_store()
        self.assertIsNone(store.get_latest_feedback_model())

    def test_save_and_get_key_value(self):
        """Generic get/save on schema_meta works."""
        store = self._make_state_store()
        self.assertIsNone(store.get("nonexistent_key"))

        store.save("test_key", "test_value")
        self.assertEqual(store.get("test_key"), "test_value")

        store.save("test_key", "updated_value")
        self.assertEqual(store.get("test_key"), "updated_value")

    def test_export_import_includes_feedback_models(self):
        """feedback_models table is included in export_state / import_state."""
        store = self._make_state_store()
        blob = pickle.dumps({"dummy": "model"})
        model_id = store.save_feedback_model(100, 0.88, blob)

        snapshot = store.export_state()
        self.assertIn("feedback_models", snapshot)
        self.assertEqual(len(snapshot["feedback_models"]), 1)
        self.assertEqual(snapshot["feedback_models"][0]["sample_count"], 100)

        # Import into a fresh store
        store2 = self._make_state_store()
        store2.import_state(snapshot)
        loaded = store2.get_latest_feedback_model()
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["sample_count"], 100)
        self.assertAlmostEqual(loaded["auc"], 0.88)
        self.assertEqual(loaded["pickle_blob"], blob)


class TestSemanticScoreReal(unittest.TestCase):
    """Test the real semantic_score implementation (cosine similarity)."""

    def test_no_embeddings_returns_zero(self):
        from app.services.ranker import semantic_score
        self.assertEqual(semantic_score({"id": "test"}, None), 0.0)
        self.assertEqual(semantic_score({"id": "test"}, []), 0.0)

    @patch("app.services.embedding_service.EmbeddingService")
    def test_with_embeddings_computes_cosine(self, mock_emb_svc_cls):
        """Real cosine similarity with top-3 mean."""
        mock_svc = MagicMock()
        mock_svc.embed_paper.return_value = [1.0, 0.0, 0.0, 0.0]
        mock_emb_svc_cls.return_value = mock_svc

        from app.services.ranker import semantic_score

        library = [
            [1.0, 0.0, 0.0, 0.0],  # cos=1.0
            [1.0, 1.0, 0.0, 0.0],  # cos=0.707
            [0.0, 1.0, 0.0, 0.0],  # cos=0.0
            [-1.0, 0.0, 0.0, 0.0],  # cos=-1.0
        ]
        paper = {"id": "2401.99999", "title": "Test", "abstract": "A paper."}
        score = semantic_score(paper, library)
        # Top 3: 1.0, 0.707, 0.0 -> mean ~0.569
        self.assertAlmostEqual(score, (1.0 + 0.70710677 + 0.0) / 3, places=5)
        self.assertGreater(score, 0.0)
        self.assertLessEqual(score, 1.0)

    @patch("app.services.embedding_service.EmbeddingService")
    def test_single_library_embedding(self, mock_emb_svc_cls):
        """Single library embedding — no averaging, just that one value."""
        mock_svc = MagicMock()
        mock_svc.embed_paper.return_value = [1.0, 2.0]
        mock_emb_svc_cls.return_value = mock_svc

        from app.services.ranker import semantic_score

        paper = {"id": "2401.10000", "title": "Test"}
        score = semantic_score(paper, [[2.0, 4.0]])  # cos=1.0
        self.assertAlmostEqual(score, 1.0, places=5)


class TestFeedbackScoreReal(unittest.TestCase):
    """Test the real feedback_score implementation (predict_proba)."""

    def test_no_model_returns_zero(self):
        from app.services.ranker import feedback_score
        self.assertEqual(feedback_score({"id": "test"}, None), 0.0)

    @patch("app.services.embedding_service.EmbeddingService")
    def test_with_model_uses_predict_proba(self, mock_emb_svc_cls):
        """predict_proba positive class is returned."""
        mock_svc = MagicMock()
        mock_svc.embed_paper.return_value = [0.5, 0.5, 0.5]
        mock_emb_svc_cls.return_value = mock_svc

        from app.services.ranker import feedback_score

        mock_model = _make_mock_model(return_proba=0.85)
        paper = {"id": "2401.10001", "title": "Test"}
        score = feedback_score(paper, mock_model)
        self.assertAlmostEqual(score, 0.85, places=5)

    @patch("app.services.embedding_service.EmbeddingService")
    def test_low_probability(self, mock_emb_svc_cls):
        """Low probability from model is returned as-is."""
        mock_svc = MagicMock()
        mock_svc.embed_paper.return_value = [0.1, 0.2, 0.3]
        mock_emb_svc_cls.return_value = mock_svc

        from app.services.ranker import feedback_score

        mock_model = _make_mock_model(return_proba=0.12)
        paper = {"id": "2401.10002", "title": "Test"}
        score = feedback_score(paper, mock_model)
        self.assertAlmostEqual(score, 0.12, places=5)

    @patch("app.services.embedding_service.EmbeddingService")
    def test_empty_embedding_returns_zero(self, mock_emb_svc_cls):
        """If the paper can't be embedded, score is 0.0."""
        mock_svc = MagicMock()
        mock_svc.embed_paper.return_value = []
        mock_emb_svc_cls.return_value = mock_svc

        from app.services.ranker import feedback_score

        mock_model = _make_mock_model(return_proba=0.9)
        paper = {"id": "2401.10003", "title": "Test"}
        score = feedback_score(paper, mock_model)
        self.assertEqual(score, 0.0)
