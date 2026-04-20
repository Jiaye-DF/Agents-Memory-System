from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.response import success
from app.schemas.agent_templates.schemas import AgentTemplateResponse
from app.schemas.auth.schemas import TokenPayload
from app.schemas.response import ApiResponse
from app.services import agent_template_service


class AgentTemplateListData(BaseModel):
    items: list[AgentTemplateResponse]


router = APIRouter(prefix="/agent-templates", tags=["agent-templates"])


@router.get("", response_model=ApiResponse[AgentTemplateListData])
async def list_agent_templates(
    _current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await agent_template_service.list_templates(db)
    return success(data=result)
