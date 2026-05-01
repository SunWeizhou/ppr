"""Feedback model training: logistic regression on user interaction embeddings.

Retrains when enough new feedback events have accumulated since last
training, and saves the model to the feedback_models table via StateStore.
A quality gate (AUC >= 0.55) decides whether the model is eligible to
influence paper scoring.
"""

from __future__ import annotations

import logging
import pickle
from datetime import UTC, datetime, timedelta, timezone

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

logger = logging.getLogger(__name__)

_MIN_TRAINING_INTERVAL = timedelta(hours=12)
_MIN_SAMPLES = 60
_FEEDBACK_EVENT_TYPES = ("feedback_relevant", "feedback_ignored")


def _load_embedding(state_store, paper_id: str) -> list[float] | None:
    """Load a paper embedding from the store, or attempt to compute it."""
    cached = state_store.get_paper_embedding(paper_id)
    if cached is not None:
        blob, _model_name, _created_at = cached
        return np.frombuffer(blob, dtype=np.float32).tolist()

    # Try to compute the embedding on the fly
    try:
        from app.services.embedding_service import EmbeddingService

        svc = EmbeddingService()
        # Build a minimal paper dict so embed_paper can find the id
        paper = {"id": paper_id, "title": "", "abstract": ""}
        vec = svc.embed_paper(paper)
        if vec:
            return vec
    except Exception:
        logger.debug("Could not compute embedding for %s", paper_id, exc_info=True)

    return None


def retrain_if_needed(state_store) -> bool:
    """Train/re-train a feedback model if conditions are met.

    Conditions:
    - At least 12 hours since last training
    - At least 60 interaction events of type ``feedback_relevant`` /
      ``feedback_ignored``

    Model: ``sklearn.linear_model.LogisticRegression(class_weight='balanced')``

    Quality gate: if AUC < 0.55 the model is saved but not enabled (caller
    decides what "not enabled" means -- here we simply save it and let
    ``get_feedback_model_auc()`` reflect the real AUC).

    Returns ``True`` if a new model was trained, ``False`` otherwise.
    """
    # ---- Time check ----
    last_trained_str = state_store.get("feedback_model_trained_at")
    if last_trained_str:
        try:
            last_trained = datetime.fromisoformat(last_trained_str)
            now = datetime.now(tz=UTC)
            if last_trained.tzinfo is None:
                last_trained = last_trained.replace(tzinfo=UTC)
            if now - last_trained < _MIN_TRAINING_INTERVAL:
                logger.info(
                    "Skipping feedback model training: last trained at %s (< %s)",
                    last_trained_str,
                    _MIN_TRAINING_INTERVAL,
                )
                return False
        except (ValueError, TypeError):
            pass  # malformed timestamp -- proceed

    # ---- Gather events ----
    events = state_store.list_interaction_events(limit=2000)
    relevant: list[str] = []  # paper_ids for feedback_relevant
    ignored: list[str] = []   # paper_ids for feedback_ignored

    for ev in events:
        etype = ev.get("event_type", "")
        pid = ev.get("paper_id", "")
        if not pid:
            continue
        if etype == "feedback_relevant":
            relevant.append(pid)
        elif etype == "feedback_ignored":
            ignored.append(pid)

    total_samples = len(relevant) + len(ignored)
    if total_samples < _MIN_SAMPLES:
        logger.info(
            "Skipping feedback model training: only %d events (need %d)",
            total_samples,
            _MIN_SAMPLES,
        )
        return False

    # ---- Build feature matrix ----
    # De-duplicate paper_ids per class (multiple events on same paper are ok)
    relevant_ids = list(set(relevant))
    ignored_ids = list(set(ignored))

    if not relevant_ids or not ignored_ids:
        logger.info(
            "Skipping feedback model training: need at least 1 positive and 1 negative sample"
        )
        return False

    X_list: list[np.ndarray] = []
    y_list: list[int] = []

    for pid in relevant_ids:
        vec = _load_embedding(state_store, pid)
        if vec is not None and len(vec) > 0:
            X_list.append(np.array(vec, dtype=np.float32))
            y_list.append(1)

    for pid in ignored_ids:
        vec = _load_embedding(state_store, pid)
        if vec is not None and len(vec) > 0:
            X_list.append(np.array(vec, dtype=np.float32))
            y_list.append(0)

    if len(X_list) < _MIN_SAMPLES:
        logger.info(
            "Skipping feedback model training: only %d samples with embeddings (need %d)",
            len(X_list),
            _MIN_SAMPLES,
        )
        return False

    if len(set(y_list)) < 2:
        logger.info(
            "Skipping feedback model training: only one class after embedding lookup"
        )
        return False

    X = np.stack(X_list)
    y = np.array(y_list, dtype=np.int32)

    # ---- Train ----
    try:
        model = LogisticRegression(max_iter=200, class_weight="balanced")
        model.fit(X, y)
        y_proba = model.predict_proba(X)[:, 1]
        auc = float(roc_auc_score(y, y_proba))
    except Exception:
        logger.exception("Feedback model training failed")
        return False

    # ---- Quality gate ----
    if auc < 0.55:
        logger.info(
            "Feedback model AUC=%.4f < 0.55, saving but not enabling feedback signal",
            auc,
        )

    # ---- Persist ----
    pickle_blob = pickle.dumps(model)
    state_store.save_feedback_model(len(X_list), auc, pickle_blob)
    state_store.save("feedback_model_trained_at", datetime.now(tz=UTC).isoformat())
    state_store.save("feedback_model_auc", str(auc))

    logger.info(
        "Trained feedback model: AUC=%.4f, samples=%d (pos=%d, neg=%d)",
        auc,
        len(X_list),
        int(y.sum()),
        int((1 - y).sum()),
    )
    return True
