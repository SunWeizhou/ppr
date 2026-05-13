"""AI Analysis API routes."""
from flask import jsonify, request

from . import bp
from .helpers import _ai_analysis_service


@bp.get("/api/papers/<paper_id>/analysis")
def get_paper_analysis(paper_id):
    from app.data._constants import canonical_paper_id as _canonical_paper_id

    canonical_id = _canonical_paper_id(paper_id)
    service = _ai_analysis_service()
    store = service.state_store
    analysis = service.get_analysis(canonical_id)
    if not analysis:
        return jsonify({"success": False, "error": "analysis_not_found"}), 404
    return jsonify({
        "success": True,
        "analysis": analysis,
        "evidence_claims": _analysis_evidence_claims(store, canonical_id, analysis),
    })


@bp.post("/api/papers/<paper_id>/analysis/generate")
def generate_paper_analysis(paper_id):
    from app.data._constants import canonical_paper_id as _canonical_paper_id

    canonical_id = _canonical_paper_id(paper_id)
    service = _ai_analysis_service()
    store = service.state_store
    data = request.get_json() or {}

    # Resolve full paper context from backend (SQLite / Markdown fallback)
    paper = _resolve_paper_context(canonical_id)

    # Fallback to frontend-provided paper body for backward compatibility
    if not paper:
        frontend_paper = data.get("paper") or {}
        if frontend_paper:
            paper = _build_paper_dict(frontend_paper)

    if not paper:
        return jsonify({"success": False, "error": "Paper not found"}), 404

    paper["id"] = canonical_id

    user_profile = data.get("user_profile")

    # Build structured recommendation reason for the response
    recommendation_reason = None
    try:
        from app.services.scoring_service import build_recommendation_reason

        recommendation_reason = build_recommendation_reason(
            paper,
            user_profile=user_profile,
        )
    except Exception:
        pass

    try:
        analysis = service.get_or_create_analysis(
            paper,
            user_profile=user_profile,
            recommendation_context=_recommendation_context_from_request(data, store),
            force=bool(data.get("force", False)),
        )
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400

    result = {
        "success": True,
        "analysis": analysis,
        "evidence_claims": _analysis_evidence_claims(store, canonical_id, analysis),
    }
    if recommendation_reason:
        result["recommendation_reason"] = recommendation_reason
    return jsonify(result)


def _resolve_paper_context(paper_id: str) -> dict | None:
    """Resolve full paper context from SQLite recommendation_items or Markdown history fallback."""
    from state_store import get_state_store

    store = get_state_store()

    # 1) Search SQLite recommendation_items (primary)
    from app.data._constants import canonical_paper_id as _canonical_paper_id

    try:
        runs = store.list_recommendation_runs(limit=10)
        for run in runs:
            items = store.get_recommendation_items(run["run_id"])
            for item in items:
                stored_id = _canonical_paper_id(item.get("paper_id") or item.get("id") or "")
                if stored_id == paper_id:
                    return _build_paper_dict(item)
    except Exception:
        pass

    # 2) Fallback to SQLite paper metadata. Search and preview write full
    # abstracts here, so this is the best source for ad-hoc discovered papers.
    try:
        meta = store.get_paper_metadata(paper_id)
        if meta:
            return _build_paper_dict(meta)
    except Exception:
        pass

    # 3) Fallback to Markdown history
    import os
    from app_paths import HISTORY_DIR

    if os.path.exists(str(HISTORY_DIR)):
        for fname in sorted(os.listdir(str(HISTORY_DIR)), reverse=True):
            if not fname.startswith("digest_") or not fname.endswith(".md"):
                continue
            filepath = os.path.join(str(HISTORY_DIR), fname)
            try:
                from app.viewmodels.inbox_viewmodel import InboxViewModel

                papers, _ = InboxViewModel.parse_digest(filepath, use_cache=False)
                for p in papers:
                    if _canonical_paper_id(p.get("id") or "") == paper_id:
                        return _build_paper_dict(p)
            except Exception:
                continue

    return None


def _analysis_evidence_claims(store, paper_id: str, analysis: dict | None) -> list[dict]:
    claims = store.list_evidence_claims(paper_id=paper_id)
    if not analysis:
        return claims
    ordered_ids = analysis.get("evidence_claim_ids") or []
    if not ordered_ids:
        return claims
    by_id = {claim.get("id"): claim for claim in claims}
    ordered = [by_id[claim_id] for claim_id in ordered_ids if claim_id in by_id]
    remaining = [claim for claim in claims if claim.get("id") not in set(ordered_ids)]
    return ordered + remaining


def _recommendation_context_from_request(data: dict, store) -> dict | None:
    context = dict(data.get("recommendation_context") or {})
    raw_question_id = (
        data.get("research_question_id")
        or context.get("research_question_id")
        or (context.get("research_question") or {}).get("id")
    )
    if raw_question_id in (None, ""):
        return context or None
    try:
        question_id = int(raw_question_id)
    except (TypeError, ValueError):
        return context or None

    question = store.get_research_question(question_id)
    if question:
        context["research_question_id"] = question_id
        context["research_question"] = question
    return context or None


def _build_paper_dict(item: dict) -> dict:
    """Normalize a paper record into a dict with expected keys for AI analysis."""
    import json

    paper = dict(item)
    paper["id"] = paper.get("paper_id") or paper.get("id") or ""

    # Parse JSON fields if they are still strings (SQLite raw format)
    for field in ("authors_json", "categories_json"):
        raw = paper.pop(field, None)
        if raw is not None:
            if isinstance(raw, str):
                try:
                    parsed = json.loads(raw)
                except (TypeError, json.JSONDecodeError):
                    parsed = []
            elif isinstance(raw, list):
                parsed = raw
            else:
                parsed = []
            key = field.replace("_json", "")
            # Only set if not already populated by get_recommendation_items
            if key not in paper or not paper[key]:
                paper[key] = parsed

    # Ensure key fields are present
    paper.setdefault("title", "")
    paper.setdefault("abstract", "")
    paper.setdefault("authors", [])
    paper.setdefault("categories", [])

    # Parse score_details — prefer the already-parsed version from
    # get_recommendation_items, otherwise parse score_details_json
    sd = paper.get("score_details") or paper.get("score_details_json") or {}
    if isinstance(sd, str):
        try:
            sd = json.loads(sd)
        except (TypeError, json.JSONDecodeError):
            sd = {}
    elif not isinstance(sd, dict):
        sd = {}
    paper["score_details"] = sd

    return paper
