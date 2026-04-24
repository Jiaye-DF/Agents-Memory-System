export interface Script {
  script_uid: string;
  owner_user_uid: string;
  owner_username: string | null;
  name: string;
  description: string | null;
  file_name: string;
  file_size: number;
  is_active: boolean;
  favorite_count: number;
  download_count: number;
  is_favorited: boolean;
  created_at: string;
  updated_at: string;
}

export interface ScriptUpdateRequest {
  name?: string;
  description?: string | null;
}

export interface ScriptCreateParams {
  name: string;
  description?: string;
  files: File[];
  /** 與 files 一一對應的相對路徑；通常取自 `File.webkitRelativePath || file.name` */
  relativePaths: string[];
}
