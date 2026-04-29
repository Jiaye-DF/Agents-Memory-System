import re

from pydantic import BaseModel, field_validator

MODEL_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*\/[a-z0-9][a-z0-9.-]*$")


class LlmModelResponse(BaseModel):
    llm_model_uid: str
    provider: str
    vendor: str
    model_id: str
    display_name: str
    is_default: bool = False
    max_output_tokens: int | None = None


class LlmModelCreateRequest(BaseModel):
    model_id: str
    display_name: str
    is_default: bool | None = False
    max_output_tokens: int | None = None

    @field_validator("model_id")
    @classmethod
    def validate_model_id(cls, value: str) -> str:
        value = value.strip()
        if len(value) > 100 or not MODEL_ID_PATTERN.match(value):
            raise ValueError(
                "模型 ID 格式必須為 vendor/slug（如 anthropic/claude-sonnet-4）"
            )
        return value

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        value = value.strip()
        if not value or len(value) > 100:
            raise ValueError("顯示名稱為必填，且不可超過 100 字元")
        return value

    @field_validator("max_output_tokens")
    @classmethod
    def validate_max_output_tokens(cls, value: int | None) -> int | None:
        if value is not None and value <= 0:
            raise ValueError("max_output_tokens 必須為正整數")
        return value


class LlmModelUpdateRequest(BaseModel):
    display_name: str | None = None
    is_active: bool | None = None
    is_default: bool | None = None
    max_output_tokens: int | None = None

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str | None) -> str | None:
        if value is not None:
            value = value.strip()
            if not value or len(value) > 100:
                raise ValueError("顯示名稱為必填，且不可超過 100 字元")
        return value

    @field_validator("max_output_tokens")
    @classmethod
    def validate_max_output_tokens(cls, value: int | None) -> int | None:
        if value is not None and value <= 0:
            raise ValueError("max_output_tokens 必須為正整數")
        return value


class LlmModelAdminResponse(BaseModel):
    """Admin 視角的 LLM 模型完整欄位。"""

    llm_model_uid: str
    provider: str
    vendor: str
    model_id: str
    display_name: str
    is_active: bool
    is_deleted: bool
    is_default: bool
    max_output_tokens: int | None
    created_at: str
    updated_at: str


class OpenRouterModelInfo(BaseModel):
    """OpenRouter catalog 單一模型摘要。"""

    id: str
    name: str
    context_length: int | None = None


class OpenRouterCatalogData(BaseModel):
    items: list[OpenRouterModelInfo]
