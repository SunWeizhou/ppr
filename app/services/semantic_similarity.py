"""Semantic similarity computation with smart caching and model selection."""

from __future__ import annotations

import os
import pickle
from typing import Dict, List, Optional, Tuple

from logger_config import get_logger

from app_paths import CACHE_DIR
from app.services.settings_service import load_user_config
# get_zotero_path is imported lazily inside compute_zotero_embedding to
# avoid circular import (zotero_service imports semantic_similarity)

logger = get_logger(__name__)

# Global model cache to avoid reloading
_CACHED_MODEL = None
_CACHED_MODEL_NAME: Optional[str] = None


# ---------------------------------------------------------------------------
# Smart model selection (moved from arxiv_recommender_v5)
# ---------------------------------------------------------------------------


def get_best_embedding_model() -> str:
    """Auto-detect best embedding model based on hardware."""
    # Check user config first
    config = load_user_config()
    user_model = config.get('settings', {}).get('embedding_model', '')
    if user_model:
        return user_model

    # Auto-detect based on hardware
    has_gpu, vram = _detect_nvidia_gpu()
    ram_gb = _get_ram_gb()

    if has_gpu and vram >= 6:
        model = 'BAAI/bge-large-en-v1.5'
        reason = f'GPU detected ({vram}GB VRAM)'
    elif ram_gb >= 16:
        model = 'sentence-transformers/all-mpnet-base-v2'
        reason = f'High RAM ({ram_gb}GB)'
    else:
        model = 'sentence-transformers/all-MiniLM-L6-v2'
        reason = f'Standard config ({ram_gb}GB RAM)'

    logger.info(f"Auto-selected model: {model} ({reason})")
    return model


def _detect_nvidia_gpu() -> Tuple[bool, int]:
    """Detect NVIDIA GPU and VRAM."""
    try:
        import subprocess
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=memory.total', '--format=csv,noheader,nounits'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            vram_mb = int(result.stdout.strip().split('\n')[0])
            return True, vram_mb // 1024
    except Exception:
        pass
    return False, 0


def _get_ram_gb() -> int:
    """Get system RAM in GB."""
    try:
        import psutil
        return psutil.virtual_memory().total // (1024**3)
    except ImportError:
        # Fallback for Windows without psutil
        try:
            import subprocess
            result = subprocess.run(
                ['wmic', 'computersystem', 'get', 'totalphysicalmemory'],
                capture_output=True, text=True
            )
            ram_bytes = int(result.stdout.split('\n')[1].strip())
            return ram_bytes // (1024**3)
        except Exception:
            return 8  # Default assumption


# ---------------------------------------------------------------------------
# SemanticSimilarity class (moved from arxiv_recommender_v5)
# ---------------------------------------------------------------------------


class SemanticSimilarity:
    """Compute semantic similarity with smart caching."""

    CACHE_FILE: Optional[str] = None

    def __init__(self, model_name: str = '', cache_dir: Optional[str] = None):
        global _CACHED_MODEL, _CACHED_MODEL_NAME
        self.model_name = model_name or get_best_embedding_model()
        self.cache_dir = cache_dir or str(CACHE_DIR)
        self._cache_file = os.path.join(self.cache_dir, 'zotero_embedding.pkl')

        # Reuse cached model if same model name
        if _CACHED_MODEL_NAME == self.model_name and _CACHED_MODEL is not None:
            self.model = _CACHED_MODEL
            self.zotero_embedding = None
        else:
            self.model = None
            self.zotero_embedding = None

    def _load_model(self):
        """Lazy load the model with auto device detection and global caching."""
        global _CACHED_MODEL, _CACHED_MODEL_NAME

        # Check global cache first
        if _CACHED_MODEL is not None and _CACHED_MODEL_NAME == self.model_name:
            self.model = _CACHED_MODEL
            return True

        if self.model is None:
            try:
                from sentence_transformers import SentenceTransformer

                # Always use CPU for MiniLM (fast enough, more reliable)
                device = 'cpu'

                logger.info(f"Loading embedding model: {self.model_name} (device: {device})")
                self.model = SentenceTransformer(self.model_name, device=device)

                # Cache globally
                _CACHED_MODEL = self.model
                _CACHED_MODEL_NAME = self.model_name

            except ImportError:
                logger.warning("sentence-transformers not installed. Using keyword matching.")
                return False
        return True

    def _get_fingerprint(self, papers: List[Dict], zotero_path: str) -> Dict:
        """Get quick fingerprint to detect changes."""
        return {
            'count': len(papers),
            'db_mtime': os.path.getmtime(zotero_path) if os.path.exists(zotero_path) else 0,
        }

    def compute_zotero_embedding(self, papers: List[Dict], zotero_path: Optional[str] = None):
        """Compute embedding with smart cache invalidation."""
        if not self._load_model():
            return None

        # Lazy import to avoid circular dependency with zotero_service
        from app.services.zotero_service import get_zotero_path as _get_zotero_path
        zotero_path = zotero_path or _get_zotero_path()
        current_fp = self._get_fingerprint(papers, zotero_path)

        # Try loading cache
        if os.path.exists(self._cache_file):
            try:
                with open(self._cache_file, 'rb') as f:
                    cached = pickle.load(f)
                if (cached.get('fingerprint', {}).get('count') == current_fp['count'] and
                        cached.get('fingerprint', {}).get('db_mtime') == current_fp['db_mtime']):
                    logger.debug(f"Using cached embedding ({len(papers)} papers)")
                    self.zotero_embedding = cached['embedding']
                    return self.zotero_embedding
            except Exception as e:
                logger.warning(f"Cache read error: {e}")

        # Compute new embedding
        logger.info(f"Computing embedding for {len(papers)} papers...")
        texts = [p['title'] + ' ' + (p.get('abstract', '') or '')[:500] for p in papers]
        embeddings = self.model.encode(texts, show_progress_bar=False)
        self.zotero_embedding = embeddings.mean(axis=0)

        # Save cache
        try:
            os.makedirs(self.cache_dir, exist_ok=True)
            with open(self._cache_file, 'wb') as f:
                pickle.dump({'embedding': self.zotero_embedding, 'fingerprint': current_fp}, f)
            logger.debug("Embedding cached successfully")
        except Exception as e:
            logger.warning(f"Cache save error: {e}")

        return self.zotero_embedding

    def compute_similarity(self, paper: Dict) -> float:
        """Compute semantic similarity between paper and Zotero library."""
        if self.model is None or self.zotero_embedding is None:
            return 0.0

        text = paper['title']
        if paper.get('abstract'):
            text += ' ' + paper['abstract'][:500]

        paper_embedding = self.model.encode([text], show_progress_bar=False)[0]

        # Cosine similarity
        from numpy import dot
        from numpy.linalg import norm
        similarity = dot(self.zotero_embedding, paper_embedding) / (
            norm(self.zotero_embedding) * norm(paper_embedding)
        )
        return float(similarity)


__all__ = [
    "SemanticSimilarity",
    "get_best_embedding_model",
    "_detect_nvidia_gpu",
    "_get_ram_gb",
]
