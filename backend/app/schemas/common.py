from pydantic import BaseModel, field_validator


class VisibilityRequest(BaseModel):
    visibility: str

    @field_validator("visibility")
    @classmethod
    def validate_visibility(cls, value: str) -> str:
        if value not in ("public", "private"):
            raise ValueError("可見性只能為 public 或 private")
        return value
