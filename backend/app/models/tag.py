import uuid

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Tag(Base):
    __tablename__ = "tag"

    tag_uid: Mapped[uuid.UUID] = mapped_column(
        Uuid, default=uuid.uuid4, nullable=False
    )
    owner_user_uid: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("user.user_uid"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)
