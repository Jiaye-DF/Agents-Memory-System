from datetime import datetime

from pydantic import BaseModel, field_validator


class AgentCreateRequest(BaseModel):
    name: str
    description: str | None = None
    language: str | None = None
    style: str | None = None
    identity: str | None = None
    role_prompt: str | None = None
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    greeting: str | None = None
    response_format: str | None = "markdown"
    response_format_example: str | None = None
    visibility: str = "private"
    skill_uids: list[str] | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if len(value.strip()) == 0:
            raise ValueError("名稱不可為空")
        if len(value) > 100:
            raise ValueError("名稱長度不可超過 100 字元")
        return value.strip()

    @field_validator("visibility")
    @classmethod
    def validate_visibility(cls, value: str) -> str:
        if value not in ("public", "private"):
            raise ValueError("可見性只能為 public 或 private")
        return value


class AgentUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    language: str | None = None
    style: str | None = None
    identity: str | None = None
    role_prompt: str | None = None
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    greeting: str | None = None
    response_format: str | None = None
    response_format_example: str | None = None
    skill_uids: list[str] | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is not None:
            if len(value.strip()) == 0:
                raise ValueError("名稱不可為空")
            if len(value) > 100:
                raise ValueError("名稱長度不可超過 100 字元")
            return value.strip()
        return value


class AgentResponse(BaseModel):
    agent_uid: str
    owner_uid: str
    owner_username: str | None
    name: str
    description: str | None
    language: str | None
    style: str | None
    identity: str | None
    role_prompt: str | None
    model: str | None
    temperature: float | None
    max_tokens: int | None
    greeting: str | None
    response_format: str | None
    response_format_example: str | None
    visibility: str
    is_active: bool
    skill_uids: list[str]
    created_at: datetime
    updated_at: datetime


