import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, Numeric, String, Text, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class MessageBase(DeclarativeBase):
    """chat_message 專用 base：無 updated_at / is_deleted。"""

    pid: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ChatMessage(MessageBase):
    __tablename__ = "chat_message"

    chat_message_uid: Mapped[uuid.UUID] = mapped_column(
        Uuid, default=uuid.uuid4, nullable=False
    )
    # 不使用 Python 層 FK：ChatMessage 與 ChatSession 屬不同 DeclarativeBase
    # （為了排除 updated_at / is_deleted），FK 仍由 DB migration 保證
    chat_session_uid: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_in: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_out: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 6), nullable=True
    )
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
