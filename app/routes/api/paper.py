"""Paper-related API routes (fetch, BibTeX, citation, download, related)."""
import logging
import os
import re
from datetime import datetime

from flask import jsonify, make_response, request, send_file

from state_store import _canonical_paper_id

from . import bp
from .helpers import (
    CACHE_DIR,
    HISTORY_DIR,
    PROJECT_ROOT,
    _current_state_store,
    _feedback_service,
    _load_history_paper_index,
)

logger = logging.getLogger(__name__)


@bp.get("/api/pdf/<paper_id>")
def download_pdf(paper_id):
    # Canonicalize and validate the paper_id to prevent path traversal
    paper_id = _canonical_paper_id(paper_id)
    if not re.match(r"^\d{4}\.\d{4,5}$", paper_id):
        return jsonify({"success": False, "error": "Invalid paper ID"}), 400

    pdf_dir = os.path.join(str(PROJECT_ROOT), "cache", "pdfs")
    pdf_path = os.path.join(pdf_dir, f"{paper_id}.pdf")

    # Resolve real paths to prevent path traversal via symlinks or .. segments
    real_pdf_path = os.path.realpath(pdf_path)
    real_pdf_dir = os.path.realpath(pdf_dir)
    if not real_pdf_path.startswith(real_pdf_dir + os.sep):
        return jsonify({"success": False, "error": "Forbidden"}), 403

    if os.path.exists(real_pdf_path):
        return send_file(real_pdf_path, as_attachment=True)
    return f'<script>window.location.href="https://arxiv.org/pdf/{paper_id}.pdf";</script>'


@bp.get("/api/dates")
def get_dates():
    # SQLite first
    dates = _current_state_store().list_recommendation_dates(limit=90)
    if not dates:
        # Fallback to markdown history
        import os as _os

        dates = []
        hist_dir = str(HISTORY_DIR)
        if _os.path.exists(hist_dir):
            for f in _os.listdir(hist_dir):
                if f.startswith("digest_") and f.endswith(".md"):
                    date = f.replace("digest_", "").replace(".md", "")
                    dates.append(date)
        dates = sorted(dates, reverse=True)
    return jsonify(dates)


@bp.get("/api/citation/<paper_id>")
def get_citation(paper_id):
    """Get citation data for a paper."""
    try:
        from arxiv_recommender_v5 import CitationAnalyzer

        analyzer = CitationAnalyzer(str(CACHE_DIR))
        data = analyzer.fetch_citation_data(paper_id)

        return jsonify({
            "success": True,
            "paper_id": paper_id,
            "citations": data.get("citations", 0),
            "influential_citations": data.get("influential_citations", 0),
            "references": data.get("references", 0),
        })
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@bp.get("/api/fetch_paper/<paper_id>")
def fetch_paper_info(paper_id):
    """Fetch paper info from arXiv API and save to cache."""
    from app.services.arxiv_source import fetch_arxiv_metadata

    try:
        metadata = fetch_arxiv_metadata(paper_id)
        if metadata is None:
            return jsonify({"success": False, "error": "Paper not found"}), 404

        # Record paper opened interaction event
        _current_state_store().record_event("paper_opened", paper_id)

        # Save to state_store
        _current_state_store().save_paper_metadata(paper_id, {
            "title": metadata["title"],
            "abstract": metadata["abstract"][:500],
            "authors": ", ".join(metadata["authors"]),
            "date": datetime.now().strftime("%Y-%m-%d"),
            "score": 0,
            "relevance": "从 arXiv 获取",
        })

        return jsonify({
            "success": True,
            "paper_id": paper_id,
            "title": metadata["title"],
            "abstract": metadata["abstract"][:500],
            "authors": ", ".join(metadata["authors"]),
        })
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@bp.get("/api/export/bibtex/<paper_id>")
def export_bibtex(paper_id):
    from app.services.arxiv_source import fetch_arxiv_metadata

    # Canonicalize and validate the paper_id
    paper_id = _canonical_paper_id(paper_id)
    if not re.match(r"^\d{4}\.\d{4,5}$", paper_id):
        return jsonify({"success": False, "error": "Invalid paper ID"}), 400

    try:
        metadata = fetch_arxiv_metadata(paper_id)
        if metadata is None:
            return jsonify({"success": False, "error": "Paper not found"}), 404

        year = metadata.get("published", "")[:4] or str(datetime.now().year)
        author_field = " and ".join(metadata.get("authors", [])) or "Unknown"
        citation_key = re.sub(r"[^a-zA-Z0-9]+", "", paper_id)
        bibtex = (
            f"@article{{arxiv{citation_key},\n"
            f"  title = {{{metadata['title']}}},\n"
            f"  author = {{{author_field}}},\n"
            f"  journal = {{arXiv preprint arXiv:{paper_id}}},\n"
            f"  year = {{{year}}},\n"
            f"  url = {{{metadata['link']}}}\n"
            f"}}\n"
        )

        _current_state_store().record_event("export_to_zotero", paper_id, {"source": "bibtex_export"})

        response = make_response(bibtex, 200)
        response.headers["Content-Type"] = "application/x-bibtex; charset=utf-8"
        response.headers["Content-Disposition"] = f'attachment; filename="{paper_id}.bib"'
        return response
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@bp.get("/api/related/<paper_id>")
def get_related_papers(paper_id):
    """Get related papers based on a given paper."""
    from app.services.arxiv_source import fetch_arxiv_metadata

    try:
        # Try to resolve the paper from favorites, history, or arXiv
        paper_info = None
        favorites = _feedback_service().load_favorites()
        history_index = _load_history_paper_index()

        if paper_id in favorites:
            favorite = favorites[paper_id]
            paper_info = {
                "title": favorite.get("title", ""),
                "abstract": favorite.get("abstract", favorite.get("summary", "")),
            }
        elif paper_id in history_index:
            history_paper = history_index[paper_id]
            paper_info = {
                "title": history_paper.get("title", ""),
                "abstract": history_paper.get("abstract", history_paper.get("summary", "")),
            }
        else:
            metadata = fetch_arxiv_metadata(paper_id)
            if metadata is not None:
                paper_info = {
                    "title": metadata.get("title", ""),
                    "abstract": metadata.get("abstract", ""),
                }

        if not paper_info:
            return jsonify({"success": False, "error": "Paper not found", "related": []}), 404

        # Extract keywords from paper
        text = (paper_info.get("title", "") + " " + paper_info.get("abstract", "")).lower()

        # Find important terms
        words = re.findall(r"\b[a-z]+\b", text)
        word_freq = {}
        for w in words:
            if len(w) > 4:  # Skip short words
                word_freq[w] = word_freq.get(w, 0) + 1

        top_keywords = sorted(word_freq.items(), key=lambda x: -x[1])[:5]
        keywords = [k[0] for k in top_keywords]

        # Search for related papers
        from arxiv_recommender_v5 import search_by_keywords

        related = search_by_keywords(keywords, max_results=10, days_back=180)

        # Remove the original paper
        related = [p for p in related if p.get("id") != paper_id][:5]

        return jsonify({"success": True, "related": related, "keywords": keywords})

    except Exception as exc:
        return jsonify({"success": False, "error": str(exc), "related": []}), 500
