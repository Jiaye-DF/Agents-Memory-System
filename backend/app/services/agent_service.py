from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import ensure_modifiable, ensure_owner, ensure_readable
from app.core.datetime import to_taipei_iso
from app.core.exceptions import AppError
from app.core.pagination import paginate, paginate_ordered
from app.models.agent import Agent
from app.repositories import (
    agent_language_repository,
    agent_repository,
    user_favorite_repository,
)
from app.schemas.agents.schemas import AgentCreateRequest, AgentUpdateRequest
from app.schemas.common import VisibilityRequest
from app.services import download_service, system_setting_service

DEFAULT_MAX_SKILLS = 10
NOT_FOUND_DETAIL = "找不到指定的 Agent"


def _agent_to_dict(
    agent: Agent, skills: list[dict], is_favorited: bool = False
) -> dict:
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
        "model": agent.model,
        "temperature": agent.temperature,
        "max_tokens": agent.max_tokens,
        "greeting": agent.greeting,
        "response_format": agent.response_format,
        "response_format_example": agent.response_format_example,
        "visibility": agent.visibility,
        "is_active": agent.is_active,
        "skill_uids": [s["skill_uid"] for s in skills],
        "skills": skills,
        "favorite_count": agent.favorite_count,
        "download_count": agent.download_count,
        "is_favorited": is_favorited,
        "created_at": to_taipei_iso(agent.created_at),
        "updated_at": to_taipei_iso(agent.updated_at),
    }


async def _validate_language(language: str | None, db: AsyncSession) -> None:
    if language is None or language == "":
        return
    lang = await agent_language_repository.get_active_by_code(language, db)
    if lang is None:
        raise AppError(
            detail=f"指定的語言不存在或已停用：{language}",
            response_code=400,
            status_code=400,
        )


async def _validate_skill_count(
    skill_uids: list[str] | None, db: AsyncSession
) -> None:
    if not skill_uids:
        return
    max_skills = await system_setting_service.get_int(
        "agent.max_skills", DEFAULT_MAX_SKILLS, db
    )
    if len(skill_uids) > max_skills:
        raise AppError(
            detail=f"關聯的 Skills 數量超過上限（目前上限為 {max_skills}）",
            response_code=400,
            status_code=400,
        )


async def create_agent(
    user_uid: str, data: AgentCreateRequest, db: AsyncSession
) -> dict:
    await _validate_language(data.language, db)
    await _validate_skill_count(data.skill_uids, db)

    agent = await agent_repository.create(
        {
            "owner_uid": user_uid,
            "name": data.name,
            "description": data.description,
            "language": data.language,
            "style": data.style,
            "identity": data.identity,
            "role_prompt": data.role_prompt,
            "model": data.model,
            "temperature": data.temperature,
            "max_tokens": data.max_tokens,
            "greeting": data.greeting,
            "response_format": data.response_format,
            "response_format_example": data.response_format_example,
            "visibility": data.visibility,
        },
        db,
    )

    if data.skill_uids:
        await agent_repository.set_skill_uids(
            str(agent.agent_uid), data.skill_uids, db
        )

    skills = await agent_repository.get_skills_summary(
        str(agent.agent_uid), db
    )
    return _agent_to_dict(agent, skills, is_favorited=False)


async def get_agent(
    agent_uid: str, user_uid: str, role: str, db: AsyncSession
) -> dict:
    agent = await agent_repository.get_by_uid(agent_uid, db)
    ensure_readable(agent, user_uid, role, NOT_FOUND_DETAIL)
    assert agent is not None

    skills = await agent_repository.get_skills_summary(agent_uid, db)
    favorited = await user_favorite_repository.is_favorited_bulk(
        user_uid, "agent", [agent_uid], db
    )
    return _agent_to_dict(agent, skills, is_favorited=agent_uid in favorited)


async def list_agents(
    user_uid: str,
    cursor: str | None,
    limit: int,
    db: AsyncSession,
    order_by: str | None = None,
    order: str = "desc",
) -> dict:
    base_stmt = agent_repository.stmt_visible_to_user(user_uid)

    if order_by is not None:
        try:
            order_col = agent_repository.get_order_column(order_by)
        except ValueError as exc:
            raise AppError(
                detail=str(exc), response_code=400, status_code=400
            ) from exc
        page = await paginate_ordered(
            db,
            base_stmt,
            order_col,
            order_desc=(order.lower() != "asc"),
            cursor=cursor,
            limit=limit,
        )
    else:
        page = await paginate(db, base_stmt, cursor, limit)

    item_uids = [str(a.agent_uid) for a in page.items]
    skills_map = await agent_repository.get_skills_summary_map(item_uids, db)
    favorited_set = await user_favorite_repository.is_favorited_bulk(
        user_uid, "agent", item_uids, db
    )

    return {
        "items": [
            _agent_to_dict(
                a,
                skills_map.get(str(a.agent_uid), []),
                is_favorited=str(a.agent_uid) in favorited_set,
            )
            for a in page.items
        ],
        "next_cursor": page.next_cursor,
        "has_next": page.has_next,
    }


async def update_agent(
    agent_uid: str,
    user_uid: str,
    role: str,
    data: AgentUpdateRequest,
    db: AsyncSession,
) -> dict:
    agent = await agent_repository.get_by_uid(agent_uid, db)
    ensure_modifiable(agent, user_uid, role, NOT_FOUND_DETAIL)
    assert agent is not None

    if data.language is not None:
        await _validate_language(data.language, db)
    if data.skill_uids is not None:
        await _validate_skill_count(data.skill_uids, db)

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
    if data.model is not None:
        update_data["model"] = data.model
    if data.temperature is not None:
        update_data["temperature"] = data.temperature
    if data.max_tokens is not None:
        update_data["max_tokens"] = data.max_tokens
    if data.greeting is not None:
        update_data["greeting"] = data.greeting
    if data.response_format is not None:
        update_data["response_format"] = data.response_format
    if data.response_format_example is not None:
        update_data["response_format_example"] = data.response_format_example

    if update_data:
        await agent_repository.update_obj(agent, update_data, db)

    if data.skill_uids is not None:
        await agent_repository.set_skill_uids(agent_uid, data.skill_uids, db)

    skills = await agent_repository.get_skills_summary(agent_uid, db)
    favorited = await user_favorite_repository.is_favorited_bulk(
        user_uid, "agent", [agent_uid], db
    )
    return _agent_to_dict(
        agent, skills, is_favorited=agent_uid in favorited
    )


async def delete_agent(
    agent_uid: str, user_uid: str, role: str, db: AsyncSession
) -> None:
    agent = await agent_repository.get_by_uid(agent_uid, db)
    ensure_owner(
        agent, user_uid, NOT_FOUND_DETAIL, "只有擁有者可以刪除此 Agent"
    )
    assert agent is not None

    await agent_repository.soft_delete(agent, db)


async def toggle_visibility(
    agent_uid: str,
    user_uid: str,
    data: VisibilityRequest,
    db: AsyncSession,
) -> dict:
    agent = await agent_repository.get_by_uid(agent_uid, db)
    ensure_owner(
        agent, user_uid, NOT_FOUND_DETAIL, "只有擁有者可以切換可見性"
    )
    assert agent is not None

    await agent_repository.update_obj(agent, {"visibility": data.visibility}, db)
    skills = await agent_repository.get_skills_summary(agent_uid, db)
    favorited = await user_favorite_repository.is_favorited_bulk(
        user_uid, "agent", [agent_uid], db
    )
    return _agent_to_dict(
        agent, skills, is_favorited=agent_uid in favorited
    )


async def download_agent(
    agent_uid: str, user_uid: str, role: str, db: AsyncSession
) -> str:
    agent = await agent_repository.get_by_uid(agent_uid, db)
    ensure_readable(agent, user_uid, role, NOT_FOUND_DETAIL)
    assert agent is not None

    lines = [
        f"# {agent.name}",
        "",
    ]

    if agent.description:
        lines.append("## 描述")
        lines.append("")
        lines.append(agent.description)
        lines.append("")

    if agent.identity:
        lines.append("## 身分")
        lines.append("")
        lines.append(agent.identity)
        lines.append("")

    if agent.language:
        lines.append("## 語言偏好")
        lines.append("")
        lines.append(agent.language)
        lines.append("")

    if agent.style:
        lines.append("## 風格")
        lines.append("")
        lines.append(agent.style)
        lines.append("")

    if agent.role_prompt:
        lines.append("## 角色設定")
        lines.append("")
        lines.append(agent.role_prompt)
        lines.append("")

    skills = await agent_repository.get_skills_summary(agent_uid, db)
    if skills:
        lines.append("## 關聯 Skills")
        lines.append("")
        for s in skills:
            lines.append(f"- {s['name']}")
        lines.append("")

    # Response 即將回傳前才 +1（同 user 24h Redis dedup）
    # AGENTS.md 內含關聯 Skills 視為一併下載，連動 Skills 各自計數（dedup 獨立）
    await download_service.try_increment_download(
        "agent", agent_uid, user_uid, db
    )
    for s in skills:
        await download_service.try_increment_download(
            "skill", s["skill_uid"], user_uid, db
        )

    return "\n".join(lines)
