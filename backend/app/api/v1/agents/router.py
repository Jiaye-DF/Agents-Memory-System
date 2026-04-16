from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.response import success
from app.schemas.agents.schemas import (
    AgentCreateRequest,
    AgentUpdateRequest,
    VisibilityRequest,
)
from app.schemas.auth.schemas import TokenPayload
from app.services import agent_service

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("")
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


@router.post("")
async def create_agent(
    data: AgentCreateRequest,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await agent_service.create_agent(
        current_user.user_uid, data, db
    )
    return success(data=result, response_code=201)


@router.get("/{agent_uid}")
async def get_agent(
    agent_uid: str,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    result = await agent_service.get_agent(
        agent_uid, current_user.user_uid, current_user.role, db
    )
    return success(data=result)


@router.put("/{agent_uid}")
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


@router.delete("/{agent_uid}")
async def delete_agent(
    agent_uid: str,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    await agent_service.delete_agent(
        agent_uid, current_user.user_uid, current_user.role, db
    )
    return success(data={"message": "Agent 已刪除"})


@router.patch("/{agent_uid}/visibility")
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
