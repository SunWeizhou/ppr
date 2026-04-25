"""Load recommendation snapshots for offline evaluation."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List

from state_store import _canonical_paper_id


def _normalize_paper(paper: dict) -> dict:
    item = dict(paper)
    item["id"] = _canonical_paper_id(item.get("id") or item.get("paper_id") or "")
    return item


def _load_json_run(path: Path) -> dict | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    papers = payload.get("papers")
    if not isinstance(papers, list):
        return None
    return {
        "date": str(payload.get("date") or path.stem),
        "source": str(path),
        "papers": [_normalize_paper(paper) for paper in papers if isinstance(paper, dict)],
    }


def _load_structured_runs(cache_dir: Path) -> list[dict]:
    runs = []
    daily_path = cache_dir / "daily_recommendation.json"
    if daily_path.exists():
        run = _load_json_run(daily_path)
        if run:
            runs.append(run)

    runs_dir = cache_dir / "recommendation_runs"
    if runs_dir.exists():
        for path in sorted(runs_dir.glob("*.json")):
            run = _load_json_run(path)
            if run:
                runs.append(run)
    return runs


def _load_history_run(path: Path) -> dict | None:
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return None

    papers = []
    sections = re.split(r"## \d+\.\s*", content)[1:]
    for section in sections:
        lines = [line.strip() for line in section.strip().splitlines() if line.strip()]
        if not lines:
            continue
        paper = {"title": lines[0]}
        for line in lines[1:]:
            if line.startswith("**Authors:**"):
                paper["authors"] = line.replace("**Authors:**", "").strip()
            elif line.startswith("**arXiv:**") or line.startswith("**arXiv Link:**"):
                match = re.search(r"\[([^\]]+)\]\(([^)]+)\)", line)
                if match:
                    paper["id"] = _canonical_paper_id(match.group(1))
                    paper["link"] = match.group(2)
            elif line.startswith("**Summary:**"):
                paper["summary"] = line.replace("**Summary:**", "").strip()
                paper["abstract"] = paper["summary"]
            elif line.startswith("**Relevance:**"):
                paper["relevance_reason"] = line.replace("**Relevance:**", "").strip()
                paper["relevance"] = paper["relevance_reason"]
            elif line.startswith("**Score:**"):
                try:
                    paper["score"] = float(line.replace("**Score:**", "").strip())
                except ValueError:
                    paper["score"] = 0.0
        if paper.get("id"):
            papers.append(_normalize_paper(paper))

    date_match = re.search(r"digest_(\d{4}-\d{2}-\d{2})", path.name)
    return {
        "date": date_match.group(1) if date_match else path.stem,
        "source": str(path),
        "papers": papers,
    }


def load_recommendation_runs(*, cache_dir: Path | str, history_dir: Path | str) -> List[dict]:
    """Load structured recommendation runs, falling back to markdown history."""
    cache_path = Path(cache_dir)
    history_path = Path(history_dir)
    structured = _load_structured_runs(cache_path)
    if structured:
        return structured

    if not history_path.exists():
        return []
    return [
        run
        for run in (_load_history_run(path) for path in sorted(history_path.glob("digest_*.md"), reverse=True))
        if run and run.get("papers")
    ]

