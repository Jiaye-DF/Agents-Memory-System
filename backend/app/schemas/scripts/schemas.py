from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, field_validator

from app.schemas.tags.schemas import TagSummary


class ScriptUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    visibility: Literal["public", "private"] | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is not None:
            value = value.strip()
            if not value or len(value) > 255:
                raise ValueError("名稱不可為空，且不可超過 255 字元")
        return value

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        if value is not None:
            value = value.strip()
            # description 允許為空字串時轉 None；不限制上限由 DB text 容納
            if value == "":
                return None
        return value


class ScriptResponse(BaseModel):
    script_uid: str
    owner_user_uid: str
    owner_username: str | None
    name: str
    description: str | None
    file_name: str
    file_size: int
    visibility: Literal["public", "private"]
    is_active: bool
    favorite_count: int = 0
    download_count: int = 0
    is_favorited: bool = False
    tags: list[TagSummary] = []
    created_at: str
    updated_at: str
