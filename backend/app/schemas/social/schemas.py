from __future__ import annotations

from pydantic import BaseModel, Field


class FavoriteToggleResponse(BaseModel):
    """收藏 / 取消收藏 API 回應。"""

    favorited: bool = Field(
        ..., description="當前使用者是否已收藏此資源（idempotent 動作後的最終狀態）"
    )
    favorite_count: int = Field(
        ..., description="該資源最新的收藏總數（denormalized）"
    )


class ResourceSnapshot(BaseModel):
    """我的收藏列表中嵌入的資源摘要。若資源已被刪除則整個欄位為 null。"""

    uid: str = Field(..., description="資源 uid（agent_uid / skill_uid / script_uid）")
    name: str = Field(..., description="資源名稱")
    description: str | None = Field(None, description="資源描述")
    owner_user_uid: str = Field(..., description="資源擁有者 user_uid")
    owner_username: str | None = Field(None, description="資源擁有者使用者名稱")
    visibility: str | None = Field(
        None, description="資源可見性（public / private），v1.2 script 尚未導入時可為 null"
    )
    favorite_count: int = Field(..., description="該資源最新的收藏總數")
    download_count: int = Field(..., description="該資源最新的下載總數")
    created_at: str | None = Field(None, description="資源建立時間（ISO8601，UTC+8）")
    updated_at: str | None = Field(None, description="資源最後更新時間（ISO8601，UTC+8）")


class MyFavoriteItem(BaseModel):
    """我的收藏列表單筆項目。"""

    user_favorite_uid: str = Field(..., description="收藏紀錄 uid")
    resource_type: str = Field(..., description="資源類型：agent / skill / script")
    resource_uid: str = Field(..., description="資源 uid")
    resource: ResourceSnapshot | None = Field(
        None,
        description="資源快照；若資源已被刪除 / 遺失則為 null，請搭配 tombstone_reason 判讀",
    )
    tombstone_reason: str | None = Field(
        None,
        description="資源為 null 時的原因標記，目前僅有 `resource_removed`",
    )
    created_at: str | None = Field(
        None, description="收藏紀錄建立時間（ISO8601，UTC+8）"
    )


class MyFavoritesResponse(BaseModel):
    """我的收藏列表。"""

    items: list[MyFavoriteItem] = Field(..., description="收藏項目列表")
    page: int = Field(..., description="當前頁碼（從 1 開始）")
    size: int = Field(..., description="每頁筆數")
    total: int = Field(..., description="未軟刪的收藏總筆數")
