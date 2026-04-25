"""Agentic Skill 工廠正式版 — Skill 候選 Model（v1.3.6）。

對應 V47 migration：
- pid / agentic_skill_suggestion_uid / 三層 scope（session / project / user）
- name / description / system_prompt + confidence + source_memory_uids
- signature 用於同 scope_uid 去重
- status：pending / approved / rejected / expired
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import Numeric, String, Text, Uuid
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AgenticSkillSuggestion(Base):
    """Skill 候選表（v1.3.6 取代 v1.1.7 Redis 暫存路徑，保留 30 天）。"""

    __tablename__ = "agentic_skill_suggestion"

    agentic_skill_suggestion_uid: Mapped[uuid.UUID] = mapped_column(
        Uuid, default=uuid.uuid4, nullable=False
    )
    # 不綁 FK：跨模組泛型 + 容忍 user 刪除（連動由 service layer 處理）
    owner_user_uid: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    scope: Mapped[str] = mapped_column(String(20), nullable=False)
    # 不綁 FK：scope 對應的資源刪除時改 status=expired，不硬刪 suggestion
    scope_uid: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(String(200), nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[Decimal] = mapped_column(
        Numeric(4, 3), nullable=False
    )
    source_memory_uids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(Uuid), nullable=False, default=list
    )
    signature: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )
    # 不綁 FK：approved 後若 skill 被使用者刪除，仍保留歷史紀錄
    created_skill_uid: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, nullable=True
    )
