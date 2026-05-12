import { useEffect, useRef } from "preact/hooks";
import { marked } from "marked";
import type { AgentMessage, ToolResult } from "../types";

interface Props {
  messages: AgentMessage[];
  busy: boolean;
}

// Configure marked for safe output
marked.setOptions({
  breaks: true,
  gfm: true,
});

function renderMarkdown(content: string): string {
  try {
    return marked.parse(content) as string;
  } catch {
    return content;
  }
}

function formatToolChip(meta: Record<string, unknown>): string[] {
  const results = (meta.tool_results || []) as ToolResult[];
  return results
    .filter((r) => r.tool && r.status)
    .map((r) => {
      const label = String(r.tool || "tool").replace(/_/g, " ");
      return `${label}: ${r.status}`;
    });
}

export function MessageFlow({ messages, busy }: Props) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, busy]);

  return (
    <div class="ap-thread">
      {messages.map((msg) => (
        <div key={msg.id} class={`ap-msg ap-msg--${msg.role}`}>
          {msg.role === "assistant" ? (
            <div
              class="ap-msg-content"
              dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.content) }}
            />
          ) : msg.role === "tool" ? (
            <div class="ap-msg-content ap-msg-tool">{msg.content}</div>
          ) : (
            <div class="ap-msg-content">{msg.content}</div>
          )}
          {msg.role === "assistant" && msg.metadata_json && (
            <div class="ap-msg-chips">
              {formatToolChip(msg.metadata_json).map((chip, i) => (
                <span key={i} class="ap-chip">{chip}</span>
              ))}
            </div>
          )}
        </div>
      ))}
      {busy && (
        <div class="ap-msg ap-msg--assistant">
          <div class="ap-msg-content ap-typing">
            <span class="ap-dot" /><span class="ap-dot" /><span class="ap-dot" />
          </div>
        </div>
      )}
      <div ref={endRef} />
    </div>
  );
}
