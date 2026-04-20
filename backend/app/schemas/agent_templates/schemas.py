import re

from pydantic import BaseModel, field_validator

KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,48}[a-z0-9]$")


class AgentTemplateResponse(BaseModel):
    agent_template_uid: str
    template_key: str
    label: str
    description: str | None
    name: str | None
    identity: str | None
    language: str | None
    style: str | None
    role_prompt: str | None
    greeting: str | None
    temperature: float | None
    max_tokens: int | None
    response_format: str | None
    response_format_example: str | None
    sort_order: int
    is_active: bool
    created_at: str
    updated_at: str


class AgentTemplateCreateRequest(BaseModel):
    template_key: str
    label: str
    description: str | None = None
    name: str | None = None
    identity: str | None = None
    language: str | None = None
    style: str | None = None
    role_prompt: str | None = None
    greeting: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    response_format: str | None = "markdown"
    response_format_example: str | None = None
    sort_order: int = 0

    @field_validator("template_key")
    @classmethod
    def validate_key(cls, value: str) -> str:
        value = value.strip()
        if not KEY_PATTERN.match(value):
            raise ValueError("範本識別碼僅允許英數小寫與連字號，且不可以連字號開頭或結尾")
        return value

    @field_validator("label")
    @classmethod
    def validate_label(cls, value: str) -> str:
        value = value.strip()
        if not value or len(value) > 100:
            raise ValueError("名稱為必填，且不可超過 100 字元")
        return value

    @field_validator("response_format")
    @classmethod
    def validate_response_format(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if value not in ("markdown", "plain_text", "json"):
            raise ValueError("回覆格式必須為 markdown / plain_text / json")
        return value

    @field_validator("temperature")
    @classmethod
    def validate_temperature(cls, value: float | None) -> float | None:
        if value is None:
            return value
        if value < 0 or value > 2:
            raise ValueError("溫度需介於 0 至 2 之間")
        return value


class AgentTemplateUpdateRequest(BaseModel):
    label: str | None = None
    description: str | None = None
    name: str | None = None
    identity: str | None = None
    language: str | None = None
    style: str | None = None
    role_prompt: str | None = None
    greeting: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    response_format: str | None = None
    response_format_example: str | None = None
    sort_order: int | None = None
    is_active: bool | None = None

    @field_validator("label")
    @classmethod
    def validate_label(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value or len(value) > 100:
            raise ValueError("名稱不可為空，且不可超過 100 字元")
        return value

    @field_validator("response_format")
    @classmethod
    def validate_response_format(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if value not in ("markdown", "plain_text", "json"):
            raise ValueError("回覆格式必須為 markdown / plain_text / json")
        return value

    @field_validator("temperature")
    @classmethod
    def validate_temperature(cls, value: float | None) -> float | None:
        if value is None:
            return value
        if value < 0 or value > 2:
            raise ValueError("溫度需介於 0 至 2 之間")
        return value
