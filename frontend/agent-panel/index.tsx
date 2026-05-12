import { render } from "preact";
import { useState, useEffect, useCallback } from "preact/hooks";
import { SessionList } from "./components/SessionList";
import { MessageFlow } from "./components/MessageFlow";
import { AgentInput } from "./components/AgentInput";
import * as api from "./api";
import type { AgentSession, AgentMessage, PageContext } from "./types";
import "./styles/agent-panel.css";

declare global {
  interface Window {
    togglePaperAgent?: (open?: boolean) => void;
    paperAgentPageContext?: () => PageContext;
  }
}

function collectPageContext(): PageContext {
  const selected =
    document.querySelector<HTMLElement>(".paper-result-row.is-selected") ||
    document.querySelector<HTMLElement>("[data-paper-id]");
  const queryInput =
    (document.getElementById("paperAgentSearchInput") as HTMLInputElement | null) ||
    (document.getElementById("queryText") as HTMLInputElement | null) ||
    (document.getElementById("workspacePrompt") as HTMLInputElement | null);
  const visible = Array.from(document.querySelectorAll<HTMLElement>("[data-paper-id]"))
    .map((node) => node.dataset.paperId || "")
    .filter(Boolean)
    .slice(0, 25);
  return {
    route: window.location.pathname,
    query: queryInput ? queryInput.value : "",
    selected_paper_id: selected ? selected.dataset.paperId || "" : "",
    selected_paper_title: selected ? selected.dataset.paperTitle || "" : "",
    visible_result_ids: visible,
  };
}

function AgentPanel() {
  const [open, setOpen] = useState(false);
  const [sessionsExpanded, setSessionsExpanded] = useState(false);
  const [sessions, setSessions] = useState<AgentSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<AgentMessage[]>([]);
  const [busy, setBusy] = useState(false);
  const [confirmationToken, setConfirmationToken] = useState<string | null>(null);
  const [panelWidth, setPanelWidth] = useState(360);

  // Expose global toggle
  useEffect(() => {
    window.togglePaperAgent = (nextOpen = true) => setOpen(Boolean(nextOpen));
    window.paperAgentPageContext = collectPageContext;

    function handleEsc(e: KeyboardEvent) {
      if (e.key === "Escape" && open) setOpen(false);
    }
    document.addEventListener("keydown", handleEsc);
    return () => document.removeEventListener("keydown", handleEsc);
  }, [open]);

  // Toggle body class
  useEffect(() => {
    document.body.classList.toggle("agent-panel-open", open);
  }, [open]);

  // Load sessions on open
  useEffect(() => {
    if (open) loadSessions();
  }, [open]);

  async function loadSessions() {
    try {
      const list = await api.listSessions(false, 20);
      setSessions(list);
    } catch {
      /* silent */
    }
  }

  async function loadSession(sessionId: string) {
    try {
      const { session, messages: msgs } = await api.getSession(sessionId);
      setActiveSessionId(session.id);
      setMessages(msgs);
      setSessionsExpanded(false);
    } catch {
      /* silent */
    }
  }

  async function createNewSession() {
    try {
      const session = await api.createSession();
      setActiveSessionId(session.id);
      setMessages([]);
      setSessionsExpanded(false);
      await loadSessions();
    } catch {
      /* silent */
    }
  }

  async function handlePin(id: string, pinned: boolean) {
    await api.updateSession(id, { is_pinned: pinned ? 1 : 0 } as any);
    await loadSessions();
  }

  async function handleArchive(id: string) {
    await api.updateSession(id, { is_archived: 1 } as any);
    if (activeSessionId === id) {
      setActiveSessionId(null);
      setMessages([]);
    }
    await loadSessions();
  }

  async function handleDelete(id: string) {
    await api.deleteSession(id);
    if (activeSessionId === id) {
      setActiveSessionId(null);
      setMessages([]);
    }
    await loadSessions();
  }

  const handleSend = useCallback(async (text: string, isConfirmation = false) => {
    if (busy) return;
    setBusy(true);

    if (!isConfirmation) {
      // Optimistic user message
      const tempMsg: AgentMessage = {
        id: Date.now(),
        session_id: activeSessionId || "",
        role: "user",
        content: text,
        metadata_json: {},
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, tempMsg]);
    }

    try {
      const result = await api.sendMessage(
        activeSessionId,
        text,
        collectPageContext(),
        isConfirmation ? (confirmationToken || undefined) : undefined
      );

      // Clear token after sending
      setConfirmationToken(null);

      // Update session ID if newly created
      if (result.session?.id && !activeSessionId) {
        setActiveSessionId(result.session.id);
      }

      // Add assistant reply
      if (result.reply) {
        const assistantMsg: AgentMessage = {
          id: Date.now() + 1,
          session_id: result.session?.id || "",
          role: "assistant",
          content: result.reply,
          metadata_json: {
            tool_results: result.tool_results || [],
            actions: result.actions || [],
            requires_confirmation: result.requires_confirmation,
          },
          created_at: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, assistantMsg]);

        if (result.requires_confirmation) {
          setConfirmationToken(result.confirmation_token || "required");
        }
      }

      // Handle navigation
      if (result.state_updates?.navigate) {
        window.location.href = result.state_updates.navigate;
      }

      // Dispatch queue updates
      for (const action of result.actions || []) {
        if (action.type === "queue" && action.paper_id) {
          document.dispatchEvent(
            new CustomEvent("paper-agent-queue-update", {
              detail: { paperId: action.paper_id, status: action.status },
            })
          );
        }
      }

      await loadSessions();
    } catch (err) {
      const errorMsg: AgentMessage = {
        id: Date.now() + 2,
        session_id: activeSessionId || "",
        role: "system",
        content: `Error: ${err instanceof Error ? err.message : String(err)}`,
        metadata_json: {},
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setBusy(false);
    }
  }, [activeSessionId, busy, confirmationToken]);

  // Resize handler
  function handleResizeStart(e: MouseEvent) {
    e.preventDefault();
    const startX = e.clientX;
    const startWidth = panelWidth;

    function onMove(ev: MouseEvent) {
      const delta = startX - ev.clientX;
      setPanelWidth(Math.max(280, Math.min(600, startWidth + delta)));
    }
    function onUp() {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
    }
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  }

  return (
    <>
      {/* Floating launcher button */}
      {!open && (
        <button
          class="ap-launcher"
          onClick={() => setOpen(true)}
          aria-label="Open Paper Agent"
        >
          <svg width="20" height="20" viewBox="0 0 32 32" fill="none">
            <path d="M9 5.5h9.25L24 11.25V26.5H9z" stroke="currentColor" stroke-width="2.2" stroke-linejoin="round"/>
            <path d="M18.25 5.5v6h5.75" stroke="currentColor" stroke-width="2.2" stroke-linejoin="round"/>
            <circle cx="22.5" cy="22.5" r="2.6" fill="currentColor"/>
          </svg>
        </button>
      )}

      {/* Side panel */}
      {open && (
        <aside
          class="ap-panel"
          style={{ width: `${panelWidth}px` }}
          aria-label="Paper Agent panel"
        >
          {/* Resize handle */}
          <div class="ap-resize-handle" onMouseDown={handleResizeStart} />

          {/* Header */}
          <div class="ap-header">
            <div class="ap-header-left">
              <button
                class="ap-header-btn"
                onClick={() => setSessionsExpanded(!sessionsExpanded)}
                title="Sessions"
              >
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <path d="M2 4h12M2 8h12M2 12h12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                </svg>
              </button>
              <strong class="ap-header-title">Paper Agent</strong>
            </div>
            <button
              class="ap-header-btn"
              onClick={() => setOpen(false)}
              aria-label="Close panel"
            >
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
              </svg>
            </button>
          </div>

          {/* Session list (collapsible) */}
          {sessionsExpanded && (
            <SessionList
              sessions={sessions}
              activeId={activeSessionId}
              onSelect={loadSession}
              onCreate={createNewSession}
              onPin={handlePin}
              onArchive={handleArchive}
              onDelete={handleDelete}
            />
          )}

          {/* Message flow */}
          <MessageFlow messages={messages} busy={busy} />

          {/* Confirmation Prompt */}
          {confirmationToken && (
            <div class="ap-confirmation">
              <div class="ap-confirmation-msg">This action requires your confirmation.</div>
              <div class="ap-confirmation-actions">
                <button 
                  class="ap-btn ap-btn-primary" 
                  onClick={() => handleSend("confirm", true)}
                >
                  Confirm
                </button>
                <button 
                  class="ap-btn ap-btn-ghost" 
                  onClick={() => setConfirmationToken(null)}
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          {/* Input */}
          <AgentInput onSend={handleSend} disabled={busy || !!confirmationToken} />
        </aside>
      )}
    </>
  );
}

// Mount
const root = document.getElementById("paper-agent-root");
if (root) {
  render(<AgentPanel />, root);
}
