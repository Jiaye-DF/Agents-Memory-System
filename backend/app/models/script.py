import uuid

from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.user import User


class Script(Base):
    __tablename__ = "script"

    script_uid: Mapped[uuid.UUID] = mapped_column(
        Uuid, default=uuid.uuid4, nullable=False
    )
    owner_user_uid: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("user.user_uid"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    favorite_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    download_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    owner: Mapped[User] = relationship(lazy="joined")
