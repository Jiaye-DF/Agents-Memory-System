export interface Agent {
  agent_uid: string;
  owner_uid: string;
  name: string;
  description: string | null;
  language: string | null;
  style: string | null;
  identity: string | null;
  role_prompt: string | null;
  model: string | null;
  temperature: number | null;
  max_tokens: number | null;
  greeting: string | null;
  response_format: string | null;
  visibility: "public" | "private";
  is_active: boolean;
  skill_uids: string[];
  created_at: string;
  updated_at: string;
}

export interface AgentCreateRequest {
  name: string;
  description?: string | null;
  language?: string | null;
  style?: string | null;
  identity?: string | null;
  role_prompt?: string | null;
  model?: string | null;
  temperature?: number | null;
  max_tokens?: number | null;
  greeting?: string | null;
  response_format?: string | null;
  visibility?: "public" | "private";
  skill_uids?: string[];
}

export interface AgentUpdateRequest {
  name?: string | null;
  description?: string | null;
  language?: string | null;
  style?: string | null;
  identity?: string | null;
  role_prompt?: string | null;
  model?: string | null;
  temperature?: number | null;
  max_tokens?: number | null;
  greeting?: string | null;
  response_format?: string | null;
  skill_uids?: string[];
}

export interface VisibilityRequest {
  visibility: "public" | "private";
}
