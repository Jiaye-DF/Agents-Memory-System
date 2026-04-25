import json
import logging
import time
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.datetime import to_taipei_iso
from app.core.exceptions import AppError
from app.core.pagination import paginate
from app.core.queue_keys import (
    PROJECT_MEMORY_QUEUE_KEY,
    USER_MEMORY_QUEUE_KEY,
)
from app.core.redis import get_redis
from app.models.user import User
from app.repositories import (
    chat_memory_repository,
    chat_project_repository,
    chat_session_repository,
    project_memory_repository,
    user_memory_repository,
    user_repository,
)
from app.schemas.admin.schemas import UserUpdateRequest
from app.services import memory_trace_service, rag_service

logger = logging.getLogger(__name__)


def _user_to_dict(user: User) -> dict:
    return {
        "user_uid": str(user.user_uid),
        "username": user.username,
        "account": user.account,
        "role_name": user.role.name,
        "is_active": user.is_active,
        "login_fail_count": user.login_fail_count,
        "locked_until": to_taipei_iso(user.locked_until),
        "created_at": to_taipei_iso(user.created_at),
    }


async def list_users(
    cursor: str | None, limit: int, db: AsyncSession
) -> dict:
    page = await paginate(db, user_repository.stmt_all_users(), cursor, limit)
    return {
        "items": [_user_to_dict(u) for u in page.items],
        "next_cursor": page.next_cursor,
        "has_next": page.has_next,
    }


async def get_user(user_uid: str, db: AsyncSession) -> dict:
    user = await user_repository.get_by_uid(user_uid, db)
    if user is None:
        raise AppError(detail="找不到指定的使用者", response_code=404, status_code=404)
    return _user_to_dict(user)


async def update_user(
    user_uid: str, data: UserUpdateRequest, db: AsyncSession
) -> dict:
    user = await user_repository.get_by_uid(user_uid, db)
    if user is None:
        raise AppError(detail="找不到指定的使用者", response_code=404, status_code=404)

    update_data: dict = {}

    if data.role_uid is not None:
        role = await user_repository.get_role_by_uid(data.role_uid, db)
        if role is None:
            raise AppError(
                detail="指定的角色不存在", response_code=400, status_code=400
            )
        update_data["role_uid"] = role.user_role_uid

    if data.unlock is True:
        update_data["login_fail_count"] = 0
        update_data["locked_until"] = None
        update_data["is_active"] = True

    if not update_data:
        raise AppError(detail="未提供任何更新欄位", response_code=400, status_code=400)

    await user_repository.update(user, update_data, db)
    return _user_to_dict(user)


async def disable_user(user_uid: str, db: AsyncSession) -> dict:
    """停用 user（v1.3.5 跨層生命週期）。

    propose §3-3 / Arch §5-2 表格：
    - 連動清除（hard delete）：`chat_memory` / 該 user 所有 project 的 `project_memory` / `user_memory`
    - 同 transaction 完成；任一步失敗 → 由 db 上下文 rollback
    - 停用 = `is_active=False`（軟性，仍保留 user row 與 audit），對應 propose 表格「User 停用 / 刪除」

    為避免「停用後 reactivate 仍空著三層記憶」造成困惑，停用即視同清資料；
    若需保留可後續版本再分「停用（保資料）vs 刪除（清資料）」雙路徑。
    """
    user = await user_repository.get_by_uid(user_uid, db)
    if user is None:
        raise AppError(detail="找不到指定的使用者", response_code=404, status_code=404)

    # 1. 清 chat_memory（該 user 全部 session）
    try:
        await chat_memory_repository.hard_delete_by_user(user_uid, db)
    except Exception as exc:
        logger.warning("停用 user 清 chat_memory 失敗 user=%s: %s", user_uid, exc)
        raise

    # 2. 清 project_memory（該 user 名下所有 project，含已軟刪）
    try:
        project_uids = await chat_project_repository.list_uids_by_owner(
            user_uid, db
        )
        for puid in project_uids:
            await project_memory_repository.hard_delete_by_project(puid, db)
    except Exception as exc:
        logger.warning(
            "停用 user 清 project_memory 失敗 user=%s: %s", user_uid, exc
        )
        raise

    # 3. 清 user_memory
    try:
        await user_memory_repository.hard_delete_by_user(user_uid, db)
    except Exception as exc:
        logger.warning("停用 user 清 user_memory 失敗 user=%s: %s", user_uid, exc)
        raise

    # 4. 標 is_active=False
    await user_repository.update(user, {"is_active": False}, db)
    return _user_to_dict(user)


def _project_memory_to_dict(memory) -> dict:
    return {
        "project_memory_uid": str(memory.project_memory_uid),
        "chat_project_uid": str(memory.chat_project_uid),
        "source_session_uids": [
            str(x) for x in (memory.source_session_uids or [])
        ],
        "keywords": list(memory.keywords or []),
        "entities": list(memory.entities or []),
        "topic": memory.topic,
        "created_at": to_taipei_iso(memory.created_at) or "",
    }


def _user_memory_to_dict(memory) -> dict:
    return {
        "user_memory_uid": str(memory.user_memory_uid),
        "owner_user_uid": str(memory.owner_user_uid),
        "source_session_uids": [
            str(x) for x in (memory.source_session_uids or [])
        ],
        "source_project_uids": [
            str(x) for x in (memory.source_project_uids or [])
        ],
        "keywords": list(memory.keywords or []),
        "entities": list(memory.entities or []),
        "topic": memory.topic,
        "created_at": to_taipei_iso(memory.created_at) or "",
    }


async def list_project_memories(
    chat_project_uid: str, db: AsyncSession
) -> dict:
    """v1.3.5：admin 列出指定 project 的 project_memory（不含 embedding）。"""
    items = await project_memory_repository.list_by_project(
        chat_project_uid, db
    )
    return {"items": [_project_memory_to_dict(m) for m in items]}


async def list_user_memories(user_uid: str, db: AsyncSession) -> dict:
    """v1.3.5：admin 列出指定 user 的 user_memory。"""
    items = await user_memory_repository.list_by_user(user_uid, db)
    return {"items": [_user_memory_to_dict(m) for m in items]}


async def list_roles(db: AsyncSession) -> dict:
    roles = await user_repository.list_roles(db)
    return {
        "roles": [
            {
                "user_role_uid": str(r.user_role_uid),
                "name": r.name,
                "description": r.description,
            }
            for r in roles
        ]
    }


# ---------- v1.3.1：記憶 pipeline trace（admin debug） ----------


def _ts_ms_to_taipei_iso(ts_ms: int | None) -> str | None:
    """把 unix ms 轉為 Asia/Taipei ISO 字串（依 CLAUDE.md 時區規範）。"""
    if not ts_ms:
        return None
    dt = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)
    return to_taipei_iso(dt)


async def get_memory_trace(session_uid: str, limit: int) -> dict:
    """讀取 session 的記憶 pipeline trace；找不到回 count=0 / items=[]。"""
    raw_items = await memory_trace_service.read(session_uid, limit=limit)
    items: list[dict] = []
    for it in raw_items:
        items.append(
            {
                "ts": _ts_ms_to_taipei_iso(it.get("ts")),
                "step": it.get("step") or "",
                "outcome": it.get("outcome") or "",
                "duration_ms": it.get("duration_ms"),
                "message_uids": list(it.get("message_uids") or []),
                "extra": dict(it.get("extra") or {}),
            }
        )
    return {
        "session_uid": session_uid,
        "count": len(items),
        "items": items,
    }


# ---------- v1.3.5：跨層聚合手動觸發 + 檢索診斷 ----------


async def queue_project_aggregate(
    chat_project_uid: str, owner_user_uid: str | None
) -> dict:
    """admin 手動觸發 project 聚合：LPUSH project:memory:queue。"""
    redis = get_redis()
    payload = json.dumps(
        {
            "project_uid": chat_project_uid,
            "owner_user_uid": owner_user_uid,
            "trigger_at": time.time(),
            "manual": True,
        }
    )
    await redis.lpush(PROJECT_MEMORY_QUEUE_KEY, payload)
    try:
        depth = int(await redis.llen(PROJECT_MEMORY_QUEUE_KEY))
    except Exception:
        depth = 0
    return {"queued": True, "queue_depth": depth}


async def queue_user_aggregate(user_uid: str) -> dict:
    """admin 手動觸發 user 聚合：LPUSH user:memory:queue。"""
    redis = get_redis()
    payload = json.dumps(
        {
            "user_uid": user_uid,
            "trigger_at": time.time(),
            "manual": True,
        }
    )
    await redis.lpush(USER_MEMORY_QUEUE_KEY, payload)
    try:
        depth = int(await redis.llen(USER_MEMORY_QUEUE_KEY))
    except Exception:
        depth = 0
    return {"queued": True, "queue_depth": depth}


async def debug_three_layer_retrieve(
    session_uid: str, query_text: str, db: AsyncSession
) -> dict:
    """admin 檢索診斷：對指定 session 與 query 跑三層 + 融合，回傳完整明細。

    Session 必須存在（admin 不限定 owner，因為診斷用途）。
    回傳結構對齊 ThreeLayerRagResult schema。
    """
    session = await chat_session_repository.get_by_uid(session_uid, db)
    if session is None:
        raise AppError(
            detail="找不到指定的 Session", response_code=404, status_code=404
        )

    project_uid = (
        str(session.chat_project_uid)
        if session.chat_project_uid is not None
        else None
    )
    owner_user_uid = str(session.owner_user_uid)

    result = await rag_service.retrieve_three_layer(
        session_uid, project_uid, owner_user_uid, query_text, db
    )

    session_items = [
        {
            "chat_memory_uid": str(mem.chat_memory_uid),
            "chat_session_uid": str(mem.chat_session_uid),
            "source_chat_message_uids": [
                str(x) for x in (mem.source_chat_message_uids or [])
            ],
            "keywords": list(mem.keywords or []),
            "entities": list(mem.entities or []),
            "topic": mem.topic,
            "created_at": to_taipei_iso(mem.created_at) or "",
        }
        for mem, _score in result.get("session", [])
    ]
    project_items = [
        _project_memory_to_dict(mem)
        for mem, _score in result.get("project", [])
    ]
    user_items = [
        _user_memory_to_dict(mem)
        for mem, _score in result.get("user", [])
    ]
    fused_items = [
        {
            "scope": item.scope,
            "memory_uid": item.memory_uid,
            "topic": item.topic,
            "keywords": item.keywords,
            "entities": item.entities,
            "rrf_score": item.rrf_score,
            "source_rank": item.source_rank,
        }
        for item in result.get("fused", [])
    ]
    return {
        "session": session_items,
        "project": project_items,
        "user": user_items,
        "fused": fused_items,
    }
