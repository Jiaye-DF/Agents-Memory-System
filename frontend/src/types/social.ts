export type ResourceType = "agent" | "skill" | "script";

export type FilterScope = "mine" | "favorites";

export interface FavoriteToggleResponse {
  favorited: boolean;
  favorite_count: number;
}

export interface ResourceSnapshot {
  uid: string;
  name: string;
  description: string | null;
  owner_uid: string;
  owner_username: string | null;
  visibility: "public" | "private" | null;
  favorite_count: number;
  download_count: number;
  created_at: string | null;
  updated_at: string | null;
}

export interface MyFavoriteItem {
  user_favorite_uid: string;
  resource_type: ResourceType;
  resource_uid: string;
  resource: ResourceSnapshot | null;
  tombstone_reason: string | null;
  created_at: string | null;
}

export interface MyFavoritesResponse {
  items: MyFavoriteItem[];
  page: number;
  size: number;
  total: number;
}
