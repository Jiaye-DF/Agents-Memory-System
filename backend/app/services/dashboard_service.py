"""儀錶板排行榜服務層。

規格：docs/Tasks/v1.2/tasks-v1.2.4.md §1-3 / propose-v1.2.0.md §2-4

聚合策略：
- 三類（Agent / Skill / Script）各自撈 top N（N = limit）
- 合併後依 `order_by desc` 重排、截 limit
- 資料量小（單使用者量級），不需要快取或特殊索引以外的優化
- `is_favorited` 透過 v1.2.1 的 `user_favorite_repository.is_favorited_bulk` 一次折算
- `owner` 取各資源的 joined `user` relationship（已於 Model lazy=\"joined\" 預載）

權限：本版僅顯示「使用者擁有的資源」（propose §2-4），跨使用者公開排行留 v1.4。
"""

from __future__ import annotations

import uuid
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.datetime import to_taipei_iso
from app.models.agent import Agent
from app.models.script import Script
from app.models.skill import Skill
from app.repositories import user_favorite_repository
from app.services import system_setting_service

RankingTypeFilter = Literal["all", "agent", "skill", "script"]
RankingOrderBy = Literal["download_count", "favorite_count", "created_at"]
RankingOrder = Literal["asc", "desc"]

_DEFAULT_LIMIT = 10
_RANKING_SIZE_KEY = "dashboard.ranking_size"

# order_by → 三類資源上的 SQLAlchemy 欄位（皆為 denormalized / 真實欄位）
_AGENT_ORDER_COLS = {
    "download_count": Agent.download_count,
    "favorite_count": Agent.favorite_count,
    "created_at": Agent.created_at,
}
_SKILL_ORDER_COLS = {
    "download_count": Skill.download_count,
    "favorite_count": Skill.favorite_count,
    "created_at": Skill.created_at,
}
_SCRIPT_ORDER_COLS = {
    "download_count": Script.download_count,
    "favorite_count": Script.favorite_count,
    "created_at": Script.created_at,
}


async def _resolve_limit(db: AsyncSession) -> int:
    """讀取 `dashboard.ranking_size` 設定；未設 / 非正整數則 fallback 10。"""
    value = await system_setting_service.get_int(
        _RANKING_SIZE_KEY, _DEFAULT_LIMIT, db
    )
    if value <= 0:
        return _DEFAULT_LIMIT
    return value


def _apply_direction(column, order: RankingOrder):
    """依 order 決定欄位排序方向（asc / desc）。"""
    return column.asc() if order == "asc" else column.desc()


async def _top_agents(
    user_uid: str,
    order_by: RankingOrderBy,
    order: RankingOrder,
    limit: int,
    db: AsyncSession,
) -> list[Agent]:
    stmt = (
        select(Agent)
        .where(
            Agent.is_deleted == False,  # noqa: E712
            Agent.owner_user_uid == uuid.UUID(user_uid),
        )
        .order_by(
            _apply_direction(_AGENT_ORDER_COLS[order_by], order),
            _apply_direction(Agent.pid, order),
        )
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().unique().all())


async def _top_skills(
    user_uid: str,
    order_by: RankingOrderBy,
    order: RankingOrder,
    limit: int,
    db: AsyncSession,
) -> list[Skill]:
    stmt = (
        select(Skill)
        .where(
            Skill.is_deleted == False,  # noqa: E712
            Skill.owner_user_uid == uuid.UUID(user_uid),
        )
        .order_by(
            _apply_direction(_SKILL_ORDER_COLS[order_by], order),
            _apply_direction(Skill.pid, order),
        )
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().unique().all())


async def _top_scripts(
    user_uid: str,
    order_by: RankingOrderBy,
    order: RankingOrder,
    limit: int,
    db: AsyncSession,
) -> list[Script]:
    stmt = (
        select(Script)
        .where(
            Script.is_deleted == False,  # noqa: E712
            Script.owner_user_uid == uuid.UUID(user_uid),
        )
        .order_by(
            _apply_direction(_SCRIPT_ORDER_COLS[order_by], order),
            _apply_direction(Script.pid, order),
        )
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().unique().all())


def _agent_to_item(agent: Agent, is_favorited: bool) -> dict:
    owner_username = agent.owner.username if agent.owner else ""
    return {
        "type": "agent",
        "uid": str(agent.agent_uid),
        "name": agent.name,
        "description": agent.description,
        "favorite_count": agent.favorite_count,
        "download_count": agent.download_count,
        "is_favorited": is_favorited,
        "owner": {
            "user_uid": str(agent.owner_user_uid),
            "display_name": owner_username,
        },
        "created_at": to_taipei_iso(agent.created_at) or "",
        "updated_at": to_taipei_iso(agent.updated_at) or "",
    }


def _skill_to_item(skill: Skill, is_favorited: bool) -> dict:
    owner_username = skill.owner.username if skill.owner else ""
    return {
        "type": "skill",
        "uid": str(skill.skill_uid),
        "name": skill.name,
        "description": skill.description,
        "favorite_count": skill.favorite_count,
        "download_count": skill.download_count,
        "is_favorited": is_favorited,
        "owner": {
            "user_uid": str(skill.owner_user_uid),
            "display_name": owner_username,
        },
        "created_at": to_taipei_iso(skill.created_at) or "",
        "updated_at": to_taipei_iso(skill.updated_at) or "",
    }


def _script_to_item(script: Script, is_favorited: bool) -> dict:
    owner_username = script.owner.username if script.owner else ""
    return {
        "type": "script",
        "uid": str(script.script_uid),
        "name": script.name,
        "description": script.description,
        "favorite_count": script.favorite_count,
        "download_count": script.download_count,
        "is_favorited": is_favorited,
        "owner": {
            "user_uid": str(script.owner_user_uid),
            "display_name": owner_username,
        },
        "created_at": to_taipei_iso(script.created_at) or "",
        "updated_at": to_taipei_iso(script.updated_at) or "",
    }


def _sort_key(item: dict, order_by: RankingOrderBy):
    """合併後重排的 key：主欄位 desc；`created_at` 用 ISO 字串可字典序比較。"""
    if order_by == "created_at":
        return item["created_at"]
    return item[order_by]


async def list_rankings(
    user_uid: str,
    type_filter: RankingTypeFilter,
    order_by: RankingOrderBy,
    db: AsyncSession,
    limit: int | None = None,
    order: RankingOrder = "desc",
) -> dict:
    """跨三類資源產生 top-N 排行榜。

    聚合流程：
    1. 解析 limit（未傳時取 `dashboard.ranking_size`）
    2. 依 `type_filter` 撈三類 / 單類各自 top N（依 order 決方向）
    3. 逐類折 `is_favorited`（沿用 v1.2.1 `is_favorited_bulk`）
    4. 合併後依 `order_by` + `order` 重排，截 limit
    """
    resolved_limit = limit if limit is not None and limit > 0 else (
        await _resolve_limit(db)
    )

    agents: list[Agent] = []
    skills: list[Skill] = []
    scripts: list[Script] = []

    if type_filter in ("all", "agent"):
        agents = await _top_agents(
            user_uid, order_by, order, resolved_limit, db
        )
    if type_filter in ("all", "skill"):
        skills = await _top_skills(
            user_uid, order_by, order, resolved_limit, db
        )
    if type_filter in ("all", "script"):
        scripts = await _top_scripts(
            user_uid, order_by, order, resolved_limit, db
        )

    agent_fav_set = await user_favorite_repository.is_favorited_bulk(
        user_uid, "agent", [str(a.agent_uid) for a in agents], db
    )
    skill_fav_set = await user_favorite_repository.is_favorited_bulk(
        user_uid, "skill", [str(s.skill_uid) for s in skills], db
    )
    script_fav_set = await user_favorite_repository.is_favorited_bulk(
        user_uid, "script", [str(s.script_uid) for s in scripts], db
    )

    items: list[dict] = []
    for a in agents:
        items.append(
            _agent_to_item(a, str(a.agent_uid) in agent_fav_set)
        )
    for s in skills:
        items.append(
            _skill_to_item(s, str(s.skill_uid) in skill_fav_set)
        )
    for sc in scripts:
        items.append(
            _script_to_item(sc, str(sc.script_uid) in script_fav_set)
        )

    items.sort(key=lambda x: _sort_key(x, order_by), reverse=(order == "desc"))
    items = items[:resolved_limit]

    return {"items": items}
