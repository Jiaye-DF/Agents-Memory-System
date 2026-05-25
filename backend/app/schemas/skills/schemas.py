from __future__ import annotations

from pydantic import BaseModel, field_validator

from app.schemas.tags.schemas import TagSummary


class SkillCreateRequest(BaseModel):
    name: str
    description: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value or len(value) > 100:
            raise ValueError("名稱為必填，且不可超過 100 字元")
        return value

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("描述為必填")
        return value


class SkillUpdateRequest(BaseModel):
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
        if value is not None:
            value = value.strip()
            if not value:
                raise ValueError("描述不可為空")
        return value


class SkillResponse(BaseModel):
    skill_uid: str
    owner_user_uid: str
    owner_username: str | None
    name: str
    description: str
    original_filename: str
    file_size: int
    visibility: str
    is_active: bool
    favorite_count: int = 0
    download_count: int = 0
    is_favorited: bool = False
    tags: list[TagSummary] = []
    created_at: str
    updated_at: str


class FileTreeNode(BaseModel):
    name: str
    type: str
    children: list[FileTreeNode] | None = None


class FileContentResponse(BaseModel):
    path: str
    size: int
    encoding: str
    content: str
    too_large: bool


class SkillUsageItem(BaseModel):
    agent_uid: str
    agent_name: str
    owner_username: str | None
    visibility: str


class SkillUsageResponse(BaseModel):
    items: list[SkillUsageItem]
    count: int


# 單檔大小上限：500 KB（UTF-8 字串位元組數上限，以寬鬆估算 700_000 字元攔截）
_MAX_CONTENT_BYTES = 500 * 1024


class SkillFileUpdateRequest(BaseModel):
    content: str
    expected_updated_at: str

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        if len(value.encode("utf-8")) > _MAX_CONTENT_BYTES:
            raise ValueError("檔案內容超過 500 KB 上限")
        return value

    @field_validator("expected_updated_at")
    @classmethod
    def validate_expected_updated_at(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("expected_updated_at 為必填")
        return value
