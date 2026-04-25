export interface ChatProject {
  chat_project_uid: string;
  owner_user_uid: string;
  name: string;
  description: string | null;
  session_count: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ChatProjectCreateRequest {
  name: string;
  description?: string | null;
}

export interface ChatProjectUpdateRequest {
  name?: string | null;
  description?: string | null;
}

/** Session 上掛載的 Agent（v1.3.3 多 Agent 對話）。 */
export interface SessionAgent {
  session_agent_uid: string;
  agent_uid: string;
  agent_name: string | null;
  agent_avatar_url: string | null;
  role: "primary" | "member";
  created_at: string;
}

/** Agent 簡要資訊（訊息卡片 responding_agent 用）。 */
export interface AgentBrief {
  agent_uid: string;
  name: string;
  avatar_url: string | null;
}

export interface ChatSession {
  chat_session_uid: string;
  chat_project_uid: string | null;
  /** [DEPRECATED v1.3.3] 多 Agent 改看 agents；保留以容過渡期。 */
  agent_uid: string | null;
  agent_name: string | null;
  title: string;
  last_message_at: string | null;
  message_count: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  /** v1.3.3：session 上的所有掛載 agents（primary 排在前面）。 */
  agents: SessionAgent[];
}

export interface ChatSessionCreateRequest {
  chat_project_uid?: string | null;
  /** [DEPRECATED v1.3.3] 單 Agent 路徑；新建議使用 agent_uids。 */
  agent_uid?: string;
  /** v1.3.3：第一個視為 primary，其餘為 member。 */
  agent_uids?: string[];
  title?: string | null;
}

export interface SessionAgentsListData {
  agents: SessionAgent[];
}

export interface ChatSessionUpdateRequest {
  title?: string | null;
}

export interface ChatSessionMoveRequest {
  chat_project_uid: string | null;
}

export type ChatMessageRole = "user" | "assistant" | "system" | "tool";

export interface ChatAttachment {
  chat_attachment_uid: string;
  chat_session_uid: string;
  file_name: string;
  file_type: string;
  file_size: number;
  created_at: string;
}

export interface ChatAttachmentListData {
  items: ChatAttachment[];
}

export interface ChatMessage {
  chat_message_uid: string;
  chat_session_uid: string;
  role: ChatMessageRole;
  content: string;
  token_in: number | null;
  token_out: number | null;
  cost_usd: number | null;
  model: string | null;
  finish_reason: string | null;
  created_at: string;
  attachment_uids: string[] | null;
  attachments: ChatAttachment[] | null;
  /** v1.3.3：哪個 Agent 回的（assistant 訊息有值；user 訊息為 null）。 */
  responding_agent_uid: string | null;
  responding_agent: AgentBrief | null;
}

export interface SkillSuggestionPlaceholderData {
  items: unknown[];
  hint: string;
}

export interface ChatMemory {
  chat_memory_uid: string;
  chat_session_uid: string;
  source_chat_message_uids: string[];
  keywords: string[];
  entities: string[];
  topic: string | null;
  created_at: string;
}

export type SkillSuggestionStatus = "pending" | "approved" | "rejected";

export interface SkillSuggestion {
  idx: number;
  name: string;
  description: string;
  system_prompt: string;
  confidence: number;
  source_memory_uids: string[];
  status: SkillSuggestionStatus;
  created_skill_uid: string | null;
  created_at: string | null;
}

export interface SkillSuggestionApproveResult {
  skill_uid: string;
  name: string;
  description: string;
}
