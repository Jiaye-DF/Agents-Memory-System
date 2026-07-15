import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.chat_memory import MemoryBase


class SkillEmbedding(MemoryBase):
    """Skill 多向量表：一個 Skill 對應 name / description / content 三條向量（v1.6.2）。

    - 不建 (skill_uid, source_type) 唯一約束——為 content chunking 預留；
      替換一致性由 service 層同 transaction delete + insert 保證
    - skill 軟刪時 rows 保留，檢索經 join skill.is_deleted = FALSE 自然過濾
    """

    __tablename__ = "skill_embedding"

    skill_embedding_uid: Mapped[uuid.UUID] = mapped_column(
        Uuid, default=uuid.uuid4, nullable=False
    )
    # 跨 base 不掛 ForeignKey 避免 NoReferencedTableError；FK 由 V59 migration 保證
    skill_uid: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(1536), nullable=False)
