"""Paper Agent service layer.

The Agent is intentionally thin: it plans from the current page context, then
executes local tools through StateStore/services. Provider-backed planning is an
optional enhancement; deterministic fallback remains the offline path.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import quote

from app.services.ai_providers import NoProvider, ProviderError, build_ai_provider_from_env


DESTRUCTIVE_TERMS = ("delete", "remove all", "overwrite api key", "bulk archive", "clear all")

VALID_INTENTS = frozenset({
    "answer", "search", "save", "skim", "deep_read", "watch",
    "collection", "planner", "analysis", "summarize", "recommendations",
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
    ) -> dict:
        """Handle a user message within a session context.

        If session_id is None, creates a new session automatically.
        Persists both user and assistant messages to the session.
        """
        page_context = page_context or {}
        message = str(message or "").strip()

        # Resolve or create session
        session = self._resolve_session(session_id)
        session_id = session["id"]

        # Load conversation history for context
        history = self.state_store.get_session_messages(session_id, limit=20)
        is_first_message = len(history) == 0

        tool_results: list = []
        actions: list = []
        state_updates: dict = {}

        plan = self._plan(message, page_context, tool_results, history)

        if self.safety.requires_confirmation(message, plan):
            reply = "That action needs confirmation before I run it."
            self._persist_turn(session_id, message, reply, {"confirmation": "required"})
            return self._response(
                reply,
                session=self._fresh_session(session_id),
                actions=[{"type": "confirmation", "status": "required"}],
                requires_confirmation=True,
                tool_results=tool_results,
            )

        # Execute the plan
        result = self._execute(plan, message, page_context, tool_results, actions, state_updates)

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
    ) -> str:
        """Execute a plan and return the reply text."""
        selected_paper_id = str(page_context.get("selected_paper_id") or "").strip()
        selected_title = str(
            page_context.get("selected_paper_title") or selected_paper_id or "this paper"
        )

        if plan.intent in {"save", "deep_read", "skim"} and selected_paper_id:
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

        return self._answer_chat(message, page_context, tool_results)

    def _exec_queue(self, plan, paper_id, title, message, actions, tool_results) -> str:
        status = {"save": "Saved", "deep_read": "Deep Read", "skim": "Skim Later"}[plan.intent]
        self.state_store.upsert_queue_item(
            paper_id, status,
            source="paper_agent",
            decision_context=f"Paper Agent request: {message}",
        )
        actions.append({"type": "queue", "paper_id": paper_id, "status": status})
        tool_results.append({
            "tool": "mark_reading_decision", "status": "succeeded",
            "paper_id": paper_id, "decision": status,
        })
        return f"Marked **{title}** as **{status}**."

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
        state_updates["navigate"] = f"/?q={quote(query)}" if query else "/"
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
                        "intent and query. Valid intents: answer, search, save, skim, "
                        "deep_read, watch, collection, planner, analysis, summarize, "
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
        if any(word in text for word in ("deep read", "deepread", "精读")):
            return AgentPlan("deep_read")
        if any(word in text for word in ("skim", "later", "稍后")):
            return AgentPlan("skim")
        if any(word in text for word in ("watch", "subscribe", "monitor", "追踪", "监控")):
            return AgentPlan("watch", query=str(page_context.get("query") or message).strip())
        if any(word in text for word in ("planner", "plan")):
            return AgentPlan("planner")
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

    def _answer_chat(self, message: str, page_context: dict, tool_results: list[dict]) -> str:
        try:
            provider = self.provider_factory()
            if not isinstance(provider, NoProvider) and hasattr(provider, "chat"):
                reply = provider.chat(
                    self._chat_messages(message, page_context),
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

    @staticmethod
    def _chat_messages(message: str, page_context: dict) -> list[dict]:
        route = str(page_context.get("route") or "/")
        query = str(page_context.get("query") or "").strip()
        selected_title = str(page_context.get("selected_paper_title") or "").strip()
        context_lines = [f"Current route: {route}"]
        if query:
            context_lines.append(f"Current search query: {query}")
        if selected_title:
            context_lines.append(f"Selected paper: {selected_title}")
        return [
            {
                "role": "system",
                "content": (
                    "You are Paper Agent, a concise research assistant inside a local-first "
                    "paper discovery workspace. Use Markdown when it improves readability. "
                    "Help with literature search strategy, paper triage, and current page context."
                ),
            },
            {"role": "system", "content": "\n".join(context_lines)},
            {"role": "user", "content": message},
        ]

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
                "- mark it for skim or deep read\n"
                "- create a watch\n"
                "- create a collection\n"
                "- summarize the selected paper"
            )
        if "怎么" in text or "what can" in text or "help" in text:
            location = "Search" if route == "/" else route.strip("/").title() or "Search"
            return (
                f"Paper Agent can help from the current **{location}** page.\n\n"
                "Try: `search federated learning`, `save this paper`, "
                "`deep read this paper`, `create watch for this query`, or "
                "`summarize this paper`."
            )
        if query:
            return (
                f'Paper Agent is looking at **{query}**. I can refine the query, '
                "save promising papers, create a watch, or summarize the selected paper."
            )
        return (
            "Paper Agent can chat about your research workflow and execute local actions: "
            "search papers, save papers, mark reading decisions, create watches, create "
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
    ) -> dict:
        return {
            "success": True,
            "reply": reply,
            "messages": [{"role": "assistant", "content": reply}],
            "actions": actions or [],
            "state_updates": state_updates or {},
            "requires_confirmation": requires_confirmation,
            "confirmation_token": "required" if requires_confirmation else "",
            "tool_results": tool_results or [],
            "session": session or {},
        }
