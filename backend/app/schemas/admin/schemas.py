from datetime import datetime

from pydantic import BaseModel


class UserResponse(BaseModel):
    user_uid: str
    username: str
    account: str
    role_name: str
    is_active: bool
    login_fail_count: int
    locked_until: datetime | None
    created_at: datetime


class UserUpdateRequest(BaseModel):
    role_uid: str | None = None
    unlock: bool | None = None


class RoleResponse(BaseModel):
    user_role_uid: str
    name: str
    description: str | None
