export interface AgentSkillSummary {
  skill_uid: string;
  name: string;
}

export interface Agent {
  agent_uid: string;
  owner_user_uid: string;
  owner_username: string | null;
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
  response_format_example: string | null;
  visibility: "public" | "private";
  is_active: boolean;
  skill_uids: string[];
  skills: AgentSkillSummary[];
  favorite_count: number;
  download_count: number;
  is_favorited: boolean;
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
  response_format_example?: string | null;
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
  response_format_example?: string | null;
  skill_uids?: string[];
}

export interface VisibilityRequest {
  visibility: "public" | "private";
}
