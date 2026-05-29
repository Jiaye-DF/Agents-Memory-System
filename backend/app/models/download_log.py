"""下載人員紀錄 model（v1.5.x）。

對應 V55__create_download_log.sql。

設計重點（同 llm_call_log）：
- 寫入即不可變的稽核表，**不**繼承 ``Base``（無 is_active / is_deleted / updated_at）
- 使用獨立 DeclarativeBase
- 對 user_uid / resource_uid **不**綁 FK；業務軟刪不連動稽核資料
- username / resource_name 存下載當下快照，資源日後改名 / 軟刪仍可追溯
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, String, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class DownloadLogBase(DeclarativeBase):
    """download_log 專用 base：無 updated_at / is_deleted / is_active。"""

    pid: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DownloadLog(DownloadLogBase):
    __tablename__ = "download_log"

    user_uid: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    username: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(20), nullable=False)
    resource_uid: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    resource_name: Mapped[str] = mapped_column(String(255), nullable=False)
    counted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
