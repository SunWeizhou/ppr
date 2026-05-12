export interface AgentSession {
  id: string;
  title: string;
  message_count: number;
  is_pinned: boolean;
  is_archived: boolean;
  last_active: string;
  summary?: string;
  created_at?: string;
}

export interface AgentMessage {
  id: number | string;
  session_id?: string;
  role: "user" | "assistant" | "system" | "tool";
  content: string;
  metadata_json?: Record<string, unknown>;
  created_at?: string;
}

export interface ToolResult {
  tool: string;
  status: string;
  [key: string]: unknown;
}

export interface AgentResponse {
  success: boolean;
  reply?: string;
  messages?: AgentMessage[];
  session?: Partial<AgentSession>;
  actions?: Array<{ type: string; [key: string]: unknown }>;
  state_updates?: Record<string, unknown>;
  requires_confirmation?: boolean;
  confirmation_token?: string;
  expires_at?: string;
  tool_results?: ToolResult[];
}

export interface PageContext {
  route?: string;
  query?: string;
  selected_paper_id?: string;
  selected_paper_title?: string;
  research_question_id?: string;
  [key: string]: unknown;
}
