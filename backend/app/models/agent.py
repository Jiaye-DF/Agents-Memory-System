import uuid

from sqlalchemy import Column, ForeignKey, String, Table, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.user import User


class Agent(Base):
    __tablename__ = "agent"

    agent_uid: Mapped[uuid.UUID] = mapped_column(
        Uuid, default=uuid.uuid4, nullable=False
    )
    owner_uid: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("user.user_uid"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str | None] = mapped_column(String(50), nullable=True)
    style: Mapped[str | None] = mapped_column(String(50), nullable=True)
    identity: Mapped[str | None] = mapped_column(String(200), nullable=True)
    role_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    visibility: Mapped[str] = mapped_column(
        String(10), nullable=False, default="private"
    )

    owner: Mapped[User] = relationship(lazy="joined")


agent_skill_table = Table(
    "agent_skill",
    Base.metadata,
    Column("agent_uid", Uuid, primary_key=True),
    Column("skill_uid", Uuid, primary_key=True),
)
