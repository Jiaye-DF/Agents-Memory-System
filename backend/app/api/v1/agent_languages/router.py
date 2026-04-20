from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.response import success
from app.schemas.agent_languages.schemas import AgentLanguageResponse
from app.schemas.auth.schemas import TokenPayload
from app.schemas.response import ApiResponse
from app.services import agent_language_service


class AgentLanguageListData(BaseModel):
    items: list[AgentLanguageResponse]


router = APIRouter(prefix="/agent-languages", tags=["agent-languages"])


@router.get("", response_model=ApiResponse[AgentLanguageListData])
async def list_agent_languages(
    _current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await agent_language_service.list_languages(db)
    return success(data=result)
