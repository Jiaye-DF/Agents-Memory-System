export interface Skill {
  skill_uid: string;
  owner_uid: string;
  name: string;
  description: string;
  original_filename: string;
  file_size: number;
  visibility: "public" | "private";
  is_active: boolean;
  created_at: string;
  updated_at: string;
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

export interface SkillUploadParams {
  name: string;
  description: string;
  file: File;
}
