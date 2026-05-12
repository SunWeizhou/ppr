import type { AgentSession } from "../types";

interface Props {
  sessions: AgentSession[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onCreate: () => void;
  onPin: (id: string, pinned: boolean) => void;
  onArchive: (id: string) => void;
  onDelete: (id: string) => void;
}

function timeAgo(iso: string): string {
  if (!iso) return "";
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export function SessionList({
  sessions, activeId, onSelect, onCreate, onPin, onArchive, onDelete,
}: Props) {
  return (
    <div class="ap-sessions">
      <div class="ap-sessions-header">
        <span class="ap-sessions-title">Sessions</span>
        <button class="ap-sessions-new" onClick={onCreate} aria-label="New session">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M7 1v12M1 7h12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
        </button>
      </div>
      <div class="ap-sessions-list">
        {sessions.map((s) => (
          <div
            key={s.id}
            class={`ap-session-row ${s.id === activeId ? "is-active" : ""}`}
            onClick={() => onSelect(s.id)}
          >
            <div class="ap-session-info">
              {s.is_pinned ? <span class="ap-pin-icon" title="Pinned">*</span> : null}
              <span class="ap-session-title">{s.title}</span>
            </div>
            <div class="ap-session-meta">
              <span class="ap-session-count">{s.message_count} msgs</span>
              <span class="ap-session-time">{timeAgo(s.last_active)}</span>
            </div>
            <div class="ap-session-actions" onClick={(e) => e.stopPropagation()}>
              <button
                class="ap-session-btn"
                onClick={() => onPin(s.id, !s.is_pinned)}
                title={s.is_pinned ? "Unpin" : "Pin"}
              >
                {s.is_pinned ? "Unpin" : "Pin"}
              </button>
              <button
                class="ap-session-btn"
                onClick={() => onArchive(s.id)}
                title="Archive"
              >
                Archive
              </button>
              <button
                class="ap-session-btn ap-session-btn--danger"
                onClick={() => onDelete(s.id)}
                title="Delete"
              >
                Delete
              </button>
            </div>
          </div>
        ))}
        {sessions.length === 0 && (
          <div class="ap-sessions-empty">No sessions yet. Click + to start.</div>
        )}
      </div>
    </div>
  );
}
