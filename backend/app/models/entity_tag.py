import uuid

from sqlalchemy import String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class EntityTag(Base):
    __tablename__ = "entity_tag"

    entity_tag_uid: Mapped[uuid.UUID] = mapped_column(
        Uuid, default=uuid.uuid4, nullable=False
    )
    tag_uid: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)
    entity_uid: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
