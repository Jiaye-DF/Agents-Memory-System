import re

from pydantic import BaseModel, field_validator

CODE_PATTERN = re.compile(r"^[a-zA-Z]{2,10}(-[a-zA-Z0-9]{2,10})?$")


class AgentLanguageResponse(BaseModel):
    agent_language_uid: str
    code: str
    name: str
    sort_order: int
    is_default: bool
    is_active: bool
    created_at: str
    updated_at: str


class AgentLanguageCreateRequest(BaseModel):
    code: str
    name: str
    sort_order: int = 0
    is_default: bool = False

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        value = value.strip()
        if not value or len(value) > 20:
            raise ValueError("語系碼為必填，且不可超過 20 字元")
        if not CODE_PATTERN.match(value):
            raise ValueError("語系碼格式必須為如 zh-TW、en、ja")
        return value

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value or len(value) > 50:
            raise ValueError("名稱為必填，且不可超過 50 字元")
        return value


class AgentLanguageUpdateRequest(BaseModel):
    name: str | None = None
    sort_order: int | None = None
    is_default: bool | None = None
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is not None:
            value = value.strip()
            if not value or len(value) > 50:
                raise ValueError("名稱不可為空，且不可超過 50 字元")
        return value
