"""Agentic Skill Suggestion Service（v1.3.6 Phase 4）。

對個人視角的 list / detail / accept / reject 邏輯：
- list：lazy 標記過期 → 撈 owner 的 suggestion
- detail：含來源記憶 inline 摘要（依 scope 撈對應記憶 keywords / topic）
- accept：打包 system_prompt 為 zip → upload_skill → mark_approved
        （帶 agent_uid 時同步將 skill 加入 agent.skill_uids）
- reject：mark_rejected
"""

from __future__ import annotations

import logging
import time
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.datetime import to_taipei_iso
from app.core.exceptions import AppError
from app.models.agentic_skill_suggestion import AgenticSkillSuggestion
from app.repositories import (
    agent_repository,
    agentic_skill_suggestion_repository,
    chat_memory_repository,
    project_memory_repository,
    user_memory_repository,
)
from app.services import skill_factory_service

logger = logging.getLogger(__name__)

NOT_FOUND_DETAIL = "找不到指定的 Skill 候選"
AGENT_NOT_OWNED = "Agent 不存在或無權限"


# ---------- 共用 mapper ----------


def _to_item_dict(s: AgenticSkillSuggestion) -> dict:
    """對外 schema：對齊 AgenticSkillSuggestionItem。"""
    return {
        "uid": str(s.agentic_skill_suggestion_uid),
        "scope": s.scope,
        "scope_uid": str(s.scope_uid),
        "name": s.name,
        "description": s.description,
        "system_prompt": s.system_prompt,
        "confidence": float(s.confidence),
        "source_memory_uids": [
            str(u) for u in (s.source_memory_uids or [])
        ],
        "status": s.status,
        "created_skill_uid": (
            str(s.created_skill_uid) if s.created_skill_uid else None
        ),
        "created_at": to_taipei_iso(s.created_at) or "",
        "updated_at": to_taipei_iso(s.updated_at) or "",
    }


# ---------- list ----------


async def list_suggestions(
    *,
    user_uid: str,
    scope: str | None,
    status: str | None,
    page: int,
    size: int,
    db: AsyncSession,
) -> dict:
    """個人列表 + 統計（task §4-1）。lazy 標記過期 pending。"""
    # 進入時 lazy 標記過期；commit 在 router 層處理
    await skill_factory_service.lazy_expire_old_pending(db)

    items, total = await agentic_skill_suggestion_repository.list_by_owner(
        owner_user_uid=user_uid,
        scope=scope,
        status=status,
        page=page,
        size=size,
        db=db,
    )
    return {
        "items": [_to_item_dict(s) for s in items],
        "page": page,
        "size": size,
        "total": total,
    }


# ---------- detail（含來源記憶 inline 摘要）----------


async def get_suggestion_detail(
    *,
    user_uid: str,
    suggestion_uid: str,
    db: AsyncSession,
) -> dict:
    s = await agentic_skill_suggestion_repository.get_by_uid(
        suggestion_uid, user_uid, db
    )
    if s is None:
        raise AppError(
            detail=NOT_FOUND_DETAIL, response_code=404, status_code=404
        )

    source_briefs = await _resolve_source_memory_briefs(s, db)
    return {
        "suggestion": _to_item_dict(s),
        "source_memories": source_briefs,
    }


async def _resolve_source_memory_briefs(
    s: AgenticSkillSuggestion, db: AsyncSession
) -> list[dict]:
    """依 scope + source_memory_uids 撈來源記憶簡要（不顯示 memory uid）。"""
    src_uids = {str(u) for u in (s.source_memory_uids or [])}
    if not src_uids:
        return []
    out: list[dict] = []
    if s.scope == "session":
        memories = await chat_memory_repository.list_by_session(
            str(s.scope_uid), db
        )
        for m in memories:
            if str(m.chat_memory_uid) in src_uids:
                out.append(
                    {
                        "scope": "session",
                        "topic": m.topic,
                        "keywords": list(m.keywords or []),
                        "entities": list(m.entities or []),
                        "created_at": to_taipei_iso(m.created_at),
                    }
                )
    elif s.scope == "project":
        memories = await project_memory_repository.list_by_project(
            str(s.scope_uid), db
        )
        for m in memories:
            if str(m.project_memory_uid) in src_uids:
                out.append(
                    {
                        "scope": "project",
                        "topic": m.topic,
                        "keywords": list(m.keywords or []),
                        "entities": list(m.entities or []),
                        "created_at": to_taipei_iso(m.created_at),
                    }
                )
    else:  # user
        memories = await user_memory_repository.list_by_user(
            str(s.scope_uid), db
        )
        for m in memories:
            if str(m.user_memory_uid) in src_uids:
                out.append(
                    {
                        "scope": "user",
                        "topic": m.topic,
                        "keywords": list(m.keywords or []),
                        "entities": list(m.entities or []),
                        "created_at": to_taipei_iso(m.created_at),
                    }
                )
    return out


# ---------- accept ----------


async def accept_suggestion(
    *,
    user_uid: str,
    suggestion_uid: str,
    agent_uid: str | None,
    db: AsyncSession,
) -> dict:
    """accept 流程：建立 skill → mark_approved → 可選掛載到 agent。"""
    s = await agentic_skill_suggestion_repository.get_by_uid(
        suggestion_uid, user_uid, db
    )
    if s is None:
        raise AppError(
            detail=NOT_FOUND_DETAIL, response_code=404, status_code=404
        )
    if s.status != "pending":
        raise AppError(
            detail=f"此候選已處理（狀態：{s.status}）",
            response_code=400,
            status_code=400,
        )

    # 若帶 agent_uid 先驗證擁有權（在建立 skill 之前；避免 skill 建好但掛失敗的孤兒情境）
    target_agent = None
    if agent_uid:
        try:
            uuid.UUID(agent_uid)
        except ValueError:
            raise AppError(
                detail=AGENT_NOT_OWNED, response_code=404, status_code=404
            ) from None
        target_agent = await agent_repository.get_by_uid(agent_uid, db)
        if target_agent is None or str(target_agent.owner_uid) != user_uid:
            raise AppError(
                detail=AGENT_NOT_OWNED, response_code=404, status_code=404
            )

    # 建立 skill（沿用 v1.1.7 流程：打包 prompt.md zip）
    skill_info = await skill_factory_service._create_skill_from_suggestion(  # noqa: SLF001
        user_uid=user_uid,
        name=s.name,
        description=s.description,
        system_prompt=s.system_prompt,
        db=db,
    )

    await agentic_skill_suggestion_repository.mark_approved(
        s, skill_info["skill_uid"], db
    )

    mounted = False
    if target_agent is not None:
        existing_skill_uids = await agent_repository.get_skill_uids(
            agent_uid, db
        )
        existing_set = {str(u) for u in existing_skill_uids}
        if skill_info["skill_uid"] not in existing_set:
            new_skill_uids = list(existing_set) + [skill_info["skill_uid"]]
            await agent_repository.set_skill_uids(
                agent_uid, new_skill_uids, db
            )
        mounted = True

    # 寫 agentic:skill:log（v1.3.6：approved_v2）
    await skill_factory_service._log_event(  # noqa: SLF001
        {
            "ts": time.time(),
            "type": "approved_v2",
            "user_uid": user_uid,
            "scope": s.scope,
            "scope_uid": str(s.scope_uid),
            "session_uid": (
                str(s.scope_uid) if s.scope == "session" else None
            ),
            "signature": s.signature,
            "suggestion_uid": str(s.agentic_skill_suggestion_uid),
            "created_skill_uid": skill_info["skill_uid"],
            "agent_uid": agent_uid,
            "mounted": mounted,
            "suggestion_snapshot": {
                "name": s.name,
                "description": s.description,
                "confidence": float(s.confidence),
            },
        }
    )

    return {
        "skill_uid": skill_info["skill_uid"],
        "skill_name": skill_info["name"],
        "agent_uid": agent_uid,
        "mounted": mounted,
    }


# ---------- reject ----------


async def reject_suggestion(
    *,
    user_uid: str,
    suggestion_uid: str,
    db: AsyncSession,
) -> dict:
    s = await agentic_skill_suggestion_repository.get_by_uid(
        suggestion_uid, user_uid, db
    )
    if s is None:
        raise AppError(
            detail=NOT_FOUND_DETAIL, response_code=404, status_code=404
        )
    if s.status != "pending":
        raise AppError(
            detail=f"此候選已處理（狀態：{s.status}）",
            response_code=400,
            status_code=400,
        )

    await agentic_skill_suggestion_repository.mark_rejected(s, db)

    await skill_factory_service._log_event(  # noqa: SLF001
        {
            "ts": time.time(),
            "type": "rejected_v2",
            "user_uid": user_uid,
            "scope": s.scope,
            "scope_uid": str(s.scope_uid),
            "session_uid": (
                str(s.scope_uid) if s.scope == "session" else None
            ),
            "signature": s.signature,
            "suggestion_uid": str(s.agentic_skill_suggestion_uid),
            "suggestion_snapshot": {
                "name": s.name,
                "description": s.description,
                "confidence": float(s.confidence),
            },
        }
    )

    return {"uid": str(s.agentic_skill_suggestion_uid), "status": s.status}
