"""Paper Agent service layer.

The Agent is intentionally thin: it plans from the current page context, then
executes local tools through StateStore/services. Provider-backed planning is an
optional enhancement; deterministic fallback remains the offline path.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import quote

from app.services.ai_providers import NoProvider, ProviderError, build_ai_provider_from_env


DESTRUCTIVE_TERMS = ("delete", "remove all", "overwrite api key", "bulk archive", "clear all")

VALID_INTENTS = frozenset({
    "answer", "search", "save", "watch",
    "collection", "planner", "analysis", "summarize", "recommendations",
    "read_next", "memo_update", "generate_review", "suggest_coverage", "key_paper_why",
})


@dataclass(frozen=True)
class AgentPlan:
    intent: str
    query: str = ""
    status: str = ""
    steps: list = field(default_factory=list)


class AgentSafetyPolicy:
    """Centralized confirmation policy for Agent-executed actions."""

    @staticmethod
    def requires_confirmation(message: str, plan: AgentPlan) -> bool:
        text = str(message or "").lower()
        if any(term in text for term in DESTRUCTIVE_TERMS):
            return True
        return plan.intent in {"delete", "bulk_archive", "overwrite_api_key"}


class AgentService:
    def __init__(self, state_store, *, provider_factory=build_ai_provider_from_env):
        self.state_store = state_store
        self.provider_factory = provider_factory
        self.safety = AgentSafetyPolicy()

    def handle_message(
        self,
        message: str,
        session_id: Optional[str] = None,
        page_context: Optional[dict] = None,
        confirmation_token: Optional[str] = None,
    ) -> dict:
        """Handle a user message within a session context.

        If session_id is None, creates a new session automatically.
        Persists both user and assistant messages to the session.

        If confirmation_token is provided, resumes a previously
        saved pending action instead of planning a new one.
        """
        page_context = page_context or {}
        message = str(message or "").strip()

        # Resolve or create session
        session = self._resolve_session(session_id)
        session_id = session["id"]

        # Load conversation history for context
        history = self.state_store.get_session_messages(session_id, limit=20)
        is_first_message = len(history) == 0

        # ---- Confirmation resume path ----
        if confirmation_token:
            return self._resume_confirmation(
                confirmation_token, session_id, message, page_context, history, is_first_message,
            )

        # ---- Normal planning path ----
        tool_results: list = []
        actions: list = []
        state_updates: dict = {}

        plan = self._plan(message, page_context, tool_results, history)

        if self.safety.requires_confirmation(message, plan):
            # Store the pending action for later confirmation
            pending = self.state_store.create_agent_pending_confirmation(
                session_id=session_id,
                message=message,
                plan_json=json.dumps({
                    "intent": plan.intent,
                    "query": plan.query,
                    "status": plan.status,
                    "steps": plan.steps,
                }),
                page_context_json=json.dumps(page_context),
            )
            reply = "This action requires your confirmation before I run it."
            self._persist_turn(session_id, message, reply, {"confirmation": "required"})
            return self._response(
                reply,
                session=self._fresh_session(session_id),
                actions=[{"type": "confirmation", "status": "required"}],
                requires_confirmation=True,
                confirmation_token=pending["token"],
                expires_at=pending["expires_at"],
                tool_results=tool_results,
            )

        # Execute the plan
        result = self._execute(plan, message, page_context, tool_results, actions, state_updates, history)

        # Persist messages
        metadata = {
            "tool_results": tool_results,
            "actions": actions,
            "state_updates": state_updates,
        }
        self._persist_turn(session_id, message, result, metadata)

        # Auto-title on first message
        if is_first_message:
            self._auto_title(session_id, message)

        return self._response(
            result,
            session=self._fresh_session(session_id),
            actions=actions,
            state_updates=state_updates,
            tool_results=tool_results,
        )

    def _resume_confirmation(
        self,
        token: str,
        session_id: str,
        message: str,
        page_context: dict,
        history: list,
        is_first_message: bool,
    ) -> dict:
        """Resume a previously confirmed action."""
        tool_results: list = []
        actions: list = []
        state_updates: dict = {}

        # Load pending confirmation
        pending = self.state_store.get_agent_pending_confirmation(token)
        if not pending:
            return self._response(
                "This confirmation token is invalid or has already been used.",
                session=self._fresh_session(session_id),
                actions=[{"type": "confirmation", "status": "failed"}],
                tool_results=tool_results,
            )

        # Validate session match
        if pending["session_id"] != session_id:
            return self._response(
                "This confirmation belongs to a different session.",
                session=self._fresh_session(session_id),
                actions=[{"type": "confirmation", "status": "failed"}],
                tool_results=tool_results,
            )

        # Validate status
        if pending["status"] != "pending":
            reason = "expired" if pending["status"] == "expired" else "already consumed"
            return self._response(
                f"This confirmation has {reason}.",
                session=self._fresh_session(session_id),
                actions=[{"type": "confirmation", "status": "failed"}],
                tool_results=tool_results,
            )

        # Validate expiry
        now = datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat() + "Z"
        if pending["expires_at"] < now:
            self.state_store.clean_expired_agent_confirmations()
            return self._response(
                "This confirmation has expired. Please try the action again.",
                session=self._fresh_session(session_id),
                actions=[{"type": "confirmation", "status": "expired"}],
                tool_results=tool_results,
            )

        # Reconstruct plan and page context
        try:
            plan_data = json.loads(pending["plan_json"])
            stored_context = json.loads(pending["page_context_json"])
        except (json.JSONDecodeError, TypeError):
            return self._response(
                "Could not restore the original action. Please try again.",
                session=self._fresh_session(session_id),
                actions=[{"type": "confirmation", "status": "failed"}],
                tool_results=tool_results,
            )

        plan = AgentPlan(
            intent=plan_data.get("intent", ""),
            query=plan_data.get("query", ""),
            status=plan_data.get("status", ""),
            steps=plan_data.get("steps", []),
        )

        # Execute the original action
        original_message = pending.get("message", message)
        merged_context = {**stored_context, **page_context}
        result = self._execute(plan, original_message, merged_context, tool_results, actions, state_updates, history)

        # Mark consumed
        self.state_store.consume_agent_pending_confirmation(token)

        # Persist messages
        metadata = {
            "tool_results": tool_results,
            "actions": actions,
            "state_updates": state_updates,
            "confirmed": True,
        }
        self._persist_turn(session_id, original_message, result, metadata)

        # Auto-title on first message
        if is_first_message:
            self._auto_title(session_id, original_message)

        return self._response(
            result,
            session=self._fresh_session(session_id),
            actions=actions,
            state_updates=state_updates,
            tool_results=tool_results,
        )

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def _resolve_session(self, session_id: Optional[str]) -> dict:
        """Get existing session or create a new one."""
        if session_id:
            session = self.state_store.get_agent_session(session_id)
            if session:
                return session
        return self.state_store.create_agent_session()

    def _fresh_session(self, session_id: str) -> dict:
        """Reload session to get updated counts."""
        session = self.state_store.get_agent_session(session_id)
        if not session:
            return {"id": session_id, "title": "Unknown", "message_count": 0}
        return {
            "id": session["id"],
            "title": session["title"],
            "message_count": session["message_count"],
            "last_active": session.get("last_active", ""),
        }

    def _persist_turn(self, session_id: str, user_msg: str, reply: str, metadata: dict) -> None:
        """Save user message and assistant reply to the session."""
        self.state_store.add_agent_message(session_id, "user", user_msg)
        self.state_store.add_agent_message(session_id, "assistant", reply, metadata=metadata)

    def _auto_title(self, session_id: str, first_message: str) -> None:
        """Generate a session title from the first message."""
        title = first_message[:50].strip()
        if len(first_message) > 50:
            space = title.rfind(" ")
            if space > 20:
                title = title[:space]
            title += "..."

        try:
            provider = self.provider_factory()
            if not isinstance(provider, NoProvider) and hasattr(provider, "chat"):
                llm_title = provider.chat(
                    [
                        {
                            "role": "system",
                            "content": (
                                "Generate a concise title (max 40 characters) for a research "
                                "assistant conversation. Return ONLY the title text, no quotes."
                            ),
                        },
                        {"role": "user", "content": first_message},
                    ],
                    page_context={},
                )
                llm_title = str(llm_title or "").strip().strip('"').strip("'")
                if 3 <= len(llm_title) <= 60:
                    title = llm_title
        except Exception:
            pass

        self.state_store.update_agent_session(session_id, title=title)


    def _execute(
        self,
        plan: AgentPlan,
        message: str,
        page_context: dict,
        tool_results: list,
        actions: list,
        state_updates: dict,
        history: list[dict] = None,
    ) -> str:
        """Execute a plan and return the reply text."""
        selected_paper_id = str(page_context.get("selected_paper_id") or "").strip()
        selected_title = str(
            page_context.get("selected_paper_title") or selected_paper_id or "this paper"
        )

        if plan.intent == "save" and selected_paper_id:
            return self._exec_queue(plan, selected_paper_id, selected_title, message, actions, tool_results)

        if plan.intent == "collection" and selected_paper_id:
            return self._create_collection(message, page_context, selected_paper_id, selected_title, actions, tool_results)

        if plan.intent == "watch":
            return self._exec_watch(plan, page_context, message, actions, tool_results)

        if plan.intent == "search":
            return self._exec_search(plan, page_context, actions, tool_results, state_updates)

        if plan.intent == "recommendations":
            state_updates["navigate"] = "/recommendations"
            actions.append({"type": "navigate", "target": "recommendations"})
            tool_results.append({"tool": "open_recommendations", "status": "scheduled"})
            return "Opening the **Recommendations** workspace."

        if plan.intent == "planner":
            return (
                "Planner execution is available from a research question workspace. "
                "Create or select a question first."
            )

        if plan.intent == "analysis" and selected_paper_id:
            actions.append({"type": "analysis", "paper_id": selected_paper_id, "status": "available_on_detail"})
            state_updates["navigate"] = f"/papers/{quote(selected_paper_id)}"
            tool_results.append({"tool": "generate_paper_analysis", "status": "scheduled", "paper_id": selected_paper_id})
            return f"I can generate analysis for **{selected_title}** on the detail page."

        if plan.intent == "summarize" and selected_paper_id:
            return self._summarize_selected_paper(selected_paper_id, selected_title, actions, tool_results)

        # ---- New research-assistant behaviors (F-AGENT-2) ----
        rq_id = page_context.get("research_question_id")

        if plan.intent == "read_next" and rq_id:
            return self._exec_read_next(int(rq_id), actions, tool_results)

        if plan.intent == "memo_update" and rq_id:
            return self._exec_memo_update_suggestions(int(rq_id), actions, tool_results)

        if plan.intent == "generate_review" and rq_id:
            return self._exec_generate_review(int(rq_id), actions, tool_results)

        if plan.intent == "suggest_coverage" and rq_id:
            return self._exec_suggest_coverage(int(rq_id), actions, tool_results)

        if plan.intent == "key_paper_why" and rq_id and selected_paper_id:
            return self._exec_key_paper_why(int(rq_id), selected_paper_id, selected_title, actions, tool_results)

        if plan.intent in ("read_next", "memo_update", "generate_review", "suggest_coverage", "key_paper_why"):
            return (
                "I need a workspace context to help with that. "
                "Open a research question workspace first, then ask me again."
            )

        return self._answer_chat(message, page_context, tool_results, history)

    def _exec_queue(self, plan, paper_id, title, message, actions, tool_results) -> str:
        self.state_store.upsert_queue_item(
            paper_id, "Inbox",
            source="paper_agent",
            decision_context=f"Paper Agent request: {message}",
        )
        actions.append({"type": "queue", "paper_id": paper_id, "status": "Inbox"})
        tool_results.append({
            "tool": "mark_reading_decision", "status": "succeeded",
            "paper_id": paper_id, "decision": "Inbox",
        })
        return f"Added **{title}** to Reading."

    def _exec_watch(self, plan, page_context, message, actions, tool_results) -> str:
        query = plan.query or str(page_context.get("query") or message).strip()
        sub = self.state_store.create_subscription(
            "query",
            query[:48] or "Paper Agent watch",
            query,
            payload_json={"source": "paper_agent", "description": "Created by Paper Agent"},
        )
        actions.append({"type": "watch", "subscription_id": sub["id"], "query": query})
        tool_results.append({"tool": "create_watch", "status": "succeeded", "subscription_id": sub["id"], "query": query})
        return f"Watching **{query}**."

    def _exec_search(self, plan, page_context, actions, tool_results, state_updates) -> str:
        query = plan.query or str(page_context.get("query") or "").strip()
        actions.append({"type": "search", "query": query})
        tool_results.append({"tool": "search_papers", "status": "scheduled", "query": query})
        state_updates["navigate"] = f"/search?q={quote(query)}" if query else "/search"
        return f"Searching for **{query}**." if query else "Tell me what to search for."

    # ------------------------------------------------------------------
    # Planning
    # ------------------------------------------------------------------

    def _plan(
        self,
        message: str,
        page_context: dict,
        tool_results: list,
        history: Optional[list] = None,
    ) -> AgentPlan:
        fallback = self._fallback_plan(message, page_context)
        if fallback.intent != "answer":
            return fallback
        provider_plan = self._provider_plan(message, page_context, tool_results, history or [])
        if provider_plan:
            return provider_plan
        return fallback

    def _provider_plan(
        self,
        message: str,
        page_context: dict,
        tool_results: list,
        history: Optional[list] = None,
    ) -> AgentPlan | None:
        try:
            provider = self.provider_factory()
            if isinstance(provider, NoProvider) or not hasattr(provider, "chat"):
                return None

            # Build context-aware messages for planning
            messages = [
                {
                    "role": "system",
                    "content": (
                        "Classify a Paper Agent user request. Return JSON only with keys "
                        "intent and query. Valid intents: answer, search, save, "
                        "watch, collection, planner, analysis, summarize, "
                        "recommendations. Do not execute tools."
                    ),
                },
                {"role": "system", "content": json.dumps(page_context, ensure_ascii=False, sort_keys=True)},
            ]

            # Add recent history for context
            for msg in (history or [])[-6:]:
                role = msg.get("role", "user")
                if role in ("user", "assistant"):
                    messages.append({"role": role, "content": msg.get("content", "")})

            messages.append({"role": "user", "content": message})

            content = provider.chat(messages, page_context=page_context)
            parsed = self._extract_json(content)
            intent = str(parsed.get("intent") or "").strip().lower()
            if intent in VALID_INTENTS:
                tool_results.append({"tool": "plan_intent", "status": "succeeded", "model": getattr(provider, "model_name", "provider")})
                return AgentPlan(intent=intent, query=str(parsed.get("query") or "").strip())
        except (json.JSONDecodeError, KeyError, TypeError):
            return None
        except Exception as exc:
            tool_results.append({"tool": "plan_intent", "status": "degraded", "error": str(exc)})
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
                return json.loads(text[start : end + 1])
            raise

    @staticmethod
    def _fallback_plan(message: str, page_context: dict) -> AgentPlan:
        text = str(message or "").lower()
        if "recommend" in text or "推荐" in text:
            return AgentPlan("recommendations")
        if "collection" in text or "collect this" in text:
            return AgentPlan("collection")
        if any(word in text for word in ("summarize", "summary", "what is this paper", "总结")):
            return AgentPlan("summarize")
        if any(word in text for word in ("analysis", "analyze", "analyse", "分析")):
            return AgentPlan("analysis")
        if any(word in text for word in ("save", "saved", "keep", "收藏", "保存")):
            return AgentPlan("save")
        if any(word in text for word in ("watch", "subscribe", "monitor", "追踪", "监控")):
            return AgentPlan("watch", query=str(page_context.get("query") or message).strip())
        if any(word in text for word in ("planner", "plan")):
            return AgentPlan("planner")
        # New research-assistant intents
        if any(phrase in text for phrase in ("read next", "what should i read", "what to read")):
            return AgentPlan("read_next")
        if any(phrase in text for phrase in ("memo update", "update memo", "memo section", "update my memo")):
            return AgentPlan("memo_update")
        if any(phrase in text for phrase in ("generate review", "weekly review", "this week review", "create review")):
            return AgentPlan("generate_review")
        if any(phrase in text for phrase in ("suggest coverage", "missing coverage", "literature gap", "what am i missing")):
            return AgentPlan("suggest_coverage")
        if any(phrase in text for phrase in ("key paper", "why is this key", "why key", "为什么是重要论文")):
            return AgentPlan("key_paper_why")
        if any(word in text for word in ("search", "find", "look for", "检索", "搜索", "查找")):
            query = message
            for token in ("search", "find", "look for", "检索", "搜索", "查找"):
                query = query.replace(token, " ")
            return AgentPlan("search", query=" ".join(query.split()))
        return AgentPlan("answer")

    # ------------------------------------------------------------------
    # Tool implementations
    # ------------------------------------------------------------------

    def _create_collection(self, message, page_context, selected_paper_id, selected_title, actions, tool_results) -> str:
        query = str(page_context.get("query") or "").strip()
        base_name = query[:48] if query else selected_title[:48]
        name = base_name or "Paper Agent collection"
        collection = None
        for suffix in ("", " collection", f" {selected_paper_id[-6:]}"):
            try:
                collection = self.state_store.create_collection(
                    (name + suffix).strip()[:72],
                    description=f"Created by Paper Agent from {selected_title}.",
                    query_text=query,
                )
                break
            except Exception:
                collection = None
        if collection is None:
            tool_results.append({"tool": "create_collection", "status": "failed", "error": "duplicate_collection"})
            return "I could not create a collection because a matching collection already exists."
        self.state_store.add_paper_to_collection(
            collection["id"],
            selected_paper_id,
            note=f"Added by Paper Agent from request: {message}",
        )
        actions.append({"type": "collection", "collection_id": collection["id"], "paper_id": selected_paper_id})
        tool_results.append({
            "tool": "create_collection",
            "status": "succeeded",
            "collection_id": collection["id"],
            "paper_id": selected_paper_id,
        })
        return f'Created collection **{collection["name"]}** and added **{selected_title}**.'

    def _summarize_selected_paper(self, selected_paper_id, selected_title, actions, tool_results) -> str:
        metadata = {}
        getter = getattr(self.state_store, "get_paper_metadata", None)
        if callable(getter):
            metadata = getter(selected_paper_id) or {}
        abstract = str(metadata.get("abstract") or metadata.get("summary") or "").strip()
        if abstract:
            summary = abstract[:900] + ("..." if len(abstract) > 900 else "")
            reply = f"### {selected_title}\n\n{summary}"
        else:
            reply = f'I do not have an abstract for **{selected_title}** yet.'
        actions.append({"type": "summary", "paper_id": selected_paper_id})
        tool_results.append({"tool": "summarize_selected_paper", "status": "succeeded", "paper_id": selected_paper_id})
        return reply

    # ------------------------------------------------------------------
    # New research-assistant behaviors (F-AGENT-2)
    # ------------------------------------------------------------------

    def _exec_read_next(self, rq_id: int, actions: list, tool_results: list) -> str:
        """Suggest what to read next based on workspace state and RAG retrieval."""
        ws = self.state_store.get_research_question(rq_id) or {}
        query_text = ws.get("query_text", "")

        # Use RAG to find most relevant read papers
        try:
            from app.services.rag_service import RagRetrievalService
            rag = RagRetrievalService(self.state_store)
            rag_results = rag.query(rq_id, query_text, max_results=3)
        except Exception:
            rag_results = []

        # Get inbox / reading papers
        queue = self.state_store.list_queue_items(research_question_id=rq_id) or []
        reading_items = [q for q in queue if q.get("status") == "Inbox"]
        read_items = [q for q in queue if q.get("status") == "Completed"]

        key_papers = self.state_store.list_workspace_papers(rq_id, relationship="key_confirmed") or []

        actions.append({"type": "read_next", "research_question_id": rq_id})
        tool_results.append({"tool": "read_next_suggestion", "status": "succeeded", "research_question_id": rq_id})

        lines = [f"### What to read next for: {query_text}", ""]
        if reading_items:
            lines.append(f"You have **{len(reading_items)}** papers in your reading queue:")
            for item in reading_items[:5]:
                meta = self.state_store.get_paper_metadata(item["paper_id"]) or {}
                title = meta.get("title", item["paper_id"])
                lines.append(f"- [{title}](/papers/{item['paper_id']})")
            lines.append("")
        if rag_results:
            lines.append("**Most relevant papers already read (via semantic search):**")
            for p in rag_results:
                lines.append(f"- [{p['title']}](/papers/{p['paper_id']}) — "
                             f"score: {p['score']:.2f}")
            lines.append("")
        if key_papers:
            lines.append(f"**{len(key_papers)}** key papers identified. "
                         f"Consider comparing these in your memo.")
        if not reading_items and not read_items:
            lines.append("No papers yet. Try searching for your topic first.")
        return "\n".join(lines)

    def _exec_memo_update_suggestions(self, rq_id: int, actions: list, tool_results: list) -> str:
        """Suggest which memo sections need updating."""
        from app.services.writing_prep_service import WritingPrepService

        service = WritingPrepService(self.state_store)
        result = service.generate_memo_suggestions(rq_id)

        ws = self.state_store.get_research_question(rq_id) or {}
        query_text = ws.get("query_text", "")

        actions.append({"type": "memo_update_suggestions", "research_question_id": rq_id})
        tool_results.append({"tool": "memo_update_suggestion", "status": "succeeded", "research_question_id": rq_id})

        lines = [f"### Suggested Memo Updates: {query_text}", ""]
        for sec in result.get("suggested_sections", []):
            lines.append(f"**{sec['section']}**")
            lines.append(f"> {sec['suggestion']}")
            lines.append("")
        lines.append("**Open questions to consider:**")
        for q in result.get("open_questions", []):
            lines.append(f"- {q}")
        lines.append("")
        lines.append("**Next directions:**")
        for d in result.get("next_directions", []):
            lines.append(f"- {d}")
        return "\n".join(lines)

    def _exec_generate_review(self, rq_id: int, actions: list, tool_results: list) -> str:
        """Generate this week's review."""
        from app.services.weekly_review_service import WeeklyReviewService

        ws = self.state_store.get_research_question(rq_id) or {}
        query_text = ws.get("query_text", "")

        service = WeeklyReviewService(self.state_store)
        review = service.generate_review(rq_id)

        actions.append({"type": "generate_review", "research_question_id": rq_id})
        tool_results.append({"tool": "generate_review", "status": "succeeded", "research_question_id": rq_id})

        lines = [
            f"### Weekly Review Generated for: {query_text}",
            "",
            review.get("content", ""),
            "",
            f"You can [edit and save this review](/workspaces/{rq_id}/review?week_start={review['week_start']}).",
        ]
        return "\n".join(lines)

    def _exec_suggest_coverage(self, rq_id: int, actions: list, tool_results: list) -> str:
        """Suggest missing literature coverage."""
        ws = self.state_store.get_research_question(rq_id) or {}
        query_text = ws.get("query_text", "")

        key_papers = self.state_store.list_workspace_papers(rq_id, relationship="key_confirmed") or []
        read_papers = self.state_store.list_workspace_papers(rq_id, relationship="read") or []

        actions.append({"type": "suggest_coverage", "research_question_id": rq_id})
        tool_results.append({"tool": "suggest_coverage", "status": "succeeded", "research_question_id": rq_id})

        lines = [f"### Literature Coverage: {query_text}", ""]
        lines.append(f"**Key papers identified:** {len(key_papers)}")
        lines.append(f"**Read papers:** {len(read_papers)}")
        lines.append("")
        lines.append("**Suggestions to expand coverage:**")
        lines.append("1. Search for recent survey papers on this topic")
        lines.append("2. Check the references cited by your key papers")
        lines.append("3. Look for benchmark datasets and evaluation papers")
        lines.append("4. Consider adjacent sub-fields that might have relevant methods")
        lines.append("")
        if read_papers:
            lines.append("Use **Search** to find more papers on this topic, "
                         f"or try the [Recommendations](/recommendations?q={query_text}) page.")
        return "\n".join(lines)

    def _exec_key_paper_why(self, rq_id: int, paper_id: str, title: str, actions: list, tool_results: list) -> str:
        """Explain why a paper is marked as a key paper."""
        wp = self.state_store.get_workspace_paper(paper_id, rq_id)
        meta = self.state_store.get_paper_metadata(paper_id) or {}
        title = meta.get("title", title)
        abstract = meta.get("abstract", "")[:300]

        actions.append({"type": "key_paper_why", "paper_id": paper_id, "research_question_id": rq_id})
        tool_results.append({"tool": "key_paper_explanation", "status": "succeeded", "paper_id": paper_id})

        lines = [f"### Why is \"{title}\" a Key Paper?", ""]
        if wp:
            lines.append(f"**Relationship:** {wp.get('relationship', 'unknown')}")
            lines.append(f"**Reason:** {wp.get('reason', 'Not specified')}")
        lines.append("")
        if abstract:
            lines.append(f"**Abstract preview:** {abstract}...")
            lines.append("")
        lines.append(f"[View full paper details](/papers/{paper_id}?research_question_id={rq_id})")
        return "\n".join(lines)

    def _answer_chat(self, message: str, page_context: dict, tool_results: list[dict], history: list[dict] = None) -> str:
        try:
            provider = self.provider_factory()
            if not isinstance(provider, NoProvider) and hasattr(provider, "chat"):
                reply = provider.chat(
                    self._chat_messages(message, page_context, history),
                    page_context=page_context,
                )
                if reply:
                    tool_results.append({
                        "tool": "chat",
                        "status": "succeeded",
                        "model": getattr(provider, "model_name", "provider"),
                    })
                    return reply
        except (ProviderError, Exception) as exc:
            tool_results.append({"tool": "chat", "status": "degraded", "error": str(exc)})
        return self._fallback_chat_reply(message, page_context)

    def _chat_messages(self, message: str, page_context: dict, history: list[dict] = None) -> list[dict]:
        route = str(page_context.get("route") or "/")
        query = str(page_context.get("query") or "").strip()
        selected_title = str(page_context.get("selected_paper_title") or "").strip()
        context_lines = [f"Current route: {route}"]
        if query:
            context_lines.append(f"Current search query: {query}")
        if selected_title:
            context_lines.append(f"Selected paper: {selected_title}")
        # Inject workspace context when a research_question_id is present
        rq_id = page_context.get("research_question_id")
        if rq_id is not None:
            try:
                ws = self.state_store.get_research_question(int(rq_id))
                if ws:
                    context_lines.append(f"Workspace: {ws.get('title', ws.get('query_text', ''))}")
                    context_lines.append(f"Workspace intent: {ws.get('intent_statement', 'Not specified')}")
                    # Reading stats for this workspace
                    queue = self.state_store.list_queue_items(research_question_id=int(rq_id))
                    reading_count = sum(1 for q in queue if q.get("status") == "Inbox")
                    completed_count = sum(1 for q in queue if q.get("status") == "Completed")
                    context_lines.append(f"Workspace has {reading_count} papers in reading, {completed_count} read")
                    # Memo status
                    memo = self.state_store.get_memo(int(rq_id))
                    has_memo = memo is not None and bool(memo.get("content", "").strip())
                    context_lines.append(f"Research memo: {'written' if has_memo else 'not yet created'}")
            except Exception:
                pass
        msgs = [
            {
                "role": "system",
                "content": (
                    "You are Paper Agent, a concise research assistant inside a local-first "
                    "paper discovery workspace. Use Markdown when it improves readability. "
                    "Help with literature search strategy, paper triage, and current page context."
                ),
            },
            {"role": "system", "content": "\n".join(context_lines)},
        ]
        
        # Add history
        for item in (history or [])[-8:]:
            if item.get("role") in ("user", "assistant"):
                msgs.append({
                    "role": item["role"],
                    "content": item.get("content", "")
                })
        
        msgs.append({"role": "user", "content": message})
        return msgs

    @staticmethod
    def _fallback_chat_reply(message: str, page_context: dict) -> str:
        text = message.lower()
        route = str(page_context.get("route") or "/")
        query = str(page_context.get("query") or "").strip()
        if any(token in text for token in ("你好", "hello", "hi", "hey")):
            return (
                "你好，我是 **Paper Agent**。\n\n"
                "你可以让我：\n"
                "- search papers\n"
                "- save the selected paper\n"
                "- create a watch\n"
                "- create a collection\n"
                "- summarize the selected paper"
            )
        if "怎么" in text or "what can" in text or "help" in text:
            location = "Home" if route == "/" else route.strip("/").title() or "Search"
            return (
                f"Paper Agent can help from the current **{location}** page.\n\n"
                "Try: `search federated learning`, `save this paper`, "
                "`create watch for this query`, or `summarize this paper`."
            )
        if query:
            return (
                f'Paper Agent is looking at **{query}**. I can refine the query, '
                "save promising papers, create a watch, or summarize the selected paper."
            )
        return (
            "Paper Agent can chat about your research workflow and execute local actions: "
            "search papers, save papers, create watches, create "
            "collections, and summarize selected papers."
        )

    @staticmethod
    def _response(
        reply: str,
        *,
        session: Optional[dict] = None,
        actions: Optional[list] = None,
        state_updates: Optional[dict] = None,
        tool_results: Optional[list] = None,
        requires_confirmation: bool = False,
        confirmation_token: str = "",
        expires_at: str = "",
    ) -> dict:
        return {
            "success": True,
            "reply": reply,
            "messages": [{"role": "assistant", "content": reply}],
            "actions": actions or [],
            "state_updates": state_updates or {},
            "requires_confirmation": requires_confirmation,
            "confirmation_token": confirmation_token,
            "expires_at": expires_at,
            "tool_results": tool_results or [],
            "session": session or {},
        }
