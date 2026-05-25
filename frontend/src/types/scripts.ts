import type { TagSummary } from "./tags";

export interface Script {
  script_uid: string;
  owner_user_uid: string;
  owner_username: string | null;
  name: string;
  description: string | null;
  file_name: string;
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

export interface ScriptUpdateRequest {
  name?: string;
  description?: string | null;
  visibility?: "public" | "private";
}

export interface ScriptCreateParams {
  name: string;
  description?: string;
  visibility?: "public" | "private";
  files: File[];
  /** 與 files 一一對應的相對路徑；通常取自 `File.webkitRelativePath || file.name` */
  relativePaths: string[];
}
