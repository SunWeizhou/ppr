import React, { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeSanitize from "rehype-sanitize";
import "./agent.css";

declare global {
  interface Window {
    togglePaperAgent?: (open?: boolean) => void;
    sendPaperAgentMessage?: (event: Event | FormEvent) => void;
    paperAgentPageContext?: () => PageContext;
    restorePaperAgentPendingEvent?: () => void;
  }
}

type Role = "system" | "user" | "assistant" | "tool";

type PageContext = {
  route: string;
  query: string;
  selected_paper_id: string;
  selected_paper_title: string;
  visible_result_ids: string[];
};

type AgentMessage = {
  id: string;
  role: Role;
  content: string;
};

type ToolResult = {
  tool?: string;
  status?: string;
  error?: string;
  [key: string]: unknown;
};

type AgentResponse = {
  success: boolean;
  reply?: string;
  messages?: AgentMessage[];
  actions?: Array<{ type?: string; paper_id?: string; status?: string }>;
  tool_results?: ToolResult[];
  state_updates?: { navigate?: string };
  requires_confirmation?: boolean;
};

const pendingEventKey = "paperAgentPendingEvent";
const openAfterNavigateKey = "paperAgentOpenAfterNavigate";

function id(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function requestJson(url: string, init: RequestInit = {}): Promise<AgentResponse> {
  return fetch(url, init).then(async (response) => {
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.success === false) {
      throw new Error(payload.error || `Request failed (${response.status})`);
    }
    return payload;
  });
}

function collectPageContext(): PageContext {
  const selected =
    document.querySelector<HTMLElement>(".paper-result-row.is-selected") ||
    document.querySelector<HTMLElement>("[data-paper-id]");
  const queryInput =
    document.getElementById("paperAgentSearchInput") as HTMLInputElement | null ||
    document.getElementById("queryText") as HTMLInputElement | null ||
    document.getElementById("workspacePrompt") as HTMLInputElement | null;
  const visible = Array.from(document.querySelectorAll<HTMLElement>("[data-paper-id]"))
    .map((node) => node.dataset.paperId || "")
    .filter(Boolean)
    .slice(0, 25);
  return {
    route: window.location.pathname,
    query: queryInput ? queryInput.value : "",
    selected_paper_id: selected ? selected.dataset.paperId || "" : "",
    selected_paper_title: selected ? selected.dataset.paperTitle || "" : "",
    visible_result_ids: visible
  };
}

function formatToolResult(result: ToolResult): string {
  const label = String(result.tool || "tool").replace(/_/g, " ");
  const status = String(result.status || "done");
  if (result.error) {
    return `${label} · ${status}: ${String(result.error)}`;
  }
  return `${label} · ${status}`;
}

function AgentDrawer() {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState("");
  const [messages, setMessages] = useState<AgentMessage[]>([
    {
      id: "welcome",
      role: "system",
      content: "Tell me what to search, save, watch, summarize, or mark for reading."
    }
  ]);
  const threadRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    window.paperAgentPageContext = collectPageContext;
    window.togglePaperAgent = (nextOpen = true) => setOpen(Boolean(nextOpen));
    window.sendPaperAgentMessage = (event: Event | FormEvent) => {
      event.preventDefault();
      const formInput = document.getElementById("agentInput") as HTMLInputElement | null;
      const value = formInput?.value || draft;
      if (formInput) formInput.value = "";
      setDraft("");
      void sendMessage(value);
    };
    window.restorePaperAgentPendingEvent = restorePendingEvent;
    restorePendingEvent();
  }, []);

  useEffect(() => {
    document.body.classList.toggle("agent-drawer-open", open);
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 20);
    }
  }, [open]);

  useEffect(() => {
    if (threadRef.current) {
      threadRef.current.scrollTop = threadRef.current.scrollHeight;
    }
  }, [messages, busy]);

  function restorePendingEvent() {
    let message = "";
    let shouldOpen = false;
    try {
      message = sessionStorage.getItem(pendingEventKey) || "";
      shouldOpen = sessionStorage.getItem(openAfterNavigateKey) === "1";
      sessionStorage.removeItem(pendingEventKey);
      sessionStorage.removeItem(openAfterNavigateKey);
    } catch (_error) {
      message = "";
    }
    if (message) {
      setMessages((existing) => [
        ...existing,
        { id: id("assistant"), role: "assistant", content: message }
      ]);
    }
    if (shouldOpen) setOpen(true);
  }

  async function sendMessage(raw: string) {
    const message = raw.trim();
    if (!message || busy) return;
    const userMessage: AgentMessage = { id: id("user"), role: "user", content: message };
    setMessages((existing) => [...existing, userMessage]);
    setBusy(true);
    try {
      const payload = await requestJson("/api/agent/messages", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, page_context: collectPageContext() })
      });
      const next: AgentMessage[] = [];
      if (payload.reply) {
        next.push({ id: id("assistant"), role: "assistant", content: payload.reply });
      }
      for (const result of payload.tool_results || []) {
        next.push({ id: id("tool"), role: "tool", content: formatToolResult(result) });
      }
      setMessages((existing) => [...existing, ...next]);
      for (const action of payload.actions || []) {
        if (action.type === "queue" && action.paper_id) {
          document.dispatchEvent(new CustomEvent("paper-agent-queue-update", {
            detail: { paperId: action.paper_id, status: action.status }
          }));
        }
      }
      if (payload.state_updates?.navigate) {
        try {
          sessionStorage.setItem(pendingEventKey, payload.reply || "Done.");
          sessionStorage.setItem(openAfterNavigateKey, "1");
        } catch (_error) {
          // Navigation should still happen if session storage is unavailable.
        }
        window.location.href = payload.state_updates.navigate;
      }
    } catch (error) {
      setMessages((existing) => [
        ...existing,
        {
          id: id("system"),
          role: "system",
          content: `Agent request failed: ${error instanceof Error ? error.message : String(error)}`
        }
      ]);
    } finally {
      setBusy(false);
    }
  }

  const statusText = useMemo(() => {
    const context = collectPageContext();
    if (context.selected_paper_title) return `Context: ${context.selected_paper_title}`;
    if (context.query) return `Context: ${context.query}`;
    return "Context: current page";
  }, [open, messages.length]);

  return (
    <>
      <button
        type="button"
        className="agent-launcher"
        id="agentLauncher"
        aria-label="Open Paper Agent"
        onClick={() => setOpen(true)}
      >
        <span className="paper-agent-logo" aria-hidden="true">
          <svg viewBox="0 0 32 32" role="img" focusable="false">
            <path d="M9 5.5h9.25L24 11.25V26.5H9z" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinejoin="round"/>
            <path d="M18.25 5.5v6h5.75" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinejoin="round"/>
            <circle cx="22.5" cy="22.5" r="2.6" fill="currentColor"/>
          </svg>
        </span>
      </button>
      <aside className={`agent-drawer ${open ? "is-open" : ""}`} id="agentDrawer" aria-label="Paper Agent drawer" aria-hidden={!open}>
        <div className="agent-drawer-head">
          <div className="agent-title">
            <span className="paper-agent-logo" aria-hidden="true">
              <svg viewBox="0 0 32 32" role="img" focusable="false">
                <path d="M9 5.5h9.25L24 11.25V26.5H9z" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinejoin="round"/>
                <path d="M18.25 5.5v6h5.75" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinejoin="round"/>
                <circle cx="22.5" cy="22.5" r="2.6" fill="currentColor"/>
              </svg>
            </span>
            <div>
              <strong>Paper Agent</strong>
              <span className="agent-context-line">{statusText}</span>
            </div>
          </div>
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => setOpen(false)}>Close</button>
        </div>
        <div className="agent-thread" id="agentThread" ref={threadRef}>
          {messages.map((message) => (
            <div key={message.id} className={`agent-message agent-message-${message.role}`}>
              <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize]}>
                {message.content}
              </ReactMarkdown>
            </div>
          ))}
          {busy && <div className="agent-message agent-message-loading">Thinking...</div>}
        </div>
        <form
          className="agent-composer"
          id="agentForm"
          onSubmit={(event) => {
            event.preventDefault();
            const value = draft;
            setDraft("");
            void sendMessage(value);
          }}
        >
          <input
            id="agentInput"
            ref={inputRef}
            type="text"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="Ask Paper Agent to do something..."
            autoComplete="off"
            disabled={busy}
          />
          <button type="submit" className="btn btn-primary btn-sm" disabled={busy || !draft.trim()}>
            Send
          </button>
        </form>
      </aside>
    </>
  );
}

const root = document.getElementById("paper-agent-root");
if (root) {
  createRoot(root).render(<AgentDrawer />);
}
