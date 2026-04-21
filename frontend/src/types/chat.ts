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

export interface ChatSession {
  chat_session_uid: string;
  chat_project_uid: string | null;
  agent_uid: string;
  agent_name: string | null;
  title: string;
  last_message_at: string | null;
  message_count: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ChatSessionCreateRequest {
  chat_project_uid?: string | null;
  agent_uid: string;
  title?: string | null;
}

export interface ChatSessionUpdateRequest {
  title?: string | null;
}

export interface ChatSessionMoveRequest {
  chat_project_uid: string | null;
}

export type ChatMessageRole = "user" | "assistant" | "system" | "tool";

export interface ChatMessage {
  chat_message_uid: string;
  chat_session_uid: string;
  role: ChatMessageRole;
  content: string;
  token_in: number | null;
  token_out: number | null;
  cost_usd: number | null;
  model: string | null;
  created_at: string;
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
