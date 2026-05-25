from __future__ import annotations

from pydantic import BaseModel, field_validator, model_validator


MAX_TAG_LEN = 50
MAX_TAGS_PER_ENTITY = 20


class TagSummary(BaseModel):
    """精簡 tag 表示，給 entity Response 內嵌使用。"""

    tag_uid: str
    name: str


class TagDetail(BaseModel):
    """完整 tag 表示，給 `/tags` 列表回傳。"""

    tag_uid: str
    name: str
    usage_count: int = 0
    created_at: str


class TagListResponse(BaseModel):
    items: list[TagDetail]


class TagCreateRequest(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Tag 名稱不可為空")
        if len(value) > MAX_TAG_LEN:
            raise ValueError(f"Tag 名稱不可超過 {MAX_TAG_LEN} 字元")
        return value


class TagRenameRequest(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Tag 名稱不可為空")
        if len(value) > MAX_TAG_LEN:
            raise ValueError(f"Tag 名稱不可超過 {MAX_TAG_LEN} 字元")
        return value


class TagCreateResponse(BaseModel):
    tag: TagDetail
    created: bool


class EntityTagsRequest(BaseModel):
    """整批替換 entity 的 tag 綁定。

    `names` 與 `tag_uids` 二選一互斥：
    - `names` 走 find-or-create（不存在自動新建）
    - `tag_uids` 走既有 tag 直接綁定（不存在 / 非 owner → 400）
    """

    names: list[str] | None = None
    tag_uids: list[str] | None = None

    @model_validator(mode="after")
    def validate_one_of(self) -> "EntityTagsRequest":
        names_set = self.names is not None
        uids_set = self.tag_uids is not None
        if names_set == uids_set:
            raise ValueError("須提供 names 或 tag_uids 其中一個（互斥）")
        return self

    @field_validator("names")
    @classmethod
    def validate_names(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        if len(value) > MAX_TAGS_PER_ENTITY:
            raise ValueError(
                f"單一資源最多 {MAX_TAGS_PER_ENTITY} 個 tag"
            )
        cleaned: list[str] = []
        seen: set[str] = set()
        for raw in value:
            name = raw.strip()
            if not name:
                continue
            if len(name) > MAX_TAG_LEN:
                raise ValueError(f"Tag 名稱不可超過 {MAX_TAG_LEN} 字元：{name}")
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(name)
        return cleaned

    @field_validator("tag_uids")
    @classmethod
    def validate_tag_uids(
        cls, value: list[str] | None
    ) -> list[str] | None:
        if value is None:
            return value
        if len(value) > MAX_TAGS_PER_ENTITY:
            raise ValueError(
                f"單一資源最多 {MAX_TAGS_PER_ENTITY} 個 tag"
            )
        return list(dict.fromkeys(value))
