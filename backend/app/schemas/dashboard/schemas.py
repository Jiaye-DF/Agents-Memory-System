"""儀錶板排行榜 API Schema。

規格：docs/Tasks/v1.2/tasks-v1.2.4.md §1-2 / propose-v1.2.0.md §2-4

設計要點：
- 單一 endpoint 跨 Agent / Skill / Script 三類資源，回傳統一 shape
- 所有欄位**必填**不可省略；`description` 允許 null（資料模型本就可空）
- `owner` shape 固定為 `{user_uid, display_name}`（對應資源 owner 的 user.username）
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RankingItemOwner(BaseModel):
    """排行榜項目的擁有者資訊。"""

    user_uid: str = Field(..., description="擁有者 user_uid")
    display_name: str = Field(
        ..., description="擁有者顯示名稱（對應 user.username）"
    )


class RankingItem(BaseModel):
    """排行榜單筆項目。三類資源共用此 shape。"""

    type: Literal["agent", "skill", "script"] = Field(
        ..., description="資源類型"
    )
    uid: str = Field(
        ..., description="資源 uid（agent_uid / skill_uid / script_uid）"
    )
    name: str = Field(..., description="資源名稱")
    description: str | None = Field(
        ..., description="資源描述；Agent / Script 可為 null，Skill 必有值"
    )
    favorite_count: int = Field(..., description="被收藏次數（denormalized）")
    download_count: int = Field(
        ...,
        description=(
            "被下載次數（denormalized）；Agent 在 v1.2 內恆為 0，"
            "選 download_count 排序時自然排尾"
        ),
    )
    is_favorited: bool = Field(
        ..., description="當前使用者是否已收藏此項"
    )
    owner: RankingItemOwner = Field(..., description="資源擁有者資訊")
    created_at: str = Field(
        ..., description="建立時間（ISO8601，UTC+8）"
    )
    updated_at: str = Field(
        ..., description="最後更新時間（ISO8601，UTC+8）"
    )


class RankingResponse(BaseModel):
    """排行榜 API 回應包裝。"""

    items: list[RankingItem] = Field(
        ..., description="依 order_by 重排並截 limit 後的排行榜項目"
    )
