"""三層記憶（v1.3.5）對外 schema：

- ProjectMemoryItem / UserMemoryItem：admin debug 與管理頁列表用
- FusedMemoryItem：RRF 融合後的單筆結構（含 scope 標籤）
- ThreeLayerRagResult：admin debug `GET /admin/debug/memory/retrieve` 回應
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.chat.memory_schemas import ChatMemoryResponse


class ProjectMemoryItem(BaseModel):
    """Project 層記憶（不含 embedding）。"""

    project_memory_uid: str
    chat_project_uid: str
    source_session_uids: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    topic: str | None = None
    created_at: str


class UserMemoryItem(BaseModel):
    """User 層記憶（不含 embedding）。"""

    user_memory_uid: str
    owner_user_uid: str
    source_session_uids: list[str] = Field(default_factory=list)
    source_project_uids: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    topic: str | None = None
    created_at: str


class FusedMemoryItem(BaseModel):
    """RRF 融合後單筆記憶（給 admin debug 用，亦給 service 層內部結果）。"""

    scope: Literal["session", "project", "user"]
    memory_uid: str
    topic: str | None = None
    keywords: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    rrf_score: float = Field(..., description="RRF 分數（Σ 1/(k + rank)）")
    source_rank: int = Field(..., description="該筆在原層內的排名（從 1 起算）")


class ProjectMemoryListData(BaseModel):
    items: list[ProjectMemoryItem]


class UserMemoryListData(BaseModel):
    items: list[UserMemoryItem]


class ThreeLayerRagResult(BaseModel):
    """`GET /admin/debug/memory/retrieve` 回應；含未融合三層 + 融合後。"""

    session: list[ChatMemoryResponse] = Field(default_factory=list)
    project: list[ProjectMemoryItem] = Field(default_factory=list)
    user: list[UserMemoryItem] = Field(default_factory=list)
    fused: list[FusedMemoryItem] = Field(default_factory=list)


class AggregateTriggerResult(BaseModel):
    """`POST /admin/memory/aggregate/{scope}/{uid}` 回應。"""

    queued: bool
    queue_depth: int
