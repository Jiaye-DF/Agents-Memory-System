import uuid

from sqlalchemy import Float, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AgentTemplate(Base):
    __tablename__ = "agent_template"

    agent_template_uid: Mapped[uuid.UUID] = mapped_column(
        Uuid, default=uuid.uuid4, nullable=False
    )
    template_key: Mapped[str] = mapped_column(String(50), nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    identity: Mapped[str | None] = mapped_column(String(200), nullable=True)
    language: Mapped[str | None] = mapped_column(String(20), nullable=True)
    style: Mapped[str | None] = mapped_column(String(50), nullable=True)
    role_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    greeting: Mapped[str | None] = mapped_column(Text, nullable=True)
    temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_format: Mapped[str | None] = mapped_column(
        String(20), nullable=True, default="markdown"
    )
    response_format_example: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
