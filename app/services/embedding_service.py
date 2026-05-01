"""Compute and cache paper embeddings using sentence-transformers.

This is the v2 embedding service. It stores embeddings in the SQLite
``paper_embeddings`` table via ``StateStore``, replacing the old
pickle-based NPZ cache in ``semantic_similarity.py``.

Key design decisions:

- **Lazy model loading**: the SentenceTransformer model is only loaded on the
  first call to ``embed_text()`` (not on import). A global module-level
  cache avoids reloading across ``EmbeddingService`` instances.
- **Database caching**: after computing an embedding, it is saved to the
  ``paper_embeddings`` table. The cache is checked before computing.
- **Batch processing**: when embedding many papers, ``model.encode()`` is
  called with ``batch_size`` for efficiency.
- **Graceful fallback**: if ``sentence-transformers`` is not installed, a
  warning is logged and empty embeddings are returned (no crash).
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

import numpy as np

from state_store import get_state_store

logger = logging.getLogger(__name__)

# Default model name — used when config_manager is unavailable
_DEFAULT_MODEL_NAME = "BAAI/bge-large-en-v1.5"

# Global model cache (module-level) so it is shared across service instances
_CACHED_MODEL = None
_CACHED_MODEL_NAME: Optional[str] = None


def _resolve_default_model_name() -> str:
    """Resolve the default embedding model from config, with fallback."""
    try:
        from config_manager import get_config
        model = get_config()._settings.embedding_model
        if model:
            return model
    except Exception:
        pass
    return _DEFAULT_MODEL_NAME


class EmbeddingService:
    """Compute and cache embeddings using sentence-transformers.

    Usage::

        svc = EmbeddingService()
        vec = svc.embed_text("transformer attention mechanisms")
        # vec is a list[float] of length 1024
    """

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or _resolve_default_model_name()
        self._model = None  # will be set on first use (lazy)
        self._load_attempted = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def embed_text(self, text: str) -> list[float]:
        """Embed a single text string.

        Returns a 1024-dim ``list[float]``.  Returns an empty list if
        the model could not be loaded.
        """
        if not self._load_model():
            return []
        vector = self._model.encode(text).tolist()  # type: ignore[union-attr]
        return vector

    def embed_paper(self, paper: dict) -> list[float]:
        """Embed a paper dict (title + abstract), with caching.

        ``paper`` must have ``id`` (or ``paper_id``) and ``title`` keys.
        An ``abstract`` key is optional.

        Returns a 1024-dim ``list[float]``, or ``[]`` on failure.
        """
        paper_id = paper.get("id") or paper.get("paper_id", "")
        if not paper_id:
            return []

        # Check cache
        store = get_state_store()
        cached = store.get_paper_embedding(paper_id)
        if cached is not None and cached[1] == self.model_name:
            blob, _model_name, _created_at = cached
            return np.frombuffer(blob, dtype=np.float32).tolist()

        if not self._load_model():
            return []

        text = self._build_paper_text(paper)
        vector = self._model.encode(text).tolist()  # type: ignore[union-attr]

        # Save to database cache
        blob = np.array(vector, dtype=np.float32).tobytes()
        store.save_paper_embedding(paper_id, blob, self.model_name)

        return vector

    def embed_papers_batch(self, papers: list[dict]) -> dict[str, list[float]]:
        """Bulk-embed papers, returns ``{paper_id: embedding_vector}``.

        Papers already cached in the database are skipped.  Uncached
        papers are encoded in a single batch call for efficiency.
        """
        store = get_state_store()
        results: dict[str, list[float]] = {}

        # Separate cached and uncached
        uncached: list[dict] = []
        for paper in papers:
            paper_id = paper.get("id") or paper.get("paper_id", "")
            if not paper_id:
                continue
            cached = store.get_paper_embedding(paper_id)
            if cached is not None and cached[1] == self.model_name:
                blob, _model_name, _created_at = cached
                results[paper_id] = np.frombuffer(blob, dtype=np.float32).tolist()
            else:
                uncached.append(paper)

        if not uncached:
            return results

        if not self._load_model():
            return results

        # Build texts for all uncached papers
        texts = [self._build_paper_text(p) for p in uncached]
        vectors = self._model.encode(texts, batch_size=32).tolist()  # type: ignore[union-attr]

        # Store and collect results
        for paper, vector in zip(uncached, vectors):
            paper_id = paper.get("id") or paper.get("paper_id", "")
            blob = np.array(vector, dtype=np.float32).tobytes()
            store.save_paper_embedding(paper_id, blob, self.model_name)
            results[paper_id] = vector

        return results

    def compute_library_embeddings(self, zotero_papers: list[dict]) -> list[list[float]]:
        """Compute embeddings for Zotero library papers.

        Each paper in ``zotero_papers`` should have at least ``title``
        (and optionally ``abstract``).  Existing embeddings in the
        ``paper_embeddings`` table are reused; only new/changed papers
        are encoded.

        Returns a list of embedding vectors (one per paper).
        """
        results = self.embed_papers_batch(zotero_papers)
        # Return embeddings in the same order as zotero_papers
        embeddings: list[list[float]] = []
        for paper in zotero_papers:
            paper_id = paper.get("id") or paper.get("paper_id", "")
            vec = results.get(paper_id)
            if vec is not None:
                embeddings.append(vec)
        return embeddings

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_paper_text(paper: dict) -> str:
        """Build a single text string from title + abstract."""
        title = paper.get("title", "")
        abstract = paper.get("abstract", "") or ""
        if abstract:
            return title + " " + abstract[:500]
        return title

    def _load_model(self) -> bool:
        """Lazy-load the sentence-transformers model.

        Returns ``True`` if the model is ready, ``False`` if
        sentence-transformers is not installed.
        """
        global _CACHED_MODEL, _CACHED_MODEL_NAME

        if self._model is not None:
            return True

        if self._load_attempted:
            return self._model is not None

        self._load_attempted = True

        # Check global cache first
        if _CACHED_MODEL is not None and _CACHED_MODEL_NAME == self.model_name:
            self._model = _CACHED_MODEL
            return True

        try:
            from sentence_transformers import SentenceTransformer

            logger.info("Loading embedding model: %s", self.model_name)
            self._model = SentenceTransformer(self.model_name)

            # Cache globally so other EmbeddingService instances share it
            _CACHED_MODEL = self._model
            _CACHED_MODEL_NAME = self.model_name

            return True
        except ImportError:
            logger.warning(
                "sentence-transformers not installed. Install with: pip install sentence-transformers"
            )
            return False
        except Exception:
            logger.exception("Failed to load embedding model %s", self.model_name)
            return False


__all__ = ["EmbeddingService"]
