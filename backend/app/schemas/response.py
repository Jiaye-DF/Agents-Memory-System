from pydantic import BaseModel


class ApiResponse(BaseModel):
    success: bool
    data: dict | None = None
    detail: str | None = None
    response_code: int
