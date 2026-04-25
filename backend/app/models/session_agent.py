import uuid

from sqlalchemy import String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SessionAgent(Base):
    """Session 與 Agent 的中介表（v1.3.3 多 Agent 對話）。

    取代 chat_session.agent_uid 單一 Agent 設計；同 session 可掛多個 agent，
    其中至多一筆 role='primary'（由 DB partial unique index 保證）。
    不使用 Python 層 FK：與 chat_message 既有 pattern 對齊，FK 由 V39 migration
    在 DB 端保證。
    """

    __tablename__ = "session_agent"

    session_agent_uid: Mapped[uuid.UUID] = mapped_column(
        Uuid, default=uuid.uuid4, nullable=False
    )
    chat_session_uid: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    agent_uid: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    # 'primary' / 'member'：DB CHECK constraint 保證合法值
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, default="member"
    )
