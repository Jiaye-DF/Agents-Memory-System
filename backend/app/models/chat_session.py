import uuid

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ChatSession(Base):
    __tablename__ = "chat_session"

    chat_session_uid: Mapped[uuid.UUID] = mapped_column(
        Uuid, default=uuid.uuid4, nullable=False
    )
    chat_project_uid: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("chat_project.chat_project_uid"), nullable=False
    )
    agent_uid: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("agent.agent_uid"), nullable=False
    )
    title: Mapped[str] = mapped_column(
        String(200), nullable=False, default="未命名對話"
    )
