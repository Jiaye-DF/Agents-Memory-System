from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.response import success
from app.repositories import llm_model_repository
from app.schemas.auth.schemas import TokenPayload
from app.schemas.models.schemas import LlmModelResponse
from app.schemas.response import ApiResponse


class LlmModelListData(BaseModel):
    items: list[LlmModelResponse]


router = APIRouter(prefix="/models", tags=["models"])


@router.get("", response_model=ApiResponse[LlmModelListData])
async def list_models(
    _current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    models = await llm_model_repository.get_all_active(db)
    items = [
        LlmModelResponse(
            llm_model_uid=str(m.llm_model_uid),
            provider=m.provider,
            model_id=m.model_id,
            display_name=m.display_name,
            is_default=m.is_default,
            max_output_tokens=m.max_output_tokens,
        ).model_dump()
        for m in models
    ]
    return success(data={"items": items})
