export interface AgentTemplate {
  agent_template_uid: string;
  template_key: string;
  label: string;
  description: string | null;
  name: string | null;
  identity: string | null;
  language: string | null;
  style: string | null;
  role_prompt: string | null;
  greeting: string | null;
  temperature: number | null;
  max_tokens: number | null;
  response_format: string | null;
  response_format_example: string | null;
  sort_order: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface AgentTemplateCreateRequest {
  template_key: string;
  label: string;
  description?: string | null;
  name?: string | null;
  identity?: string | null;
  language?: string | null;
  style?: string | null;
  role_prompt?: string | null;
  greeting?: string | null;
  temperature?: number | null;
  max_tokens?: number | null;
  response_format?: string | null;
  response_format_example?: string | null;
  sort_order?: number;
}

export interface AgentTemplateUpdateRequest {
  label?: string;
  description?: string | null;
  name?: string | null;
  identity?: string | null;
  language?: string | null;
  style?: string | null;
  role_prompt?: string | null;
  greeting?: string | null;
  temperature?: number | null;
  max_tokens?: number | null;
  response_format?: string | null;
  response_format_example?: string | null;
  sort_order?: number;
  is_active?: boolean;
}
