export interface LlmModel {
  llm_model_uid: string;
  provider: string;
  model_id: string;
  display_name: string;
  is_default: boolean;
  max_output_tokens: number | null;
}

export interface LlmModelAdmin extends LlmModel {
  is_active: boolean;
  is_deleted: boolean;
  created_at: string;
  updated_at: string;
}

export interface LlmModelCreateRequest {
  model_id: string;
  display_name: string;
  is_default?: boolean;
  max_output_tokens?: number | null;
}

export interface LlmModelUpdateRequest {
  display_name?: string;
  is_active?: boolean;
  is_default?: boolean;
  max_output_tokens?: number | null;
}
