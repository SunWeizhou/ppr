"""Rule-based evidence claim generation for workspace analysis.

This service is intentionally provider-free. It creates inspectable claims from
metadata and abstracts so the workspace works without an AI provider.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

from state_store import _canonical_paper_id


class EvidenceClaimService:
    """Build evidence-linked claims without external network or LLM calls."""

    def build_rule_claims(
        self,
        paper: Dict,
        research_question: Optional[Dict] = None,
    ) -> List[Dict]:
        paper = dict(paper or {})
        question = dict(research_question or {})
        paper_id = _canonical_paper_id(paper.get("id") or paper.get("paper_id") or "")
        if not paper_id:
            raise ValueError("Missing paper id")

        title = str(paper.get("title") or "").strip()
        abstract = str(paper.get("abstract") or paper.get("summary") or "").strip()
        categories = paper.get("categories") or []
        if isinstance(categories, str):
            categories = [categories]

        claims: List[Dict] = []
        question_id = question.get("id")

        if abstract:
            first_sentence = self._first_sentence(abstract)
            claims.append(
                self._claim(
                    paper_id=paper_id,
                    research_question_id=question_id,
                    claim=f"The abstract states the paper addresses: {first_sentence}",
                    evidence_text=first_sentence,
                    evidence_source="abstract",
                    claim_type="factual",
                )
            )
        else:
            claims.append(
                self._claim(
                    paper_id=paper_id,
                    research_question_id=question_id,
                    claim="The paper has no cached abstract, so analysis is limited to metadata.",
                    evidence_text=title,
                    evidence_source="metadata",
                    claim_type="gap",
                )
            )

        if categories:
            claims.append(
                self._claim(
                    paper_id=paper_id,
                    research_question_id=question_id,
                    claim=f"The paper is categorized under: {', '.join(categories[:4])}.",
                    evidence_text=", ".join(categories[:4]),
                    evidence_source="metadata",
                    claim_type="factual",
                )
            )

        query_text = str(question.get("query_text") or "").strip()
        if query_text:
            overlap = self._keyword_overlap(query_text, f"{title} {abstract}")
            if overlap:
                claims.append(
                    self._claim(
                        paper_id=paper_id,
                        research_question_id=question_id,
                        claim=(
                            "This paper appears relevant to the research question "
                            f"because it matches: {', '.join(overlap[:6])}."
                        ),
                        evidence_text=f"Research question: {query_text}",
                        evidence_source="metadata",
                        claim_type="interpretive",
                    )
                )
            else:
                claims.append(
                    self._claim(
                        paper_id=paper_id,
                        research_question_id=question_id,
                        claim="No direct keyword overlap was found with the research question.",
                        evidence_text=f"Research question: {query_text}",
                        evidence_source="metadata",
                        claim_type="caveat",
                    )
                )

        return claims

    def _claim(
        self,
        *,
        paper_id: str,
        research_question_id,
        claim: str,
        evidence_text: str,
        evidence_source: str,
        claim_type: str,
    ) -> Dict:
        return {
            "paper_id": paper_id,
            "research_question_id": research_question_id,
            "claim": claim,
            "evidence_text": evidence_text,
            "evidence_source": evidence_source,
            "claim_type": claim_type,
            "analyst": "rule",
        }

    def _first_sentence(self, text: str) -> str:
        parts = re.split(r"(?<=[.!?])\s+", text.strip())
        sentence = parts[0].strip() if parts else text.strip()
        return sentence[:500]

    def _keyword_overlap(self, query_text: str, target_text: str) -> List[str]:
        query_terms = {
            token.lower()
            for token in re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", query_text)
        }
        target = target_text.lower()
        return sorted(term for term in query_terms if term in target)
