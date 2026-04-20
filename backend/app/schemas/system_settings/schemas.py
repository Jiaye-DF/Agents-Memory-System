from pydantic import BaseModel, RootModel, field_validator


class SystemSettingResponse(BaseModel):
    system_setting_uid: str
    key: str
    value: str
    value_type: str
    description: str | None
    is_public: bool
    is_active: bool
    created_at: str
    updated_at: str


class SystemSettingUpdateRequest(BaseModel):
    value: str | None = None
    description: str | None = None
    is_public: bool | None = None
    is_active: bool | None = None

    @field_validator("value")
    @classmethod
    def validate_value(cls, value: str | None) -> str | None:
        if value is not None and not isinstance(value, str):
            raise ValueError("value 必須為字串")
        return value


class SystemSettingPublicDict(RootModel[dict[str, str | int | bool]]):
    """public settings 字典（key -> 依 value_type 解析後的值）"""
