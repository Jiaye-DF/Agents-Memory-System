from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SkillSuggestionItem(BaseModel):
    """單筆 Skill 候選（Redis 暫存，7 天 TTL）。"""

    idx: int = Field(..., ge=0)
    name: str = Field(..., max_length=50)
    description: str = Field(..., max_length=200)
    system_prompt: str = Field(..., max_length=8000)
    confidence: float = Field(..., ge=0.0, le=1.0)
    source_memory_uids: list[str] = Field(default_factory=list)
    status: Literal["pending", "approved", "rejected"] = "pending"
    created_skill_uid: str | None = None
    created_at: str | None = None


class SkillSuggestionListData(BaseModel):
    """GET /chat/sessions/{uid}/skill-suggestions 回傳。"""

    items: list[SkillSuggestionItem]


class SkillSuggestionApproveData(BaseModel):
    """POST /.../approve 回傳。"""

    skill_uid: str
    name: str
    description: str
