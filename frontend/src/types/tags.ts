export interface TagSummary {
  tag_uid: string;
  name: string;
}

export interface TagDetail {
  tag_uid: string;
  name: string;
  usage_count: number;
  created_at: string;
}

export interface TagListResponse {
  items: TagDetail[];
}

export interface TagCreateRequest {
  name: string;
}

export interface TagCreateResponse {
  tag: TagDetail;
  created: boolean;
}

export interface TagRenameRequest {
  name: string;
}

export interface EntityTagsRequest {
  names?: string[];
  tag_uids?: string[];
}

export type EntityType = "skill" | "script" | "agent";
