export interface AgentLanguage {
  agent_language_uid: string;
  code: string;
  name: string;
  sort_order: number;
  is_default: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface AgentLanguageCreateRequest {
  code: string;
  name: string;
  sort_order?: number;
  is_default?: boolean;
}

export interface AgentLanguageUpdateRequest {
  name?: string;
  sort_order?: number;
  is_default?: boolean;
  is_active?: boolean;
}
