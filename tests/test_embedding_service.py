"""Unit tests for the v2 EmbeddingService and paper_embeddings table.

Tests are isolated from real model downloads by mocking
``sentence_transformers.SentenceTransformer``.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

import numpy as np

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_model(return_vector: list[float]):
    """Build a mock ``SentenceTransformer`` instance.

    ``encode(text)`` returns ``return_vector`` unchanged for a single string,
    and returns ``[return_vector, ...]`` for a list of strings.
    """
    model = MagicMock()
    arr = np.array(return_vector, dtype=np.float32)

    def mock_encode(texts, batch_size=None, show_progress_bar=False):
        if isinstance(texts, str):
            return arr.copy()
        return np.array([arr.copy() for _ in texts])

    model.encode = mock_encode
    return model


def _fake_vector(dim: int = 1024) -> list[float]:
    """Generate a deterministic fake vector of length ``dim``."""
    return [float(i % 10) * 0.1 for i in range(dim)]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class EmbeddingServiceTests(unittest.TestCase):
    """Test the EmbeddingService with a mocked sentence-transformers model."""

    def setUp(self):
        # Fresh temporary database for each test
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tmp_dir.name) / "test_state.db")

        # Patch StateStore before any import touches it
        from state_store import StateStore, _state_store

        # Clear the module-level singleton so get_state_store() picks up our
        # patched version
        self._orig_state_store = _state_store
        from state_store import _state_store as _st_mod

        # Build our own store with the temp db path
        self.store = StateStore(self.db_path)

        # Patch get_state_store globally to return our isolated store
        self._patcher = patch("app.services.embedding_service.get_state_store",
                              return_value=self.store)
        self._patcher.start()

        # Also clear the global model cache so each test starts fresh
        import app.services.embedding_service as emb_mod
        emb_mod._CACHED_MODEL = None
        emb_mod._CACHED_MODEL_NAME = None

    def tearDown(self):
        self._patcher.stop()
        self.tmp_dir.cleanup()

    # ------------------------------------------------------------------
    # StateStore: paper_embeddings table
    # ------------------------------------------------------------------

    def test_state_store_save_and_get(self):
        """Verify paper_embeddings table operations."""
        paper_id = "2604.11111"
        vec = _fake_vector(1024)
        blob = np.array(vec, dtype=np.float32).tobytes()
        model_name = "BAAI/bge-large-en-v1.5"

        self.store.save_paper_embedding(paper_id, blob, model_name)

        result = self.store.get_paper_embedding(paper_id)
        self.assertIsNotNone(result)
        blob_back, model_back, created_at = result
        self.assertEqual(blob, blob_back)
        self.assertEqual(model_back, model_name)
        self.assertIsNotNone(created_at)

        # Round-trip via numpy
        vec_back = np.frombuffer(blob_back, dtype=np.float32).tolist()
        self.assertEqual(len(vec_back), len(vec))
        # Use numpy's allclose to handle float32 precision loss
        self.assertTrue(np.allclose(np.array(vec, dtype=np.float32), np.array(vec_back, dtype=np.float32)))

    def test_state_store_get_nonexistent(self):
        """get_paper_embedding returns None for missing paper."""
        result = self.store.get_paper_embedding("9999.99999")
        self.assertIsNone(result)

    def test_state_store_get_all_for_model(self):
        """get_all_embeddings_for_model returns only matching model."""
        v1 = _fake_vector(1024)
        v2 = _fake_vector(1024)
        self.store.save_paper_embedding(
            "2604.11111", np.array(v1, dtype=np.float32).tobytes(), "model-a"
        )
        self.store.save_paper_embedding(
            "2604.22222", np.array(v2, dtype=np.float32).tobytes(), "model-a"
        )
        self.store.save_paper_embedding(
            "2604.33333", np.array(v1, dtype=np.float32).tobytes(), "model-b"
        )

        results = self.store.get_all_embeddings_for_model("model-a")
        self.assertEqual(len(results), 2)
        paper_ids = {r[0] for r in results}
        self.assertIn("2604.11111", paper_ids)
        self.assertIn("2604.22222", paper_ids)

    def test_state_store_canonical_id(self):
        """paper_embeddings uses canonical paper IDs."""
        self.store.save_paper_embedding(
            "2604.11111v3",
            np.array(_fake_vector(1024), dtype=np.float32).tobytes(),
            "test-model",
        )
        result = self.store.get_paper_embedding("2604.11111")
        self.assertIsNotNone(result)

        result_v = self.store.get_paper_embedding("2604.11111v3")
        self.assertIsNotNone(result_v)  # canonicalization makes both the same

    # ------------------------------------------------------------------
    # EmbeddingService: embed_text
    # ------------------------------------------------------------------

    @patch("sentence_transformers.SentenceTransformer")
    def test_embed_text_returns_1024d_vector(self, mock_st_class):
        """embed_text returns a 1024-dim list[float]."""
        expected = _fake_vector(1024)
        mock_model = _make_mock_model(expected)
        mock_st_class.return_value = mock_model

        from app.services.embedding_service import EmbeddingService

        svc = EmbeddingService("test-model")
        result = svc.embed_text("test text")

        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1024)
        self.assertAlmostEqual(result[0], expected[0])
        self.assertAlmostEqual(result[-1], expected[-1])

    @patch("sentence_transformers.SentenceTransformer")
    def test_embed_text_empty_without_model(self, mock_st_class):
        """embed_text returns [] when the model fails to load."""
        mock_st_class.side_effect = ImportError("no module")

        from app.services.embedding_service import EmbeddingService

        svc = EmbeddingService("missing-model")
        result = svc.embed_text("test")
        self.assertEqual(result, [])

    # ------------------------------------------------------------------
    # EmbeddingService: embed_paper with caching
    # ------------------------------------------------------------------

    @patch("sentence_transformers.SentenceTransformer")
    def test_embed_paper_caches_in_state_store(self, mock_st_class):
        """First call computes and caches; second call reads from cache."""
        expected = _fake_vector(1024)
        mock_model = _make_mock_model(expected)
        mock_st_class.return_value = mock_model

        from app.services.embedding_service import EmbeddingService

        svc = EmbeddingService("test-model")

        paper = {"id": "2604.11111", "title": "Test Paper", "abstract": "An abstract."}

        # First call — should compute and cache
        vec1 = svc.embed_paper(paper)
        self.assertEqual(len(vec1), 1024)

        # Verify it was stored in the DB
        cached = self.store.get_paper_embedding("2604.11111")
        self.assertIsNotNone(cached)
        self.assertEqual(cached[1], "test-model")

        # Change the mock to return a different vector; second call should still
        # return the cached value
        different = _fake_vector(1024)
        different[0] = 99.9
        mock_model.encode = lambda texts, **kw: np.array(
            [np.array(different, dtype=np.float32) for _ in (texts if isinstance(texts, list) else [texts])]
        )

        vec2 = svc.embed_paper(paper)
        self.assertEqual(vec2, vec1)  # cached, not re-computed

    @patch("sentence_transformers.SentenceTransformer")
    def test_embed_paper_no_id_returns_empty(self, mock_st_class):
        """embed_paper returns [] when paper has no id."""
        from app.services.embedding_service import EmbeddingService

        svc = EmbeddingService("test-model")
        result = svc.embed_paper({"title": "No ID"})
        self.assertEqual(result, [])

    # ------------------------------------------------------------------
    # EmbeddingService: embed_papers_batch
    # ------------------------------------------------------------------

    @patch("sentence_transformers.SentenceTransformer")
    def test_embed_papers_batch(self, mock_st_class):
        """Batch processing handles cached + uncached papers."""
        expected = _fake_vector(1024)
        mock_model = _make_mock_model(expected)
        mock_st_class.return_value = mock_model

        from app.services.embedding_service import EmbeddingService

        svc = EmbeddingService("test-model")

        # Pre-cache paper 1
        paper1_vec = np.array(expected, dtype=np.float32).tobytes()
        self.store.save_paper_embedding("2604.11111", paper1_vec, "test-model")

        papers = [
            {"id": "2604.11111", "title": "Cached Paper"},
            {"id": "2604.22222", "title": "New Paper", "abstract": "Fresh abstract."},
            {"id": "2604.33333", "title": "Another New Paper"},
        ]

        results = svc.embed_papers_batch(papers)

        self.assertIn("2604.11111", results)
        self.assertIn("2604.22222", results)
        self.assertIn("2604.33333", results)
        # New papers should now be cached
        self.assertIsNotNone(self.store.get_paper_embedding("2604.22222"))
        self.assertIsNotNone(self.store.get_paper_embedding("2604.33333"))

    @patch("sentence_transformers.SentenceTransformer")
    def test_embed_papers_batch_all_cached(self, mock_st_class):
        """Batch processing should not call model.encode when all are cached."""
        expected = _fake_vector(1024)
        mock_model = _make_mock_model(expected)
        mock_st_class.return_value = mock_model

        from app.services.embedding_service import EmbeddingService

        svc = EmbeddingService("test-model")

        # Cache all papers
        for pid in ["2604.11111", "2604.22222"]:
            blob = np.array(expected, dtype=np.float32).tobytes()
            self.store.save_paper_embedding(pid, blob, "test-model")

        papers = [
            {"id": "2604.11111", "title": "P1"},
            {"id": "2604.22222", "title": "P2"},
        ]

        # embed will call encode only for new papers — since all are cached,
        # encode should not be called
        results = svc.embed_papers_batch(papers)
        self.assertEqual(len(results), 2)

    # ------------------------------------------------------------------
    # EmbeddingService: compute_library_embeddings
    # ------------------------------------------------------------------

    @patch("sentence_transformers.SentenceTransformer")
    def test_compute_library_embeddings(self, mock_st_class):
        """compute_library_embeddings returns embeddings in the same order."""
        expected = _fake_vector(1024)
        mock_model = _make_mock_model(expected)
        mock_st_class.return_value = mock_model

        from app.services.embedding_service import EmbeddingService

        svc = EmbeddingService("test-model")

        papers = [
            {"id": "2604.11111", "title": "Paper A"},
            {"id": "2604.22222", "title": "Paper B"},
        ]

        embs = svc.compute_library_embeddings(papers)
        self.assertEqual(len(embs), 2)
        self.assertEqual(len(embs[0]), 1024)

    # ------------------------------------------------------------------
    # Graceful fallback
    # ------------------------------------------------------------------

    @patch("sentence_transformers.SentenceTransformer")
    def test_no_model_returns_empty(self, mock_st_class):
        """If model loading fails, all methods return empty results."""
        mock_st_class.side_effect = ImportError("no module")

        from app.services.embedding_service import EmbeddingService

        svc = EmbeddingService("missing-model")

        self.assertEqual(svc.embed_text("hello"), [])
        self.assertEqual(svc.embed_paper({"id": "1", "title": "x"}), [])
        self.assertEqual(svc.embed_papers_batch([{"id": "1", "title": "x"}]), {})
        self.assertEqual(svc.compute_library_embeddings([{"id": "1", "title": "x"}]), [])

    # ------------------------------------------------------------------
    # Lazy loading
    # ------------------------------------------------------------------

    def test_lazy_loading(self):
        """Model is not loaded on import or instantiation."""
        from app.services.embedding_service import EmbeddingService

        svc = EmbeddingService("test-lazy-model")
        # Model should not be loaded yet
        self.assertIsNone(svc._model)
        self.assertFalse(svc._load_attempted)

    @patch("sentence_transformers.SentenceTransformer")
    def test_lazy_loading_only_on_first_embed(self, mock_st_class):
        """Model is loaded on first embed_text call, not before."""
        from app.services.embedding_service import EmbeddingService

        svc = EmbeddingService("test-lazy-model")
        # Model not loaded after init
        self.assertIsNone(svc._model)
        mock_st_class.assert_not_called()

        # Try to embed (model loading will fail because we set side_effect)
        mock_st_class.side_effect = ImportError("no module")
        result = svc.embed_text("test")
        self.assertEqual(result, [])

        # Now _load_attempted should be True, even though loading failed
        self.assertTrue(svc._load_attempted)


if __name__ == "__main__":
    unittest.main()
