import uuid

from sqlalchemy import String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class UserFavorite(Base):
    __tablename__ = "user_favorite"

    user_favorite_uid: Mapped[uuid.UUID] = mapped_column(
        Uuid, default=uuid.uuid4, nullable=False
    )
    owner_user_uid: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    resource_type: Mapped[str] = mapped_column(String(20), nullable=False)
    resource_uid: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
