from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    success: bool
    data: T | None = None
    detail: str | None = None
    response_code: int


class PaginatedData(BaseModel, Generic[T]):
    items: list[T]
    next_cursor: str | None = None
    has_next: bool = False


class MessageData(BaseModel):
    message: str


class HealthData(BaseModel):
    database: str
    redis: str
    # v1.3.1：記憶 pipeline queue / DLQ 長度（Redis 不通時為 None）
    memory_queue_len: int | None = None
    memory_dlq_len: int | None = None


class TokenData(BaseModel):
    access_token: str
    token_type: str = "bearer"
