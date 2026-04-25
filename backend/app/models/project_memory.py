import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import String, Text, Uuid
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.models.chat_memory import MemoryBase


class ProjectMemory(MemoryBase):
    """Project 層記憶：同 project 下所有 session 的二次聚合（v1.3.5）。

    生命週期硬規範（propose §3-3）：
    - 對 chat_session 不建 FK cascade — session 刪除不連動
    - 對 chat_project 由 service 層 hard delete 連動
    - 對 user 由 service 層 hard delete 連動（user 停用 / 刪除）
    """

    __tablename__ = "project_memory"

    project_memory_uid: Mapped[uuid.UUID] = mapped_column(
        Uuid, default=uuid.uuid4, nullable=False
    )
    # 跨 base 不掛 ForeignKey 避免 NoReferencedTableError；FK 由 V44 migration 保證
    chat_project_uid: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    source_session_uids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(Uuid), nullable=False
    )
    source_chat_message_uids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(Uuid), nullable=False, default=list
    )
    keywords: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, default=list
    )
    entities: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, default=list
    )
    topic: Mapped[str | None] = mapped_column(String(200), nullable=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(1536), nullable=False)
