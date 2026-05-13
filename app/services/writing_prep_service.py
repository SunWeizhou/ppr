"""Writing prep service — generates literature review outlines, related work skeletons, etc."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.services.ai_providers import NoProvider, build_ai_provider_from_env


def _week_start() -> str:
    monday = datetime.now(timezone.utc) - timedelta(days=datetime.now(timezone.utc).weekday())
    return monday.strftime("%Y-%m-%d")


def _format_list(items: list[dict], title_key: str = "title", id_key: str = "paper_id") -> str:
    if not items:
        return "(none)"
    lines: list[str] = []
    for item in items:
        lines.append(f"- {item.get(title_key, item.get(id_key, 'unknown'))}")
    return "\n".join(lines)


class WritingPrepService:
    """Generate writing-prep outputs from workspace activity data.

    All generation is AI-provider-backed with deterministic fallback so the
    feature always returns something useful.
    """

    def __init__(self, state_store):
        self._store = state_store

    # ------------------------------------------------------------------
    # Public generation methods
    # ------------------------------------------------------------------

    def generate_literature_review_outline(
        self, research_question_id: int, *, provider=None,
    ) -> str:
        """Generate a literature review outline from workspace papers."""
        papers = self._gather_read_papers(research_question_id)
        ws = self._store.get_research_question(research_question_id) or {}
        query_text = ws.get("query_text", "Untitled")

        provider = provider or self._get_provider()
        prompt = (
            f"Generate a literature review outline for the research question:\n"
            f"'{query_text}'\n\n"
            f"Papers read so far ({len(papers)} total):\n{_format_list(papers)}\n\n"
            f"Organize into a markdown outline with sections: Introduction, "
            f"Background / Foundations, Key Approaches, Current State, "
            f"Open Challenges, Conclusion. For each section, list 1-3 bullet "
            f"points covering what to include and which papers to reference."
        )
        result = self._try_generate(prompt, provider)
        if result:
            return result
        return self._fallback_lit_review_outline(query_text, papers)

    def generate_related_work_skeleton(
        self, research_question_id: int, *, provider=None,
    ) -> str:
        """Generate a related work section skeleton from workspace papers."""
        papers = self._gather_read_papers(research_question_id)
        key_papers = self._store.list_workspace_papers(research_question_id, relationship="key_confirmed") or []
        ws = self._store.get_research_question(research_question_id) or {}
        query_text = ws.get("query_text", "Untitled")

        provider = provider or self._get_provider()
        prompt = (
            f"Generate a 'Related Work' section skeleton for a paper on:\n"
            f"'{query_text}'\n\n"
            f"Key papers:\n{_format_list(key_papers)}\n\n"
            f"Other read papers:\n{_format_list(papers)}\n\n"
            f"Return markdown with 3-5 thematic subsections, each listing "
            f"which papers to cite and what to say about them. Keep each "
            f"subsection to 1-2 sentences."
        )
        result = self._try_generate(prompt, provider)
        if result:
            return result
        return self._fallback_related_work(query_text, papers, key_papers)

    def generate_progress_summary(
        self, research_question_id: int, *, provider=None,
    ) -> str:
        """Generate a workspace progress summary."""
        papers = self._gather_read_papers(research_question_id)
        takeaways = self._store.list_reading_takeaways(research_question_id=research_question_id) or []
        memo = self._store.get_memo(research_question_id)
        ws = self._store.get_research_question(research_question_id) or {}
        query_text = ws.get("query_text", "Untitled")
        has_memo = bool(memo and memo.get("content", "").strip())

        provider = provider or self._get_provider()
        prompt = (
            f"Summarize research progress for:\n'{query_text}'\n\n"
            f"Read papers: {len(papers)}\n"
            f"Takeaways: {len(takeaways)}\n"
            f"Memo written: {'Yes' if has_memo else 'No'}\n\n"
            f"Takeaways:\n{_format_list(takeaways, title_key='takeaway_text')}\n\n"
            f"Write a 2-3 paragraph markdown progress summary covering "
            f"what has been learned, current understanding, and next steps."
        )
        result = self._try_generate(prompt, provider)
        if result:
            return result
        return self._fallback_progress_summary(query_text, papers, takeaways)

    def generate_supervisor_update(
        self, research_question_id: int, *, provider=None,
    ) -> str:
        """Generate a supervisor update draft from workspace activity."""
        papers = self._gather_read_papers(research_question_id)
        takeaways = self._store.list_reading_takeaways(research_question_id=research_question_id) or []
        ws = self._store.get_research_question(research_question_id) or {}
        query_text = ws.get("query_text", "Untitled")

        provider = provider or self._get_provider()
        prompt = (
            f"Draft a brief supervisor update for a student researching:\n"
            f"'{query_text}'\n\n"
            f"Papers read: {len(papers)}\n"
            f"Recent takeaways:\n{_format_list(takeaways, title_key='takeaway_text')}\n\n"
            f"Write 2-3 paragraphs in markdown: what was done this period, "
            f"key findings, current questions, and planned next steps. "
            f"Use a professional but concise tone suitable for email."
        )
        result = self._try_generate(prompt, provider)
        if result:
            return result
        return self._fallback_supervisor_update(query_text, papers, takeaways)

    def generate_memo_suggestions(
        self, research_question_id: int, *, provider=None,
    ) -> dict:
        """Generate suggested memo updates from workspace activity."""
        papers = self._gather_read_papers(research_question_id)
        takeaways = self._store.list_reading_takeaways(research_question_id=research_question_id) or []
        workspace_papers = self._store.list_workspace_papers(research_question_id) or []
        ws = self._store.get_research_question(research_question_id) or {}
        query_text = ws.get("query_text", "Untitled")
        memo = self._store.get_memo(research_question_id)
        memo_content = (memo or {}).get("content", "")

        provider = provider or self._get_provider()
        prompt = (
            f"Suggest memo updates for a research workspace on:\n"
            f"'{query_text}'\n\n"
            f"Current memo length: {len(memo_content)} characters\n"
            f"Read papers: {len(papers)}\n"
            f"Takeaways ({len(takeaways)}):\n{_format_list(takeaways, title_key='takeaway_text')}\n\n"
            f"Workspace paper relationships: {len(workspace_papers)} papers tracked\n\n"
            f"Return ONLY valid JSON with no markdown wrapping, using this structure:\n"
            f'{{\n  "suggested_sections": [\n    {{\n      "section": "Current Understanding",\n'
            f'      "suggestion": "Describe the suggested update in 1-2 sentences"\n    }}\n  ],\n'
            f'  "open_questions": ["question 1", "question 2"],\n'
            f'  "next_directions": ["direction 1", "direction 2"]\n'
            f"}}"
        )
        try:
            content = provider.chat([{"role": "user", "content": prompt}])
            if content:
                parsed = self._extract_json(content)
                if isinstance(parsed, dict) and parsed.get("suggested_sections"):
                    return parsed
        except Exception:
            pass
        return self._fallback_memo_suggestions(takeaways)

    def export_review_markdown(self, review: dict) -> str:
        """Render a weekly review dict as downloadable markdown."""
        content = review.get("content", "")
        event_summary = review.get("event_summary", {})
        reflection = review.get("reflection_answers", {})
        lines = [
            content.strip(),
            "",
            "---",
            "## Reflection Answers",
            "",
            f"**Which paper changed your understanding most?**",
            f"{reflection.get('changing_paper', '(not answered)')}",
            "",
            f"**What uncertainty remains?**",
            f"{reflection.get('remaining_uncertainty', '(not answered)')}",
            "",
            f"**What do you want to investigate next week?**",
            f"{reflection.get('next_investigation', '(not answered)')}",
            "",
        ]
        if event_summary:
            lines.append("---")
            lines.append(f"*Generated from {event_summary.get('total_events', 0)} activity events "
                         f"({event_summary.get('papers_read', 0)} read, "
                         f"{event_summary.get('papers_added', 0)} added)*")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _gather_read_papers(self, research_question_id: int) -> list[dict]:
        """Collect papers with 'read' or 'key_confirmed' relationship."""
        result = []
        for rel in ("read", "key_confirmed"):
            for wp in (self._store.list_workspace_papers(research_question_id, relationship=rel) or []):
                meta = self._store.get_paper_metadata(wp["paper_id"]) or {}
                result.append({
                    "paper_id": wp["paper_id"],
                    "title": meta.get("title", wp["paper_id"]),
                    "relationship": rel,
                })
        return result

    def _get_provider(self):
        return build_ai_provider_from_env()

    def _try_generate(self, prompt: str, provider) -> str | None:
        """Attempt AI generation with graceful fallback."""
        if isinstance(provider, NoProvider):
            return None
        try:
            if hasattr(provider, "chat"):
                return provider.chat([{"role": "user", "content": prompt}])
        except Exception:
            pass
        return None

    @staticmethod
    def _extract_json(content: str) -> dict:
        text = str(content or "").strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end > start:
                return json.loads(text[start: end + 1])
            return {}

    @staticmethod
    def _fallback_lit_review_outline(query_text: str, papers: list) -> str:
        return (
            f"## Literature Review Outline: {query_text}\n\n"
            f"### 1. Introduction\n"
            f"- Context and motivation for studying {query_text}\n"
            f"- Research questions and scope\n\n"
            f"### 2. Background / Foundations\n"
            f"- Foundational works and key concepts\n"
            f"- {len(papers)} papers reviewed so far\n\n"
            f"### 3. Key Approaches\n"
            f"- Major methodological approaches in the literature\n"
            f"- Comparative strengths and limitations\n\n"
            f"### 4. Current State\n"
            f"- Recent advances and state-of-the-art results\n"
            f"- Remaining gaps in the literature\n\n"
            f"### 5. Open Challenges\n"
            f"- Unresolved questions and controversies\n"
            f"- Directions for future work\n\n"
            f"### 6. Conclusion\n"
            f"- Summary of the literature landscape\n"
        )

    @staticmethod
    def _fallback_related_work(query_text: str, papers: list, key_papers: list) -> str:
        return (
            f"## Related Work: {query_text}\n\n"
            f"### Foundational Work\n"
            f"The literature on {query_text} builds on several key contributions. "
            f"The following {len(key_papers)} papers identified as key: "
            f"{', '.join(p.get('title', p['paper_id']) for p in key_papers) if key_papers else '(none yet identified)'}.\n\n"
            f"### Current Approaches\n"
            f"Recent work has explored various approaches to {query_text}, "
            f"with {len(papers)} papers reviewed in the current workspace.\n\n"
            f"### Gaps and Opportunities\n"
            f"Based on the reviewed literature, several open questions remain. "
            f"Further investigation is needed to establish robust findings."
        )

    @staticmethod
    def _fallback_progress_summary(query_text: str, papers: list, takeaways: list) -> str:
        t_text = "\n".join(f"- {t.get('takeaway_text', '')}" for t in takeaways[:5])
        return (
            f"## Progress Summary: {query_text}\n\n"
            f"**Papers reviewed:** {len(papers)}\n\n"
            f"**Key takeaways:**\n{t_text if t_text else '(none recorded yet)'}\n\n"
            f"**Next steps:** Continue reading in this area to build a comprehensive "
            f"understanding, then begin synthesizing findings."
        )

    @staticmethod
    def _fallback_supervisor_update(query_text: str, papers: list, takeaways: list) -> str:
        return (
            f"## Supervisor Update: {query_text}\n\n"
            f"**Progress this period:** Reviewed {len(papers)} papers on {query_text}.\n\n"
            f"**Key findings:** "
            f"{'See takeaways below.' if takeaways else 'Still building foundational understanding.'}\n\n"
            f"**Next steps:** Continue literature review and begin synthesizing findings."
        )

    @staticmethod
    def _fallback_memo_suggestions(takeaways: list) -> dict:
        lines = [t.get("takeaway_text", "") for t in takeaways[:3]]
        return {
            "suggested_sections": [
                {
                    "section": "Current Understanding",
                    "suggestion": " ".join(lines) if lines else "No takeaways recorded yet.",
                },
                {
                    "section": "Open Questions",
                    "suggestion": "Consider what gaps remain in the reviewed literature.",
                },
            ],
            "open_questions": ["What are the limitations of current approaches?"],
            "next_directions": ["Continue systematic literature review"],
        }
