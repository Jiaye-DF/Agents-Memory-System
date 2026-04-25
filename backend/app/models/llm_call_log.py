"""LLM 呼叫運營日誌 model（v1.3.0）。

對應 V38__create_llm_call_log.sql。

設計重點：
- 寫入即不可變的審計表，**不**繼承 ``Base``（無 is_active / is_deleted / updated_at）
- 使用獨立 DeclarativeBase（與 ChatMemory / ChatMessage 同模式）
- 對 session_uid / user_uid / agent_uid **不**綁 FK；業務軟刪不連動運營資料
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    DateTime,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class LlmCallLogBase(DeclarativeBase):
    """llm_call_log 專用 base：無 updated_at / is_deleted / is_active。"""

    pid: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class LlmCallLog(LlmCallLogBase):
    __tablename__ = "llm_call_log"

    # 業務識別欄（不綁 FK，可為 NULL；參見 docs/Arch §2-4）
    session_uid: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    user_uid: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    agent_uid: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)

    # 用途分類
    purpose: Mapped[str] = mapped_column(String(40), nullable=False)
    route: Mapped[str | None] = mapped_column(String(20), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # tokens
    input_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    output_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    cache_creation_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    cache_read_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    # cost / latency / 觀測
    actual_cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(10, 6), nullable=False, default=Decimal("0")
    )
    baseline_cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(10, 6), nullable=False, default=Decimal("0")
    )
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rag_hit_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rag_max_score: Mapped[Decimal | None] = mapped_column(
        Numeric(4, 3), nullable=True
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
