from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.response import success
from app.schemas.agents.schemas import (
    AgentCreateRequest,
    AgentResponse,
    AgentUpdateRequest,
)
from app.schemas.common import VisibilityRequest
from app.schemas.auth.schemas import TokenPayload
from app.schemas.response import ApiResponse, MessageData, PaginatedData
from app.services import agent_service

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("", response_model=ApiResponse[PaginatedData[AgentResponse]])
async def list_agents(
    current_user: TokenPayload = Depends(get_current_user),
    cursor: str | None = Query(None),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await agent_service.list_agents(
        current_user.user_uid, cursor, limit, db
    )
    return success(data=result)


@router.post("", response_model=ApiResponse[AgentResponse])
async def create_agent(
    data: AgentCreateRequest,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await agent_service.create_agent(
        current_user.user_uid, data, db
    )
    return success(data=result, response_code=201)


@router.get("/{agent_uid}", response_model=ApiResponse[AgentResponse])
async def get_agent(
    agent_uid: str,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await agent_service.get_agent(
        agent_uid, current_user.user_uid, current_user.role, db
    )
    return success(data=result)


@router.put("/{agent_uid}", response_model=ApiResponse[AgentResponse])
async def update_agent(
    agent_uid: str,
    data: AgentUpdateRequest,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await agent_service.update_agent(
        agent_uid, current_user.user_uid, current_user.role, data, db
    )
    return success(data=result)


@router.delete("/{agent_uid}", response_model=ApiResponse[MessageData])
async def delete_agent(
    agent_uid: str,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    await agent_service.delete_agent(
        agent_uid, current_user.user_uid, current_user.role, db
    )
    return success(data={"message": "Agent 已刪除"})


@router.patch(
    "/{agent_uid}/visibility",
    response_model=ApiResponse[AgentResponse],
)
async def toggle_visibility(
    agent_uid: str,
    data: VisibilityRequest,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await agent_service.toggle_visibility(
        agent_uid, current_user.user_uid, data, db
    )
    return success(data=result)


@router.get("/{agent_uid}/download")
async def download_agent(
    agent_uid: str,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    content = await agent_service.download_agent(
        agent_uid, current_user.user_uid, current_user.role, db
    )
    return Response(
        content=content,
        media_type="text/markdown",
        headers={"Content-Disposition": "attachment; filename=AGENTS.md"},
    )
