import type { TagSummary } from "./tags";

export interface Skill {
  skill_uid: string;
  owner_user_uid: string;
  owner_username: string | null;
  name: string;
  description: string;
  original_filename: string;
  file_size: number;
  visibility: "public" | "private";
  is_active: boolean;
  favorite_count: number;
  download_count: number;
  is_favorited: boolean;
  tags?: TagSummary[];
  created_at: string;
  updated_at: string;
}

export interface SkillSearchItem extends Skill {
  score: number;
  ai_reason: string | null;
}

export interface SkillSearchResult {
  items: SkillSearchItem[];
  analysis: string | null;
}

export interface SkillUpdateRequest {
  name?: string;
  description?: string;
}

export interface VisibilityRequest {
  visibility: "public" | "private";
}

export interface FileTreeNode {
  name: string;
  type: "file" | "directory";
  children?: FileTreeNode[];
}

export interface FileContent {
  path: string;
  size: number;
  encoding: "text" | "binary";
  content: string;
  too_large: boolean;
}

export interface SkillUploadParams {
  name: string;
  description: string;
  files: File[];
}

export interface SkillUsageItem {
  agent_uid: string;
  agent_name: string;
  owner_username: string | null;
  visibility: string;
}

export interface SkillUsageResponse {
  items: SkillUsageItem[];
  count: number;
}

export interface SkillReuploadParams {
  skillUid: string;
  files: File[];
  expectedUpdatedAt: string;
}

export interface SkillFileUpdateParams {
  skillUid: string;
  path: string;
  body: {
    content: string;
    expected_updated_at: string;
  };
}

export interface SkillFileUpdateResult {
  file_path: string;
  size: number;
  updated_at: string | null;
  new_content_preview: string;
}
