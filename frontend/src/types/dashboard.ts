export type RankingType = "agent" | "skill" | "script";

export type RankingTypeFilter = "all" | RankingType;

export type RankingOrderBy =
  | "download_count"
  | "favorite_count"
  | "created_at";

export interface RankingItemOwner {
  user_uid: string;
  display_name: string;
}

export interface RankingItem {
  type: RankingType;
  uid: string;
  name: string;
  description: string | null;
  favorite_count: number;
  download_count: number;
  is_favorited: boolean;
  owner: RankingItemOwner;
  created_at: string;
  updated_at: string;
}

export interface RankingResponse {
  items: RankingItem[];
}
