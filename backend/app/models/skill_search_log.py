"""AI 查詢稽核紀錄 model（v1.6.3）。

對應 V61__create_skill_search_log.sql。

設計重點（同 download_log / llm_call_log）：
- 寫入即不可變的稽核表，**不**繼承 ``Base``（無 is_active / is_deleted / updated_at）
- 對 user_uid **不**綁 FK；業務軟刪不連動稽核資料
- username 存查詢當下快照
- results 以 JSONB 精簡存 RAG 結果與相似度（UI 自 v1.6.3 起不顯示分數）
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class SkillSearchLogBase(DeclarativeBase):
    """skill_search_log 專用 base：無 updated_at / is_deleted / is_active。"""

    pid: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SkillSearchLog(SkillSearchLogBase):
    __tablename__ = "skill_search_log"

    user_uid: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    username: Mapped[str] = mapped_column(String(50), nullable=False)
    query: Mapped[str] = mapped_column(String(500), nullable=False)
    scope: Mapped[str] = mapped_column(String(10), nullable=False)
    hit_count: Mapped[int] = mapped_column(Integer, nullable=False)
    results: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
