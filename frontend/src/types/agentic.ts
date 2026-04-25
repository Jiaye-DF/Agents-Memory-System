/**
 * v1.3.6 Agentic Skill 工廠正式版型別。
 *
 * 對應 backend/app/schemas/agentic/skill_suggestion_schemas.py。
 */

export type AgenticSuggestionScope = "session" | "project" | "user";

export type AgenticSuggestionStatus =
  | "pending"
  | "approved"
  | "rejected"
  | "expired";

export interface AgenticSkillSuggestionItem {
  uid: string;
  scope: AgenticSuggestionScope;
  scope_uid: string;
  name: string;
  description: string;
  system_prompt: string;
  confidence: number;
  source_memory_uids: string[];
  status: AgenticSuggestionStatus;
  created_skill_uid: string | null;
  created_at: string;
  updated_at: string;
}

export interface AgenticSkillSuggestionListResponse {
  items: AgenticSkillSuggestionItem[];
  page: number;
  size: number;
  total: number;
}

export interface SuggestionSourceMemoryBrief {
  scope: AgenticSuggestionScope;
  topic: string | null;
  keywords: string[];
  entities: string[];
  created_at: string | null;
}

export interface AgenticSkillSuggestionDetailResponse {
  suggestion: AgenticSkillSuggestionItem;
  source_memories: SuggestionSourceMemoryBrief[];
}

export interface AgenticSkillSuggestionAcceptRequest {
  agent_uid?: string;
}

export interface AgenticSkillSuggestionAcceptResponse {
  skill_uid: string;
  skill_name: string;
  agent_uid: string | null;
  mounted: boolean;
}

export interface AgenticSkillSuggestionRejectResponse {
  uid: string;
  status: AgenticSuggestionStatus;
}

/** 推薦器精簡 schema（不含 system_prompt 全文）。 */
export interface RecommendSuggestionItem {
  uid: string;
  scope: AgenticSuggestionScope;
  name: string;
  description: string;
  confidence: number;
  source_memory_count: number;
}

export interface RecommendSuggestionListResponse {
  items: RecommendSuggestionItem[];
}
