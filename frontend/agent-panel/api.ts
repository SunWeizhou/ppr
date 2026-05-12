import type { AgentSession, AgentMessage, AgentResponse } from "./types";

const BASE = "/api/agent";

async function request<T>(url: string, init: RequestInit = {}): Promise<T> {
  const resp = await fetch(url, init);
  const payload = await resp.json().catch(() => ({}));
  if (!resp.ok || payload.success === false) {
    throw new Error(payload.error || `Request failed (${resp.status})`);
  }
  return payload;
}

export async function createSession(title?: string): Promise<AgentSession> {
  const data = await request<{ success: boolean; session: AgentSession }>(
    `${BASE}/sessions`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: title || "New Session" }),
    }
  );
  return data.session;
}

export async function listSessions(
  archived = false,
  limit = 20
): Promise<AgentSession[]> {
  const params = new URLSearchParams({
    archived: archived ? "1" : "0",
    limit: String(limit),
  });
  const data = await request<{ sessions: AgentSession[] }>(
    `${BASE}/sessions?${params}`
  );
  return data.sessions;
}

export async function getSession(
  sessionId: string
): Promise<{ session: AgentSession; messages: AgentMessage[] }> {
  return request(`${BASE}/sessions/${sessionId}`);
}

export async function updateSession(
  sessionId: string,
  updates: Partial<Pick<AgentSession, "title" | "is_pinned" | "is_archived">>
): Promise<AgentSession> {
  const data = await request<{ session: AgentSession }>(
    `${BASE}/sessions/${sessionId}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(updates),
    }
  );
  return data.session;
}

export async function deleteSession(sessionId: string): Promise<void> {
  await request(`${BASE}/sessions/${sessionId}`, { method: "DELETE" });
}

export async function sendMessage(
  sessionId: string | null,
  message: string,
  pageContext: Record<string, unknown> = {}
): Promise<AgentResponse> {
  const effectiveId = sessionId || "new";
  return request<AgentResponse>(
    `${BASE}/sessions/${effectiveId}/messages`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, page_context: pageContext }),
    }
  );
}
