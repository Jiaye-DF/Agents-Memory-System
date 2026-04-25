"""Agentic Skill 工廠正式版 — Pydantic schemas（v1.3.6）。

對外回傳的 `uid` 欄位皆為 `agentic_skill_suggestion_uid` 別名（對齊 Design-Base
10-frontend.md § 識別碼，不暴露 internal pid）。

注意：v1.1.7 PoC 的 `chat/skill_suggestion_schemas.py` 為 Redis 暫存路徑用，
本檔不動該檔；過渡期兩者並存。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# ---------- 列舉常數 ----------

SuggestionScope = Literal["session", "project", "user"]
SuggestionStatus = Literal["pending", "approved", "rejected", "expired"]


# ---------- 對外完整版（個人列表 / 詳情）----------


class AgenticSkillSuggestionItem(BaseModel):
    """單筆 Skill 候選對外格式（v1.3.6 取代 v1.1.7 SkillSuggestionItem）。"""

    model_config = ConfigDict(populate_by_name=True)

    uid: str = Field(..., description="suggestion 識別碼（對外公開）")
    scope: SuggestionScope
    scope_uid: str = Field(..., description="scope 對應資源 UID")
    name: str = Field(..., max_length=50)
    description: str = Field(..., max_length=200)
    system_prompt: str = Field(..., max_length=8000)
    confidence: float = Field(..., ge=0.0, le=1.0)
    source_memory_uids: list[str] = Field(default_factory=list)
    status: SuggestionStatus
    created_skill_uid: str | None = None
    created_at: str
    updated_at: str


class AgenticSkillSuggestionListResponse(BaseModel):
    """GET /api/v1/skill-suggestions 列表回應。"""

    items: list[AgenticSkillSuggestionItem]
    page: int
    size: int
    total: int


class AgenticSkillSuggestionDetailResponse(BaseModel):
    """GET /api/v1/skill-suggestions/{uid} 詳情回應（含來源記憶 inline 摘要）。"""

    suggestion: AgenticSkillSuggestionItem
    source_memories: list["SuggestionSourceMemoryBrief"] = Field(
        default_factory=list,
        description="來源記憶簡要（topic / keywords，不含 embedding 與 uid）",
    )


class SuggestionSourceMemoryBrief(BaseModel):
    """來源記憶 inline 摘要（前端展開用，不顯示 memory uid）。"""

    scope: SuggestionScope
    topic: str | None = None
    keywords: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    created_at: str | None = None


class AgenticSkillSuggestionAcceptRequest(BaseModel):
    """POST /api/v1/skill-suggestions/{uid}/accept body。"""

    agent_uid: str | None = Field(
        default=None,
        description="若提供，accept 後自動將新建立的 Skill 掛載到該 Agent",
    )


class AgenticSkillSuggestionAcceptResponse(BaseModel):
    """accept 成功回應。"""

    skill_uid: str
    skill_name: str
    agent_uid: str | None = None
    mounted: bool = Field(
        ...,
        description="若帶入 agent_uid 並成功掛載 = true；純 accept = false",
    )


class AgenticSkillSuggestionRejectResponse(BaseModel):
    """reject 成功回應。"""

    uid: str
    status: SuggestionStatus


# ---------- Recommender 推薦清單（精簡欄位）----------


class RecommendSuggestionItem(BaseModel):
    """給 recommender API / SSE event 用的精簡 schema（不含 system_prompt 全文）。

    前端展開詳細內容時走 detail API。
    """

    uid: str
    scope: SuggestionScope
    name: str
    description: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    source_memory_count: int = 0


class RecommendSuggestionListResponse(BaseModel):
    """GET /api/v1/agents/{uid}/skill-suggestions 回應。"""

    items: list[RecommendSuggestionItem]


# ---------- forward refs ----------

AgenticSkillSuggestionDetailResponse.model_rebuild()
