"""RAG Q&A API — paper selection toggling and question answering."""

import logging

from flask import jsonify, request

from . import bp
from .helpers import _current_state_store

logger = logging.getLogger(__name__)


@bp.post("/api/rag/toggle")
def rag_toggle():
    """Enable or disable a paper for RAG indexing in a workspace."""
    data = request.get_json() or {}
    paper_id = str(data.get("paper_id", "")).strip()
    rq_id = data.get("research_question_id")

    if not paper_id:
        return jsonify({"success": False, "error": "Missing paper_id"}), 400
    if rq_id is None:
        return jsonify({"success": False, "error": "Missing research_question_id"}), 400

    try:
        rq_id = int(rq_id)
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "Invalid research_question_id"}), 400

    store = _current_state_store()
    rq = store.get_research_question(rq_id)
    if rq is None:
        return jsonify({"success": False, "error": "Workspace not found"}), 404

    rag_enabled = bool(data.get("rag_enabled", True))
    ok = store.toggle_rag_paper(paper_id, rq_id, rag_enabled)
    if not ok:
        return jsonify({
            "success": False,
            "error": "Paper not found in this workspace",
        }), 404

    return jsonify({
        "success": True,
        "paper_id": paper_id,
        "research_question_id": rq_id,
        "rag_enabled": rag_enabled,
    })


@bp.post("/api/rag/ask")
def rag_ask():
    """Ask a question against RAG-selected papers in a workspace.

    Retrieves relevant papers via RagRetrievalService, builds context,
    and generates an answer through the AI provider when available.
    Falls back to raw retrieval results when no provider is configured.
    """
    data = request.get_json() or {}
    question = str(data.get("question", "")).strip()
    rq_id = data.get("research_question_id")

    if not question:
        return jsonify({"success": False, "error": "Missing question"}), 400
    if rq_id is None:
        return jsonify({"success": False, "error": "Missing research_question_id"}), 400

    try:
        rq_id = int(rq_id)
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "Invalid research_question_id"}), 400

    store = _current_state_store()

    # Get RAG-enabled papers
    selected = store.list_workspace_papers(rq_id, rag_enabled=True) or []
    if not selected:
        return jsonify({
            "success": False,
            "error": "No papers selected for RAG. Please select at least one paper first.",
        }), 400

    paper_ids = [wp["paper_id"] for wp in selected]

    # Retrieve relevant papers
    from app.services.rag_service import RagRetrievalService

    rag = RagRetrievalService(store)
    results = rag.query(rq_id, question, max_results=5, paper_ids=paper_ids)

    # Build sources for the response
    sources = []
    for r in results:
        meta = store.get_paper_metadata(r["paper_id"]) or {}
        takeaway = store.get_reading_takeaway(r["paper_id"], research_question_id=rq_id)
        sources.append({
            "paper_id": r["paper_id"],
            "title": r.get("title", r["paper_id"]),
            "abstract_preview": (meta.get("abstract") or meta.get("summary", ""))[:300],
            "memo_preview": (takeaway.get("takeaway_text", "") or "")[:300] if takeaway else None,
            "score": round(r.get("score", 0), 4),
        })

    # Try AI generation
    answer = ""
    rag_stats = {
        "papers_indexed": len(selected),
        "papers_retrieved": len(results),
    }

    try:
        from app.services.ai_providers import build_ai_provider_from_env, NoProvider

        provider = build_ai_provider_from_env()
        if not isinstance(provider, NoProvider) and hasattr(provider, "chat"):
            # Build context from top results
            context_parts = []
            for r in results[:5]:
                ctx = r.get("_rag_context", "")
                if ctx:
                    context_parts.append(ctx[:800])  # cap per paper
            context_text = "\n\n---\n\n".join(context_parts)[:3000]

            system_prompt = (
                "You are a literature review assistant. Answer the user's question "
                "based on the provided paper excerpts. When referencing specific "
                "papers, use their titles. If the provided excerpts do not contain "
                "enough information to answer the question, say so. Be concise and "
                "structured in your response — use bullet points when listing items."
            )

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "system", "content": f"Available papers:\n\n{context_text}"},
                {"role": "user", "content": question},
            ]

            answer = provider.chat(messages, page_context={})
            answer = str(answer or "").strip()
    except Exception:
        logger.warning("AI generation for RAG ask failed", exc_info=True)

    return jsonify({
        "success": True,
        "question": question,
        "answer": answer,
        "sources": sources,
        "rag_stats": rag_stats,
    })
