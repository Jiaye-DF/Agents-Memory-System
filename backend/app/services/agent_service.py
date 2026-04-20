from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.pagination import decode_cursor, encode_cursor
from app.models.agent import Agent
from app.repositories import agent_repository
from app.schemas.agents.schemas import (
    AgentCreateRequest,
    AgentUpdateRequest,
    VisibilityRequest,
)


def _agent_to_dict(agent: Agent, skill_uids: list[str]) -> dict:
    return {
        "agent_uid": str(agent.agent_uid),
        "owner_uid": str(agent.owner_uid),
        "owner_username": agent.owner.username if agent.owner else None,
        "name": agent.name,
        "description": agent.description,
        "language": agent.language,
        "style": agent.style,
        "identity": agent.identity,
        "role_prompt": agent.role_prompt,
        "visibility": agent.visibility,
        "is_active": agent.is_active,
        "skill_uids": skill_uids,
        "created_at": agent.created_at.isoformat(),
        "updated_at": agent.updated_at.isoformat(),
    }


async def create_agent(
    user_uid: str, data: AgentCreateRequest, db: AsyncSession
) -> dict:
    agent = await agent_repository.create(
        {
            "owner_uid": user_uid,
            "name": data.name,
            "description": data.description,
            "language": data.language,
            "style": data.style,
            "identity": data.identity,
            "role_prompt": data.role_prompt,
            "visibility": data.visibility,
        },
        db,
    )

    skill_uids: list[str] = []
    if data.skill_uids:
        await agent_repository.set_skill_uids(
            str(agent.agent_uid), data.skill_uids, db
        )
        skill_uids = data.skill_uids

    return _agent_to_dict(agent, skill_uids)


async def get_agent(
    agent_uid: str, user_uid: str, role: str, db: AsyncSession
) -> dict:
    agent = await agent_repository.get_by_uid(agent_uid, db)
    if agent is None:
        raise AppError(
            detail="找不到指定的 Agent", response_code=404, status_code=404
        )

    if role != "admin":
        if str(agent.owner_uid) != user_uid and agent.visibility != "public":
            raise AppError(
                detail="找不到指定的 Agent", response_code=404, status_code=404
            )

    skill_uids = await agent_repository.get_skill_uids(agent_uid, db)
    return _agent_to_dict(agent, skill_uids)


async def list_agents(
    user_uid: str, cursor: str | None, limit: int, db: AsyncSession
) -> dict:
    decoded_cursor: int | None = None
    if cursor is not None:
        decoded_cursor = decode_cursor(cursor)

    rows = await agent_repository.list_visible_to_user(
        user_uid, decoded_cursor, limit, db
    )

    has_next = len(rows) > limit
    items = rows[:limit]

    next_cursor: str | None = None
    if has_next and items:
        next_cursor = encode_cursor(items[-1].pid)

    agents_list = []
    for agent in items:
        skill_uids = await agent_repository.get_skill_uids(
            str(agent.agent_uid), db
        )
        agents_list.append(_agent_to_dict(agent, skill_uids))

    return {
        "items": agents_list,
        "next_cursor": next_cursor,
        "has_next": has_next,
    }


async def update_agent(
    agent_uid: str,
    user_uid: str,
    role: str,
    data: AgentUpdateRequest,
    db: AsyncSession,
) -> dict:
    agent = await agent_repository.get_by_uid(agent_uid, db)
    if agent is None:
        raise AppError(
            detail="找不到指定的 Agent", response_code=404, status_code=404
        )

    if role != "admin" and str(agent.owner_uid) != user_uid:
        raise AppError(detail="權限不足", response_code=403, status_code=403)

    update_data: dict = {}
    if data.name is not None:
        update_data["name"] = data.name
    if data.description is not None:
        update_data["description"] = data.description
    if data.language is not None:
        update_data["language"] = data.language
    if data.style is not None:
        update_data["style"] = data.style
    if data.identity is not None:
        update_data["identity"] = data.identity
    if data.role_prompt is not None:
        update_data["role_prompt"] = data.role_prompt

    if update_data:
        await agent_repository.update(agent, update_data, db)

    if data.skill_uids is not None:
        await agent_repository.set_skill_uids(agent_uid, data.skill_uids, db)

    skill_uids = await agent_repository.get_skill_uids(agent_uid, db)
    return _agent_to_dict(agent, skill_uids)


async def delete_agent(
    agent_uid: str, user_uid: str, role: str, db: AsyncSession
) -> None:
    agent = await agent_repository.get_by_uid(agent_uid, db)
    if agent is None:
        raise AppError(
            detail="找不到指定的 Agent", response_code=404, status_code=404
        )

    if str(agent.owner_uid) != user_uid:
        raise AppError(detail="只有擁有者可以刪除此 Agent", response_code=403, status_code=403)

    await agent_repository.soft_delete(agent, db)


async def toggle_visibility(
    agent_uid: str,
    user_uid: str,
    data: VisibilityRequest,
    db: AsyncSession,
) -> dict:
    agent = await agent_repository.get_by_uid(agent_uid, db)
    if agent is None:
        raise AppError(
            detail="找不到指定的 Agent", response_code=404, status_code=404
        )

    if str(agent.owner_uid) != user_uid:
        raise AppError(
            detail="只有擁有者可以切換可見性", response_code=403, status_code=403
        )

    await agent_repository.update(agent, {"visibility": data.visibility}, db)
    skill_uids = await agent_repository.get_skill_uids(agent_uid, db)
    return _agent_to_dict(agent, skill_uids)


async def download_agent(
    agent_uid: str, user_uid: str, role: str, db: AsyncSession
) -> str:
    agent = await agent_repository.get_by_uid(agent_uid, db)
    if agent is None:
        raise AppError(
            detail="找不到指定的 Agent", response_code=404, status_code=404
        )

    if role != "admin":
        if str(agent.owner_uid) != user_uid and agent.visibility != "public":
            raise AppError(
                detail="找不到指定的 Agent", response_code=404, status_code=404
            )

    lines = [
        f"# {agent.name}",
        "",
    ]

    if agent.description:
        lines.append(f"## 描述")
        lines.append("")
        lines.append(agent.description)
        lines.append("")

    if agent.identity:
        lines.append(f"## 身分")
        lines.append("")
        lines.append(agent.identity)
        lines.append("")

    if agent.language:
        lines.append(f"## 語言偏好")
        lines.append("")
        lines.append(agent.language)
        lines.append("")

    if agent.style:
        lines.append(f"## 風格")
        lines.append("")
        lines.append(agent.style)
        lines.append("")

    if agent.role_prompt:
        lines.append(f"## 角色設定")
        lines.append("")
        lines.append(agent.role_prompt)
        lines.append("")

    skill_uids = await agent_repository.get_skill_uids(agent_uid, db)
    if skill_uids:
        lines.append("## 關聯 Skills")
        lines.append("")
        for uid in skill_uids:
            lines.append(f"- {uid}")
        lines.append("")

    return "\n".join(lines)
