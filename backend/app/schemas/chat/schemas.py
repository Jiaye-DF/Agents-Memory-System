from __future__ import annotations

from pydantic import BaseModel, field_validator

from app.schemas.chat.attachment_schemas import ChatAttachmentResponse


class ChatProjectCreateRequest(BaseModel):
    name: str
    description: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value or len(value) > 100:
            raise ValueError("名稱為必填，且不可超過 100 字元")
        return value

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class ChatProjectUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is not None:
            value = value.strip()
            if not value or len(value) > 100:
                raise ValueError("名稱不可為空，且不可超過 100 字元")
        return value

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip()


class ChatProjectResponse(BaseModel):
    chat_project_uid: str
    owner_user_uid: str
    name: str
    description: str | None
    session_count: int
    is_active: bool
    created_at: str
    updated_at: str


class ChatSessionCreateRequest(BaseModel):
    chat_project_uid: str | None = None
    agent_uid: str
    title: str | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            return None
        if len(value) > 200:
            raise ValueError("標題不可超過 200 字元")
        return value


class ChatSessionUpdateRequest(BaseModel):
    title: str | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("標題不可為空")
        if len(value) > 200:
            raise ValueError("標題不可超過 200 字元")
        return value


class ChatSessionMoveRequest(BaseModel):
    """移動 session 至某個 project；傳 None 代表移出成為游離 session。"""

    chat_project_uid: str | None = None


class ChatSessionResponse(BaseModel):
    chat_session_uid: str
    chat_project_uid: str | None
    agent_uid: str
    agent_name: str | None
    title: str
    message_count: int
    last_message_at: str | None
    is_active: bool
    created_at: str
    updated_at: str


class ChatMessageCreateRequest(BaseModel):
    content: str
    attachment_uids: list[str] | None = None

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("內容為必填")
        if len(value) > 10000:
            raise ValueError("內容不可超過 10000 字元")
        return value

    @field_validator("attachment_uids")
    @classmethod
    def validate_attachment_uids(
        cls, value: list[str] | None
    ) -> list[str] | None:
        if value is None:
            return None
        cleaned = [x for x in value if isinstance(x, str) and x.strip()]
        return cleaned or None


class ChatMessageResponse(BaseModel):
    chat_message_uid: str
    chat_session_uid: str
    role: str
    content: str
    token_in: int | None
    token_out: int | None
    cost_usd: float | None
    model: str | None
    finish_reason: str | None = None
    created_at: str
    # 遵循 20-backend.md § 關聯資源回應：同時回 uid 陣列與 {uid, name, ...} 物件陣列
    attachment_uids: list[str] | None = None
    attachments: list[ChatAttachmentResponse] | None = None
