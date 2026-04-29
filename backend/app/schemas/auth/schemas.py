import re

from pydantic import BaseModel, field_validator, model_validator


def _validate_password(value: str) -> str:
    if len(value) < 8:
        raise ValueError("密碼長度須至少 8 個字元")
    if not re.search(r"[A-Z]", value):
        raise ValueError("密碼須包含至少一個大寫字母")
    if not re.search(r"[a-z]", value):
        raise ValueError("密碼須包含至少一個小寫字母")
    if not re.search(r"\d", value):
        raise ValueError("密碼須包含至少一個數字")
    return value


class RegisterRequest(BaseModel):
    username: str
    account: str
    password: str
    confirm_password: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        if len(value) < 2 or len(value) > 50:
            raise ValueError("使用者名稱須為 2-50 字元")
        return value

    @field_validator("account")
    @classmethod
    def validate_account(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("帳號長度須至少 8 個字元")
        if not re.search(r"[a-zA-Z]", value):
            raise ValueError("帳號須包含至少一個英文字母")
        if not re.search(r"\d", value):
            raise ValueError("帳號須包含至少一個數字")
        return value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return _validate_password(value)

    @model_validator(mode="after")
    def passwords_match(self) -> "RegisterRequest":
        if self.password != self.confirm_password:
            raise ValueError("密碼與確認密碼不一致")
        return self


class LoginRequest(BaseModel):
    account: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ResetPasswordRequest(BaseModel):
    account: str
    username: str
    new_password: str
    confirm_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        return _validate_password(value)

    @model_validator(mode="after")
    def passwords_match(self) -> "ResetPasswordRequest":
        if self.new_password != self.confirm_password:
            raise ValueError("密碼與確認密碼不一致")
        return self


class TokenPayload(BaseModel):
    user_uid: str
    role: str


class SsoExchangeRequest(BaseModel):
    code: str


class SsoBackChannelLogoutRequest(BaseModel):
    user_id: str
    timestamp: int
    signature: str
