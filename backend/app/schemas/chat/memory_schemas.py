from __future__ import annotations

from pydantic import BaseModel, Field


class ChatMemoryResponse(BaseModel):
    """對外記憶回應（不含 embedding）。"""

    chat_memory_uid: str
    chat_session_uid: str
    source_chat_message_uids: list[str]
    keywords: list[str]
    entities: list[str]
    topic: str | None
    created_at: str


class ChatMemoryListData(BaseModel):
    items: list[ChatMemoryResponse]


class MemoryExtractResult(BaseModel):
    """小模型抽取記憶的固定 JSON 結構。"""

    keywords: list[str] = Field(default_factory=list, max_length=20)
    entities: list[str] = Field(default_factory=list, max_length=20)
    topic: str = Field(default="", max_length=200)
    is_actionable: bool = False
