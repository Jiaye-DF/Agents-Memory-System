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
    # v1.3.5：跨層聚合 worker queue / DLQ 長度
    project_memory_queue_len: int | None = None
    project_memory_dlq_len: int | None = None
    user_memory_queue_len: int | None = None
    user_memory_dlq_len: int | None = None


class TokenData(BaseModel):
    access_token: str
    token_type: str = "bearer"
