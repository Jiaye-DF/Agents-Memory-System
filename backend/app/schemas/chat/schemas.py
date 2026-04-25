from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, field_validator, model_validator

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
    # [DEPRECATED v1.3.3] 單 Agent 路徑；新建議使用 agent_uids
    agent_uid: str | None = None
    # v1.3.3 多 Agent：第一個視為 primary，其餘為 member
    agent_uids: list[str] | None = None
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

    @field_validator("agent_uids")
    @classmethod
    def validate_agent_uids(
        cls, value: list[str] | None
    ) -> list[str] | None:
        if value is None:
            return None
        cleaned = [x for x in value if isinstance(x, str) and x.strip()]
        # 維持原順序、去重（dict 保序）
        deduped = list(dict.fromkeys(cleaned))
        return deduped or None

    @model_validator(mode="after")
    def _ensure_at_least_one_agent(self) -> "ChatSessionCreateRequest":
        if not self.agent_uid and not self.agent_uids:
            raise ValueError("agent_uid 或 agent_uids 至少擇一")
        return self


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


class SessionAgentItem(BaseModel):
    """session_agent 中介表單筆對外格式（v1.3.3）。"""

    session_agent_uid: str
    agent_uid: str
    agent_name: str | None
    agent_avatar_url: str | None = None
    role: Literal["primary", "member"]
    created_at: str


class ChatSessionResponse(BaseModel):
    chat_session_uid: str
    chat_project_uid: str | None
    # [DEPRECATED v1.3.3] 多 Agent 改看 agents；保留以容過渡期
    agent_uid: str | None
    agent_name: str | None
    title: str
    message_count: int
    last_message_at: str | None
    is_active: bool
    created_at: str
    updated_at: str
    # v1.3.3：session 的所有掛載 agents（含 primary / member）
    agents: list[SessionAgentItem] = []


class SessionAgentAddRequest(BaseModel):
    """加掛 Agent 至 session（v1.3.3）。"""

    agent_uid: str

    @field_validator("agent_uid")
    @classmethod
    def validate_agent_uid(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("agent_uid 為必填")
        return value


class SessionAgentsListData(BaseModel):
    """加掛 / 移除 / 提升 primary 後的回傳格式（v1.3.3）。"""

    agents: list[SessionAgentItem]


class AgentBrief(BaseModel):
    """訊息附帶的 Agent 簡要資訊（v1.3.3 多 Agent）。"""

    agent_uid: str
    name: str
    avatar_url: str | None = None


class SkillSuggestionPlaceholderData(BaseModel):
    """Skill 推薦 stub 回傳（v1.3.3 占位，v1.3.6 接真實邏輯）。"""

    items: list[dict] = []
    hint: str = "pending v1.3.6"


class ChatMessageCreateRequest(BaseModel):
    content: str
    attachment_uids: list[str] | None = None
    # v1.3.3：使用者於前端 @mention 解析後傳入；未指定時後端取 primary agent
    mentioned_agent_uid: str | None = None

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

    @field_validator("mentioned_agent_uid")
    @classmethod
    def validate_mentioned_agent_uid(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


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
    # v1.3.3：哪個 Agent 回的；user 訊息為 None
    responding_agent_uid: str | None = None
    responding_agent: AgentBrief | None = None
