import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class MemoryBase(DeclarativeBase):
    """chat_memory 專用 base：無 updated_at / is_deleted / is_active。"""

    pid: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ChatMemory(MemoryBase):
    __tablename__ = "chat_memory"

    chat_memory_uid: Mapped[uuid.UUID] = mapped_column(
        Uuid, default=uuid.uuid4, nullable=False
    )
    chat_session_uid: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("chat_session.chat_session_uid"), nullable=False
    )
    source_chat_message_uids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(Uuid), nullable=False
    )
    keywords: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, default=list
    )
    entities: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, default=list
    )
    topic: Mapped[str | None] = mapped_column(String(200), nullable=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(1536), nullable=False)
