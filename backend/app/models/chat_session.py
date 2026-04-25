import uuid

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ChatSession(Base):
    __tablename__ = "chat_session"

    chat_session_uid: Mapped[uuid.UUID] = mapped_column(
        Uuid, default=uuid.uuid4, nullable=False
    )
    chat_project_uid: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("chat_project.chat_project_uid"), nullable=True
    )
    owner_user_uid: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("user.user_uid"), nullable=False
    )
    # [DEPRECATED v1.3.3] 多 Agent 對話改用 session_agent 中介表；
    # 此欄位保留為 nullable 以容過渡期（向後相容舊查詢路徑）。
    agent_uid: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("agent.agent_uid"), nullable=True
    )
    title: Mapped[str] = mapped_column(
        String(200), nullable=False, default="未命名對話"
    )
