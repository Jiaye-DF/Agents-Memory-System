from __future__ import annotations

from pydantic import BaseModel, field_validator


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


class VisibilityRequest(BaseModel):
    visibility: str

    @field_validator("visibility")
    @classmethod
    def validate_visibility(cls, value: str) -> str:
        if value not in ("public", "private"):
            raise ValueError("visibility 只能為 public 或 private")
        return value


class SkillResponse(BaseModel):
    skill_uid: str
    owner_uid: str
    name: str
    description: str
    original_filename: str
    file_size: int
    visibility: str
    is_active: bool
    created_at: str
    updated_at: str


class FileTreeNode(BaseModel):
    name: str
    type: str
    children: list[FileTreeNode] | None = None
