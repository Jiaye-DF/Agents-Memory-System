import asyncio
import json
import logging
import zipfile
from collections.abc import AsyncIterator
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.openrouter import model_supports_vision
from app.core.datetime import to_taipei_iso
from app.core.exceptions import AppError
from app.core.pagination import paginate
from app.core.redis import get_redis
from app.models.agent import Agent
from app.models.chat_memory import ChatMemory
from app.models.chat_message import ChatMessage
from app.models.chat_project import ChatProject
from app.models.chat_session import ChatSession
from app.models.skill import Skill
from app.repositories import (
    agent_repository,
    chat_memory_repository,
    chat_message_repository,
    chat_project_repository,
    chat_session_repository,
    session_agent_repository,
    skill_repository,
)
from app.schemas.chat.schemas import (
    ChatProjectCreateRequest,
    ChatProjectUpdateRequest,
    ChatSessionCreateRequest,
    ChatSessionMoveRequest,
    ChatSessionUpdateRequest,
)
from app.services import (
    chat_attachment_service,
    llm_metering,
    rag_service,
    session_event_service,
    system_setting_service,
)

logger = logging.getLogger(__name__)

DEFAULT_MAX_PROJECTS_PER_USER = 5
DEFAULT_MAX_SESSIONS_PER_PROJECT = 3
DEFAULT_MAX_ORPHAN_SESSIONS_PER_USER = 10
MAX_ORPHAN_SESSIONS_HARD_LIMIT = 30
DEFAULT_MODEL = "openai/gpt-4o-mini"
HISTORY_WINDOW = 20
MAX_RETRIES = 2
RETRY_BACKOFF_SECONDS = (0.5, 1.5)
# v1.3.3 多 Agent：軟性上限，可由 system_setting 覆寫
DEFAULT_MAX_AGENTS_PER_SESSION = 5
# v1.3.1 Skill 多 md 拼接：單一 md 字數警示閾值（可由 system_setting `skill.md_max_chars` 覆寫）
DEFAULT_SKILL_MD_MAX_CHARS = 8000

PROJECT_NOT_FOUND = "找不到指定的 Project"
SESSION_NOT_FOUND = "找不到指定的 Session"
AGENT_NOT_FOUND = "找不到指定的 Agent 或無權使用"
AGENT_NOT_IN_SESSION = "agent_not_in_session"
CANNOT_REMOVE_LAST_AGENT = "cannot_remove_last_agent"


# ---------- helpers ----------

def _project_to_dict(project: ChatProject, session_count: int) -> dict:
    return {
        "chat_project_uid": str(project.chat_project_uid),
        "owner_user_uid": str(project.owner_user_uid),
        "name": project.name,
        "description": project.description,
        "session_count": session_count,
        "is_active": project.is_active,
        "created_at": to_taipei_iso(project.created_at),
        "updated_at": to_taipei_iso(project.updated_at),
    }


def _session_to_dict(
    session: ChatSession,
    agent_name: str | None,
    message_count: int,
    last_message_at,
    agents: list[dict] | None = None,
) -> dict:
    return {
        "chat_session_uid": str(session.chat_session_uid),
        "chat_project_uid": (
            str(session.chat_project_uid)
            if session.chat_project_uid is not None
            else None
        ),
        # v1.3.3：agent_uid 改 nullable（多 Agent 過渡期保留）
        "agent_uid": (
            str(session.agent_uid)
            if session.agent_uid is not None
            else None
        ),
        "agent_name": agent_name,
        "title": session.title,
        "message_count": message_count,
        "last_message_at": to_taipei_iso(last_message_at),
        "is_active": session.is_active,
        "created_at": to_taipei_iso(session.created_at),
        "updated_at": to_taipei_iso(session.updated_at),
        # v1.3.3：session_agent 中介表內容（已軟刪除過濾、primary 在前）
        "agents": agents or [],
    }


def _session_agent_pair_to_dict(
    session_agent, agent_obj
) -> dict:
    """轉 (SessionAgent, Agent) tuple 為對外 dict（v1.3.3）。"""
    return {
        "session_agent_uid": str(session_agent.session_agent_uid),
        "agent_uid": str(session_agent.agent_uid),
        "agent_name": agent_obj.name if agent_obj is not None else None,
        # avatar_url 目前 agent 表沒有；保留欄位給日後擴充
        "agent_avatar_url": None,
        "role": session_agent.role,
        "created_at": to_taipei_iso(session_agent.created_at),
    }


async def _list_session_agents_dict(
    chat_session_uid: str, db: AsyncSession
) -> list[dict]:
    pairs = await session_agent_repository.list_by_session(
        chat_session_uid, db
    )
    return [_session_agent_pair_to_dict(sa, ag) for sa, ag in pairs]


def _memory_to_dict(memory: ChatMemory) -> dict:
    return {
        "chat_memory_uid": str(memory.chat_memory_uid),
        "chat_session_uid": str(memory.chat_session_uid),
        "source_chat_message_uids": [
            str(x) for x in (memory.source_chat_message_uids or [])
        ],
        "keywords": list(memory.keywords or []),
        "entities": list(memory.entities or []),
        "topic": memory.topic,
        "created_at": to_taipei_iso(memory.created_at),
    }


def _message_to_dict(
    message: ChatMessage,
    attachments_map: dict[str, dict] | None = None,
    agents_brief_map: dict[str, dict] | None = None,
) -> dict:
    attachment_uids: list[str] | None = None
    attachments: list[dict] | None = None
    raw_uids = message.attachment_uids
    if raw_uids:
        attachment_uids = [str(x) for x in raw_uids]
        if attachments_map:
            attachments = [
                attachments_map[u]
                for u in attachment_uids
                if u in attachments_map
            ]

    # v1.3.3：訊息來源 Agent
    responding_agent_uid: str | None = None
    responding_agent: dict | None = None
    if message.responding_agent_uid is not None:
        responding_agent_uid = str(message.responding_agent_uid)
        if agents_brief_map and responding_agent_uid in agents_brief_map:
            responding_agent = agents_brief_map[responding_agent_uid]

    return {
        "chat_message_uid": str(message.chat_message_uid),
        "chat_session_uid": str(message.chat_session_uid),
        "role": message.role,
        "content": message.content,
        "token_in": message.token_in,
        "token_out": message.token_out,
        "cost_usd": float(message.cost_usd) if message.cost_usd is not None else None,
        "model": message.model,
        "finish_reason": message.finish_reason,
        "created_at": to_taipei_iso(message.created_at),
        "attachment_uids": attachment_uids,
        "attachments": attachments,
        "responding_agent_uid": responding_agent_uid,
        "responding_agent": responding_agent,
    }


async def _agents_brief_map(
    agent_uids: list[str], db: AsyncSession
) -> dict[str, dict]:
    """批次取 agents 簡要資訊（給訊息列表的 responding_agent 用），避免 N+1。"""
    unique_uids = list({u for u in agent_uids if u})
    if not unique_uids:
        return {}
    agents = await agent_repository.get_by_uids(
        unique_uids, db, include_deleted=True
    )
    return {
        str(a.agent_uid): {
            "agent_uid": str(a.agent_uid),
            "name": a.name,
            "avatar_url": None,
        }
        for a in agents
    }


def _ensure_project_owner(project: ChatProject | None, user_uid: str) -> ChatProject:
    if project is None:
        raise AppError(detail=PROJECT_NOT_FOUND, response_code=404, status_code=404)
    if str(project.owner_user_uid) != user_uid:
        raise AppError(detail=PROJECT_NOT_FOUND, response_code=404, status_code=404)
    return project


async def _ensure_session_owner(
    session: ChatSession | None, user_uid: str, db: AsyncSession
) -> tuple[ChatSession, ChatProject | None]:
    """驗證 session 擁有權；回傳 session 與其所屬 project（游離 session 時 project 為 None）。"""
    if session is None:
        raise AppError(detail=SESSION_NOT_FOUND, response_code=404, status_code=404)
    if str(session.owner_user_uid) != user_uid:
        raise AppError(detail=SESSION_NOT_FOUND, response_code=404, status_code=404)
    project: ChatProject | None = None
    if session.chat_project_uid is not None:
        project = await chat_project_repository.get_by_uid(
            str(session.chat_project_uid), db
        )
    return session, project


def _auto_title_from_first_message(content: str) -> str:
    cleaned = content.replace("\r", " ").replace("\n", " ").strip()
    if len(cleaned) <= 30:
        return cleaned or "未命名對話"
    return cleaned[:30]


async def _skill_prompt_text(skill: Skill, db: AsyncSession) -> str:
    """讀取 skill zip 內所有 .md 並按檔名字典序拼接為 prompt 內容。

    v1.3.1：
    - 全部 `.md`（含子目錄、忽略目錄項）依 `info.filename` 字典序排序
    - 每份前加 `### {filename}` 標題；header 仍維持 skill name / description
    - 單份內容超過 `skill.md_max_chars`（預設 8000 字）僅 log warning，不截斷

    建議 Design-Base 規範類 Skill 採 `design-base-frontend` /
    `design-base-backend` / `design-base-auth` 命名（無強制）。
    """
    header = f"### {skill.name}\n{skill.description}\n"
    zip_path = skill.file_path
    if not zip_path or not Path(zip_path).exists():
        return header

    md_max_chars = await system_setting_service.get_int(
        "skill.md_max_chars", DEFAULT_SKILL_MD_MAX_CHARS, db
    )

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            md_files = [
                info for info in zf.infolist()
                if not info.is_dir() and info.filename.lower().endswith(".md")
            ]
            if not md_files:
                return header

            # 字典序：依 filename（含子目錄相對路徑）排序，確保跨平台輸出一致
            md_files.sort(key=lambda info: info.filename)

            sections: list[str] = [header]
            for info in md_files:
                try:
                    with zf.open(info, "r") as f:
                        content = f.read().decode("utf-8", errors="replace")
                except Exception as exc:
                    logger.warning(
                        "讀取 skill md 失敗 skill_uid=%s file=%s: %s",
                        skill.skill_uid,
                        info.filename,
                        exc,
                    )
                    continue

                content_len = len(content)
                if content_len > md_max_chars:
                    logger.warning(
                        "skill md 過長 skill_uid=%s file=%s len=%d max=%d",
                        skill.skill_uid,
                        info.filename,
                        content_len,
                        md_max_chars,
                    )

                # 標題用 zip 內相對路徑（含子目錄）；前面已加總 header，這裡用更深一級
                sections.append(
                    f"### {info.filename}\n{content.strip()}\n"
                )

            return "\n".join(sections).rstrip() + "\n"
    except Exception as exc:
        logger.warning("讀取 skill 內容失敗 skill_uid=%s: %s", skill.skill_uid, exc)
        return header


async def _build_system_prompt(
    agent: Agent,
    db: AsyncSession,
    memories: list[ChatMemory] | None = None,
) -> str:
    """組 agent + skills + 相關記憶的 system prompt。"""
    lines: list[str] = []
    lines.append(f"[Agent: {agent.name}]")
    role_text = agent.role_prompt or agent.identity or ""
    if role_text:
        lines.append(role_text)
    lines.append("")
    if agent.language:
        lines.append(f"Language: {agent.language}")
    if agent.style:
        lines.append(f"Style: {agent.style}")
    if agent.response_format:
        lines.append(f"Output format: {agent.response_format}")

    skill_uids = await agent_repository.get_skill_uids(str(agent.agent_uid), db)
    if skill_uids:
        lines.append("")
        lines.append("## Skills")
        for skill_uid in skill_uids:
            skill = await skill_repository.get_by_uid(skill_uid, db)
            if skill is None:
                continue
            lines.append(await _skill_prompt_text(skill, db))

    if memories:
        lines.append("")
        lines.append("## 相關記憶")
        lines.append("<memory>")
        for mem in memories:
            topic = mem.topic or "(未命名主題)"
            keywords = ", ".join(list(mem.keywords or []))
            lines.append(f"[{topic}] keywords: {keywords}")
        lines.append("</memory>")

    return "\n".join(lines).strip()


# ---------- Project ----------

async def list_projects(
    user_uid: str, cursor: str | None, limit: int, db: AsyncSession
) -> dict:
    page = await paginate(
        db, chat_project_repository.stmt_by_owner(user_uid), cursor, limit
    )
    count_map = await chat_project_repository.session_count_map(
        [str(p.chat_project_uid) for p in page.items], db
    )
    return {
        "items": [
            _project_to_dict(p, count_map.get(str(p.chat_project_uid), 0))
            for p in page.items
        ],
        "next_cursor": page.next_cursor,
        "has_next": page.has_next,
    }


async def get_project(
    chat_project_uid: str, user_uid: str, db: AsyncSession
) -> dict:
    project = await chat_project_repository.get_by_uid(chat_project_uid, db)
    project = _ensure_project_owner(project, user_uid)
    count_map = await chat_project_repository.session_count_map(
        [str(project.chat_project_uid)], db
    )
    return _project_to_dict(project, count_map.get(str(project.chat_project_uid), 0))


async def create_project(
    user_uid: str, data: ChatProjectCreateRequest, db: AsyncSession
) -> dict:
    max_projects = await system_setting_service.get_int(
        "chat.max_projects_per_user", DEFAULT_MAX_PROJECTS_PER_USER, db
    )
    current = await chat_project_repository.count_by_owner(user_uid, db)
    if current >= max_projects:
        raise AppError(
            detail=f"已達上限，admin 設定 {max_projects}/user",
            response_code=400,
            status_code=400,
        )

    project = await chat_project_repository.create(
        {
            "owner_user_uid": user_uid,
            "name": data.name,
            "description": data.description,
        },
        db,
    )
    return _project_to_dict(project, 0)


async def update_project(
    chat_project_uid: str,
    user_uid: str,
    data: ChatProjectUpdateRequest,
    db: AsyncSession,
) -> dict:
    project = await chat_project_repository.get_by_uid(chat_project_uid, db)
    project = _ensure_project_owner(project, user_uid)

    update_data: dict = {}
    if data.name is not None:
        update_data["name"] = data.name
    if data.description is not None:
        update_data["description"] = data.description

    if not update_data:
        raise AppError(
            detail="未提供任何更新欄位", response_code=400, status_code=400
        )
    await chat_project_repository.update(project, update_data, db)
    count_map = await chat_project_repository.session_count_map(
        [str(project.chat_project_uid)], db
    )
    return _project_to_dict(project, count_map.get(str(project.chat_project_uid), 0))


async def delete_project(
    chat_project_uid: str, user_uid: str, db: AsyncSession
) -> None:
    project = await chat_project_repository.get_by_uid(chat_project_uid, db)
    project = _ensure_project_owner(project, user_uid)
    await chat_project_repository.soft_delete(project, db)


# ---------- Session ----------

async def list_sessions(
    chat_project_uid: str, user_uid: str, cursor: str | None, limit: int, db: AsyncSession
) -> dict:
    project = await chat_project_repository.get_by_uid(chat_project_uid, db)
    _ensure_project_owner(project, user_uid)

    page = await paginate(
        db, chat_session_repository.stmt_by_project(chat_project_uid), cursor, limit
    )
    session_uids = [str(s.chat_session_uid) for s in page.items]
    stats_map = await chat_session_repository.message_stats_map(session_uids, db)

    # v1.3.3：批次預取每個 session 的 agents（含 primary / member）
    agents_per_session: dict[str, list[dict]] = {}
    for sid in session_uids:
        agents_per_session[sid] = await _list_session_agents_dict(sid, db)

    items = []
    for s in page.items:
        sid = str(s.chat_session_uid)
        count, last_at = stats_map.get(sid, (0, None))
        agents_dicts = agents_per_session.get(sid, [])
        # 顯示用 agent_name：取 primary 那筆，沒有則 None
        primary_dict = next(
            (a for a in agents_dicts if a["role"] == "primary"), None
        )
        primary_name = primary_dict["agent_name"] if primary_dict else None
        items.append(
            _session_to_dict(s, primary_name, count, last_at, agents=agents_dicts)
        )
    return {
        "items": items,
        "next_cursor": page.next_cursor,
        "has_next": page.has_next,
    }


async def get_session(
    chat_session_uid: str, user_uid: str, db: AsyncSession
) -> dict:
    session = await chat_session_repository.get_by_uid(chat_session_uid, db)
    session, _ = await _ensure_session_owner(session, user_uid, db)

    agents_dicts = await _list_session_agents_dict(
        str(session.chat_session_uid), db
    )
    primary_dict = next(
        (a for a in agents_dicts if a["role"] == "primary"), None
    )
    primary_name = primary_dict["agent_name"] if primary_dict else None
    stats_map = await chat_session_repository.message_stats_map(
        [str(session.chat_session_uid)], db
    )
    count, last_at = stats_map.get(str(session.chat_session_uid), (0, None))
    return _session_to_dict(
        session, primary_name, count, last_at, agents=agents_dicts
    )


async def _ensure_orphan_capacity(user_uid: str, db: AsyncSession) -> None:
    max_orphan = await system_setting_service.get_int(
        "chat.max_orphan_sessions_per_user",
        DEFAULT_MAX_ORPHAN_SESSIONS_PER_USER,
        db,
    )
    max_orphan = min(max_orphan, MAX_ORPHAN_SESSIONS_HARD_LIMIT)
    current = await chat_session_repository.count_orphan_by_owner(user_uid, db)
    if current >= max_orphan:
        raise AppError(
            detail=f"游離對話已達上限，admin 設定 {max_orphan}/user",
            response_code=400,
            status_code=400,
        )


async def _ensure_project_capacity(
    chat_project_uid: str, db: AsyncSession
) -> None:
    max_sessions = await system_setting_service.get_int(
        "chat.max_sessions_per_project", DEFAULT_MAX_SESSIONS_PER_PROJECT, db
    )
    current = await chat_session_repository.count_by_project(
        chat_project_uid, db
    )
    if current >= max_sessions:
        raise AppError(
            detail=f"已達上限，admin 設定 {max_sessions}/project",
            response_code=400,
            status_code=400,
        )


def _resolve_create_agent_uids(data: ChatSessionCreateRequest) -> list[str]:
    """合併 deprecated agent_uid 與 agent_uids；保序去重。第一個視為 primary。"""
    candidates: list[str] = []
    if data.agent_uids:
        candidates.extend(data.agent_uids)
    if data.agent_uid:
        candidates.append(data.agent_uid)
    return list(dict.fromkeys(candidates))


async def _ensure_agent_visible(
    agent_uid: str, user_uid: str, db: AsyncSession
):
    """共用：取 agent 並檢查 user 可見性（owner 或 public）。回傳 Agent。"""
    agent = await agent_repository.get_by_uid(agent_uid, db)
    if agent is None:
        raise AppError(detail=AGENT_NOT_FOUND, response_code=404, status_code=404)
    if str(agent.owner_uid) != user_uid and agent.visibility != "public":
        raise AppError(detail=AGENT_NOT_FOUND, response_code=404, status_code=404)
    return agent


async def _get_max_agents_per_session(db: AsyncSession) -> int:
    return await system_setting_service.get_int(
        "multi_agent.max_per_session",
        DEFAULT_MAX_AGENTS_PER_SESSION,
        db,
    )


async def create_session(
    user_uid: str, data: ChatSessionCreateRequest, db: AsyncSession
) -> dict:
    if data.chat_project_uid is not None:
        project = await chat_project_repository.get_by_uid(
            data.chat_project_uid, db
        )
        _ensure_project_owner(project, user_uid)
        await _ensure_project_capacity(data.chat_project_uid, db)
    else:
        await _ensure_orphan_capacity(user_uid, db)

    # v1.3.3：解析 agent_uids（兼容 deprecated agent_uid）
    agent_uids = _resolve_create_agent_uids(data)
    if not agent_uids:
        raise AppError(detail=AGENT_NOT_FOUND, response_code=404, status_code=404)

    max_agents = await _get_max_agents_per_session(db)
    if len(agent_uids) > max_agents:
        raise AppError(
            detail=f"每個 Session 最多掛 {max_agents} 個 Agent",
            response_code=422,
            status_code=422,
        )

    # 逐筆驗證可見性；第一筆作為 primary
    agents_obj = []
    for uid in agent_uids:
        ag = await _ensure_agent_visible(uid, user_uid, db)
        agents_obj.append(ag)
    primary_agent = agents_obj[0]

    title = data.title or "未命名對話"
    session = await chat_session_repository.create(
        {
            "chat_project_uid": data.chat_project_uid,
            "owner_user_uid": user_uid,
            # 向後相容欄位：寫入 primary 的 uid（v1.3.3 標 deprecated）
            "agent_uid": str(primary_agent.agent_uid),
            "title": title,
        },
        db,
    )

    # 寫入 session_agent：第一筆 primary，其餘 member
    for idx, ag in enumerate(agents_obj):
        await session_agent_repository.add(
            str(session.chat_session_uid),
            str(ag.agent_uid),
            db,
            role="primary" if idx == 0 else "member",
        )

    agents_dicts = await _list_session_agents_dict(
        str(session.chat_session_uid), db
    )
    return _session_to_dict(
        session, primary_agent.name, 0, None, agents=agents_dicts
    )


async def list_orphan_sessions(
    user_uid: str, cursor: str | None, limit: int, db: AsyncSession
) -> dict:
    page = await paginate(
        db, chat_session_repository.stmt_orphan_by_owner(user_uid), cursor, limit
    )
    session_uids = [str(s.chat_session_uid) for s in page.items]
    stats_map = await chat_session_repository.message_stats_map(session_uids, db)

    agents_per_session: dict[str, list[dict]] = {}
    for sid in session_uids:
        agents_per_session[sid] = await _list_session_agents_dict(sid, db)

    items = []
    for s in page.items:
        sid = str(s.chat_session_uid)
        count, last_at = stats_map.get(sid, (0, None))
        agents_dicts = agents_per_session.get(sid, [])
        primary_dict = next(
            (a for a in agents_dicts if a["role"] == "primary"), None
        )
        primary_name = primary_dict["agent_name"] if primary_dict else None
        items.append(
            _session_to_dict(s, primary_name, count, last_at, agents=agents_dicts)
        )
    return {
        "items": items,
        "next_cursor": page.next_cursor,
        "has_next": page.has_next,
    }


async def move_session(
    chat_session_uid: str,
    user_uid: str,
    data: ChatSessionMoveRequest,
    db: AsyncSession,
) -> dict:
    """把 session 移入指定 project；chat_project_uid 傳 None 代表移出為游離。"""
    session = await chat_session_repository.get_by_uid(chat_session_uid, db)
    session, _current_project = await _ensure_session_owner(session, user_uid, db)

    target_uid = data.chat_project_uid
    current_uid = (
        str(session.chat_project_uid)
        if session.chat_project_uid is not None
        else None
    )
    sid = str(session.chat_session_uid)

    async def _build_response() -> dict:
        agents_dicts = await _list_session_agents_dict(sid, db)
        primary_dict = next(
            (a for a in agents_dicts if a["role"] == "primary"), None
        )
        primary_name = primary_dict["agent_name"] if primary_dict else None
        stats_map_inner = await chat_session_repository.message_stats_map(
            [sid], db
        )
        count, last_at = stats_map_inner.get(sid, (0, None))
        return _session_to_dict(
            session, primary_name, count, last_at, agents=agents_dicts
        )

    if target_uid == current_uid:
        # 不變；直接回現況
        return await _build_response()

    if target_uid is not None:
        project = await chat_project_repository.get_by_uid(target_uid, db)
        _ensure_project_owner(project, user_uid)
        await _ensure_project_capacity(target_uid, db)
    else:
        await _ensure_orphan_capacity(user_uid, db)

    await chat_session_repository.update(
        session, {"chat_project_uid": target_uid}, db
    )
    return await _build_response()


async def update_session(
    chat_session_uid: str,
    user_uid: str,
    data: ChatSessionUpdateRequest,
    db: AsyncSession,
) -> dict:
    session = await chat_session_repository.get_by_uid(chat_session_uid, db)
    session, _ = await _ensure_session_owner(session, user_uid, db)

    update_data: dict = {}
    if data.title is not None:
        update_data["title"] = data.title

    if not update_data:
        raise AppError(
            detail="未提供任何更新欄位", response_code=400, status_code=400
        )
    await chat_session_repository.update(session, update_data, db)

    agents_dicts = await _list_session_agents_dict(
        str(session.chat_session_uid), db
    )
    primary_dict = next(
        (a for a in agents_dicts if a["role"] == "primary"), None
    )
    primary_name = primary_dict["agent_name"] if primary_dict else None
    stats_map = await chat_session_repository.message_stats_map(
        [str(session.chat_session_uid)], db
    )
    count, last_at = stats_map.get(str(session.chat_session_uid), (0, None))
    return _session_to_dict(
        session, primary_name, count, last_at, agents=agents_dicts
    )


# ---------- Session Agents (v1.3.3) ----------

async def list_session_agents(
    chat_session_uid: str, user_uid: str, db: AsyncSession
) -> dict:
    """列出 session 已掛 agents。"""
    session = await chat_session_repository.get_by_uid(chat_session_uid, db)
    await _ensure_session_owner(session, user_uid, db)
    agents_dicts = await _list_session_agents_dict(chat_session_uid, db)
    return {"agents": agents_dicts}


async def add_agent_to_session(
    chat_session_uid: str,
    agent_uid: str,
    user_uid: str,
    db: AsyncSession,
) -> dict:
    """加掛 agent 至 session。
    - 驗證 user 對 session 與 agent 的權限
    - 超過 multi_agent.max_per_session 上限回 422
    - 已存在且有效則直接 idempotent 回現況
    - 軟刪過的 (session, agent) 會被復活為 member
    """
    session = await chat_session_repository.get_by_uid(chat_session_uid, db)
    await _ensure_session_owner(session, user_uid, db)
    await _ensure_agent_visible(agent_uid, user_uid, db)

    # 上限檢查（軟刪不計）
    current_count = await session_agent_repository.count_active(
        chat_session_uid, db
    )
    existing = await session_agent_repository.get_pair(
        chat_session_uid, agent_uid, db
    )
    will_increase = existing is None or existing.is_deleted
    if will_increase:
        max_agents = await _get_max_agents_per_session(db)
        if current_count >= max_agents:
            raise AppError(
                detail=f"每個 Session 最多掛 {max_agents} 個 Agent",
                response_code=422,
                status_code=422,
            )

    await session_agent_repository.add(
        chat_session_uid, agent_uid, db, role="member"
    )
    await db.commit()

    agents_dicts = await _list_session_agents_dict(chat_session_uid, db)
    return {"agents": agents_dicts}


async def remove_agent_from_session(
    chat_session_uid: str,
    agent_uid: str,
    user_uid: str,
    db: AsyncSession,
) -> dict:
    """移除 agent；最後一個禁止移除；移除 primary 時 promote 加入時間最早的 member。"""
    session = await chat_session_repository.get_by_uid(chat_session_uid, db)
    await _ensure_session_owner(session, user_uid, db)

    target = await session_agent_repository.get_pair(
        chat_session_uid, agent_uid, db
    )
    if target is None or target.is_deleted:
        raise AppError(
            detail=AGENT_NOT_IN_SESSION,
            response_code=422,
            status_code=422,
        )

    current_count = await session_agent_repository.count_active(
        chat_session_uid, db
    )
    if current_count <= 1:
        raise AppError(
            detail=CANNOT_REMOVE_LAST_AGENT,
            response_code=422,
            status_code=422,
        )

    was_primary = target.role == "primary"
    ok = await session_agent_repository.remove(
        chat_session_uid, agent_uid, db
    )
    if not ok:
        raise AppError(
            detail=AGENT_NOT_IN_SESSION,
            response_code=422,
            status_code=422,
        )

    # 移除 primary：promote 剩下加入時間最早的 member
    if was_primary:
        remaining = await session_agent_repository.list_by_session(
            chat_session_uid, db
        )
        if remaining:
            # 列表已 primary 在前 + created_at 升序；此時剩下都是 member
            new_primary_sa, _ = remaining[0]
            await session_agent_repository.set_primary(
                chat_session_uid, str(new_primary_sa.agent_uid), db
            )
            # 同步把 chat_session.agent_uid（deprecated 欄位）改為新 primary
            await chat_session_repository.update(
                session, {"agent_uid": str(new_primary_sa.agent_uid)}, db
            )

    await db.commit()
    agents_dicts = await _list_session_agents_dict(chat_session_uid, db)
    return {"agents": agents_dicts}


async def promote_primary(
    chat_session_uid: str,
    agent_uid: str,
    user_uid: str,
    db: AsyncSession,
) -> dict:
    """將指定 agent 設為 primary（必須是 session 成員）。"""
    session = await chat_session_repository.get_by_uid(chat_session_uid, db)
    await _ensure_session_owner(session, user_uid, db)

    if not await session_agent_repository.is_member(
        chat_session_uid, agent_uid, db
    ):
        raise AppError(
            detail=AGENT_NOT_IN_SESSION,
            response_code=422,
            status_code=422,
        )

    try:
        await session_agent_repository.set_primary(
            chat_session_uid, agent_uid, db
        )
    except ValueError:
        raise AppError(
            detail=AGENT_NOT_IN_SESSION,
            response_code=422,
            status_code=422,
        ) from None

    # 同步 deprecated 欄位
    await chat_session_repository.update(
        session, {"agent_uid": agent_uid}, db
    )
    await db.commit()
    agents_dicts = await _list_session_agents_dict(chat_session_uid, db)
    return {"agents": agents_dicts}


async def get_skill_suggestions_stub(
    agent_uid: str,
    user_uid: str,
    db: AsyncSession,
    scope: str | None = None,
    scope_uid: str | None = None,
) -> dict:
    """v1.3.3 占位 endpoint：回空陣列 + hint='pending v1.3.6'。

    驗證 agent 對 user 可見；若帶 scope=session 則順便驗 session 擁有權，
    避免任何使用者在尚未上線時亂打。實際推薦邏輯由 v1.3.6 實作。
    """
    await _ensure_agent_visible(agent_uid, user_uid, db)
    if scope == "session" and scope_uid:
        session = await chat_session_repository.get_by_uid(scope_uid, db)
        await _ensure_session_owner(session, user_uid, db)
    return {"items": [], "hint": "pending v1.3.6"}


# ---------- Session Lifecycle ----------

async def delete_session(
    chat_session_uid: str, user_uid: str, db: AsyncSession
) -> None:
    session = await chat_session_repository.get_by_uid(chat_session_uid, db)
    session, _ = await _ensure_session_owner(session, user_uid, db)
    # v1.1.2：軟刪 Session 連動清除該 Session 下所有記憶
    try:
        await chat_memory_repository.hard_delete_by_session(
            chat_session_uid, db
        )
    except Exception as exc:
        logger.warning("刪除 Session 記憶失敗 session=%s: %s", chat_session_uid, exc)
    await chat_session_repository.soft_delete(session, db)


# ---------- Messages ----------

async def list_messages(
    chat_session_uid: str,
    user_uid: str,
    cursor: str | None,
    limit: int,
    db: AsyncSession,
) -> dict:
    session = await chat_session_repository.get_by_uid(chat_session_uid, db)
    await _ensure_session_owner(session, user_uid, db)

    page = await paginate(
        db,
        chat_message_repository.stmt_by_session(chat_session_uid),
        cursor,
        limit,
    )

    # 批次預取此頁所有 attachment（避免 N+1）
    all_uids: list[str] = []
    for m in page.items:
        if m.attachment_uids:
            all_uids.extend(str(x) for x in m.attachment_uids)
    attachments_map = await chat_attachment_service.get_summary_map_by_uids(
        list(set(all_uids)), db
    )

    # v1.3.3：批次預取 responding_agent 的 brief（避免每筆訊息一次查詢）
    agent_uids_in_messages = [
        str(m.responding_agent_uid)
        for m in page.items
        if m.responding_agent_uid is not None
    ]
    agents_brief_map = await _agents_brief_map(agent_uids_in_messages, db)

    return {
        "items": [
            _message_to_dict(m, attachments_map, agents_brief_map)
            for m in page.items
        ],
        "next_cursor": page.next_cursor,
        "has_next": page.has_next,
    }


async def list_memories(
    chat_session_uid: str, user_uid: str, db: AsyncSession
) -> dict:
    """列出 session 下所有記憶（僅擁有者；不含 embedding）。"""
    session = await chat_session_repository.get_by_uid(chat_session_uid, db)
    await _ensure_session_owner(session, user_uid, db)

    memories = await chat_memory_repository.list_by_session(chat_session_uid, db)
    return {
        "items": [_memory_to_dict(m) for m in memories],
    }


def _extract_usage(chunk: dict) -> dict | None:
    usage = chunk.get("usage") if isinstance(chunk, dict) else None
    if isinstance(usage, dict):
        return usage
    return None


def _extract_finish_reason(chunk: dict) -> str | None:
    choices = chunk.get("choices") if isinstance(chunk, dict) else None
    if not choices:
        return None
    reason = choices[0].get("finish_reason")
    if isinstance(reason, str) and reason:
        return reason
    return None


def _extract_delta_content(chunk: dict) -> str | None:
    choices = chunk.get("choices") if isinstance(chunk, dict) else None
    if not choices:
        return None
    delta = choices[0].get("delta") or {}
    content = delta.get("content")
    if isinstance(content, str):
        return content
    return None


async def send_message(
    chat_session_uid: str,
    user_uid: str,
    content: str,
    db: AsyncSession,
    attachment_uids: list[str] | None = None,
    mentioned_agent_uid: str | None = None,
) -> AsyncIterator[str]:
    """
    SSE generator：yield `event: delta/done/error\\ndata: {...}\\n\\n` 字串。

    v1.3.3 多 Agent：
    - mentioned_agent_uid 給定時，必須為 session 成員（否則回 422 agent_not_in_session）
    - 未給定時取 session 的 primary agent
    - 同訊息只跑一個 Agent（序列；A → B 由前端連續發訊驅動）
    """
    # 1. 驗證 session 擁有權
    session = await chat_session_repository.get_by_uid(chat_session_uid, db)
    try:
        session, _project = await _ensure_session_owner(session, user_uid, db)
    except AppError as exc:
        yield f"event: error\ndata: {json.dumps({'detail': exc.detail})}\n\n"
        return

    # 2. 解析要回應的 agent（v1.3.3：mention 優先 → primary → fallback）
    target_agent_uid: str | None = None
    if mentioned_agent_uid:
        is_member = await session_agent_repository.is_member(
            chat_session_uid, mentioned_agent_uid, db
        )
        if not is_member:
            yield (
                f"event: error\ndata: "
                f"{json.dumps({'detail': AGENT_NOT_IN_SESSION})}\n\n"
            )
            return
        target_agent_uid = mentioned_agent_uid
    else:
        primary_sa = await session_agent_repository.get_primary(
            chat_session_uid, db
        )
        if primary_sa is not None:
            target_agent_uid = str(primary_sa.agent_uid)
        elif session.agent_uid is not None:
            # 過渡期 fallback：session_agent 尚未灌入時走舊欄位
            target_agent_uid = str(session.agent_uid)

    if target_agent_uid is None:
        yield (
            f"event: error\ndata: "
            f"{json.dumps({'detail': '找不到對應的 Agent'})}\n\n"
        )
        return

    agent = await agent_repository.get_by_uid(target_agent_uid, db)
    if agent is None:
        yield f"event: error\ndata: {json.dumps({'detail': '找不到對應的 Agent'})}\n\n"
        return

    model = agent.model or DEFAULT_MODEL

    # 2.1 載入附件（若有）
    loaded_attachments: list[dict] = []
    if attachment_uids:
        try:
            loaded_attachments = await chat_attachment_service.load_for_prompt(
                attachment_uids, user_uid, chat_session_uid, db
            )
        except AppError as exc:
            yield f"event: error\ndata: {json.dumps({'detail': exc.detail})}\n\n"
            return
        except Exception as exc:
            logger.exception("載入附件失敗: %s", exc)
            yield (
                f"event: error\ndata: "
                f"{json.dumps({'detail': '載入附件失敗'})}\n\n"
            )
            return

    # 3. 寫 user message（保留 attachment_uids 於 DB）
    user_msg = await chat_message_repository.create(
        {
            "chat_session_uid": chat_session_uid,
            "role": "user",
            "content": content,
            "attachment_uids": (
                [str(u) for u in attachment_uids]
                if attachment_uids
                else None
            ),
        },
        db,
    )

    # 4. 若 session 為預設標題，用首則訊息填入
    if session.title in ("", "未命名對話"):
        new_title = _auto_title_from_first_message(content)
        await chat_session_repository.update(session, {"title": new_title}, db)

    # 5. 組 messages（system + 最近 N 則）
    # v1.1.2：先以 user content 檢索 session 記憶，注入 system prompt
    try:
        memories = await rag_service.retrieve(chat_session_uid, content, db)
    except Exception as exc:
        logger.warning("RAG 檢索失敗，忽略: %s", exc)
        memories = []

    # v1.3.0：metering 用 — RAG 命中筆數與 top-1 score
    rag_hit_count: int = len(memories) if memories else 0
    rag_max_score: float | None = None
    if memories:
        # rag_service.retrieve 回 list[ChatMemory]（取分數需從另一條 path 取，此處保守留 None）
        # 若需精確 score 後續可改 retrieve 回 (memory, score) tuple；此版只記命中數即可
        rag_max_score = None

    try:
        system_prompt = await _build_system_prompt(agent, db, memories=memories)
    except Exception as exc:
        logger.exception("組 system prompt 失敗: %s", exc)
        system_prompt = f"[Agent: {agent.name}]"

    history = await chat_message_repository.get_last_n(
        chat_session_uid, HISTORY_WINDOW, db
    )

    # 整合附件到 user content：
    #   - 文字 / PDF：前置 "File: {filename}\n{內容}" 拼入
    #   - 圖片：依 model 是否支援 vision 決定走 multimodal 或降級
    supports_vision = model_supports_vision(model)
    image_attachments = [a for a in loaded_attachments if a["kind"] == "image"]
    text_attachments = [a for a in loaded_attachments if a["kind"] == "text"]
    pdf_attachments = [a for a in loaded_attachments if a["kind"] == "pdf"]

    text_parts: list[str] = []
    for a in text_attachments:
        body = a.get("content_text") or ""
        warn = ""
        if a.get("text_fallback_latin1"):
            warn = "（編碼非 UTF-8，已以 latin-1 解碼，內容可能失真）"
        text_parts.append(f"File: {a['file_name']}{warn}\n{body}")
    for a in pdf_attachments:
        # v1.1.6 不抽 PDF 內文，僅標註讓 LLM 知道有附 PDF
        text_parts.append(
            f"File: {a['file_name']}（PDF，本版未抽取內文，如需解析請另議）"
        )

    if image_attachments and not supports_vision:
        # 決策 #10：優雅降級
        text_parts.append(
            f"(圖片附件已略過，目前 model「{model}」不支援 vision)"
        )

    merged_text = content
    if text_parts:
        merged_text = (
            content + "\n\n" + "\n\n".join(text_parts)
        ).strip()

    if image_attachments and supports_vision:
        user_content: list[dict] = [{"type": "text", "text": merged_text}]
        for a in image_attachments:
            data_url = a.get("content_b64")
            if not data_url:
                continue
            user_content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": data_url},
                }
            )
        latest_user_payload: str | list[dict] = user_content
    else:
        latest_user_payload = merged_text

    messages: list[dict] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    # history 不含剛寫入的 user_msg（get_last_n 按 pid 倒序）；但為確保語意正確，
    # 這裡自行組：先塞 history（排除已經是本次新增的 user message），最後塞本次 user message
    for m in history:
        if m.role not in ("user", "assistant"):
            continue
        if m.chat_message_uid == user_msg.chat_message_uid:
            continue
        messages.append({"role": m.role, "content": m.content})

    messages.append({"role": "user", "content": latest_user_payload})

    # 確保 commit 目前已寫入的 user message / session 更新，避免 generator 中斷後丟失
    await db.commit()

    # 6. 呼叫 LLM（帶重試）
    accumulated = ""
    usage: dict | None = None
    finish_reason: str | None = None
    last_error: str | None = None
    success_stream = False

    for attempt in range(MAX_RETRIES + 1):
        accumulated = ""
        usage = None
        finish_reason = None
        try:
            # v1.3.0：經 llm_metering 集中進入點，記錄成本 / 延遲 / RAG 命中
            # route='expensive'：v1.3.4 classifier 上線後改由 caller 動態傳入
            async for chunk in llm_metering.call_llm_metered_stream(
                purpose=llm_metering.PURPOSE_CHAT,
                route="expensive",
                session_uid=chat_session_uid,
                user_uid=user_uid,
                agent_uid=str(agent.agent_uid),
                rag_hit_count=rag_hit_count,
                rag_max_score=rag_max_score,
                messages=messages,
                model=model,
                temperature=agent.temperature,
                max_tokens=agent.max_tokens,
            ):
                delta = _extract_delta_content(chunk)
                if delta:
                    accumulated += delta
                    yield (
                        f"event: delta\ndata: "
                        f"{json.dumps({'content': delta})}\n\n"
                    )
                u = _extract_usage(chunk)
                if u is not None:
                    usage = u
                fr = _extract_finish_reason(chunk)
                if fr is not None:
                    finish_reason = fr
            success_stream = True
            break
        except AppError as exc:
            last_error = exc.detail
            logger.warning("LLM streaming 失敗 (attempt=%s): %s", attempt + 1, exc.detail)
        except Exception as exc:
            last_error = str(exc)
            logger.exception("LLM streaming 未預期錯誤 (attempt=%s)", attempt + 1)

        if attempt < MAX_RETRIES:
            backoff = (
                RETRY_BACKOFF_SECONDS[attempt]
                if attempt < len(RETRY_BACKOFF_SECONDS)
                else RETRY_BACKOFF_SECONDS[-1]
            )
            await asyncio.sleep(backoff)

    if not success_stream:
        yield (
            f"event: error\ndata: "
            f"{json.dumps({'detail': last_error or 'LLM 呼叫失敗'})}\n\n"
        )
        return

    # 7. 寫 assistant message
    token_in = None
    token_out = None
    cost_usd = None
    if usage:
        token_in = usage.get("prompt_tokens")
        token_out = usage.get("completion_tokens")
        # OpenRouter 可能使用 `total_cost` 或 `cost`
        cost = usage.get("total_cost")
        if cost is None:
            cost = usage.get("cost")
        if cost is not None:
            try:
                cost_usd = float(cost)
            except (TypeError, ValueError):
                cost_usd = None

    try:
        assistant_msg = await chat_message_repository.create(
            {
                "chat_session_uid": chat_session_uid,
                "role": "assistant",
                "content": accumulated,
                "token_in": token_in,
                "token_out": token_out,
                "cost_usd": cost_usd,
                "model": model,
                "finish_reason": finish_reason,
                # v1.3.3：標記哪個 Agent 回的
                "responding_agent_uid": str(agent.agent_uid),
            },
            db,
        )
        await db.commit()
    except Exception as exc:
        logger.exception("寫入 assistant message 失敗: %s", exc)
        yield (
            f"event: error\ndata: "
            f"{json.dumps({'detail': '訊息儲存失敗'})}\n\n"
        )
        return

    # v1.1.2：把 user / assistant 訊息丟入 memory queue，由 worker 非同步處理
    try:
        redis = get_redis()
        for mid in (user_msg.chat_message_uid, assistant_msg.chat_message_uid):
            await redis.lpush(
                "chat:memory:queue",
                json.dumps(
                    {
                        "session_uid": chat_session_uid,
                        "message_uid": str(mid),
                    }
                ),
            )
    except Exception as exc:
        logger.warning("enqueue memory 失敗（略過，不影響對話）: %s", exc)

    yield (
        f"event: done\ndata: "
        f"{json.dumps({'message_uid': str(assistant_msg.chat_message_uid), 'token_in': token_in, 'token_out': token_out, 'cost_usd': cost_usd, 'model': model, 'finish_reason': finish_reason})}\n\n"
    )


# ---------- v1.3.2：Session 級別非同步事件 SSE ----------

# keep-alive 心跳間隔（秒）；亦作為 pubsub.get_message timeout，
# 沒事件時 yield SSE comment（瀏覽器忽略）防反向代理閒置斷線
_SESSION_EVENT_PING_INTERVAL = 15.0


async def ensure_session_owner_for_events(
    chat_session_uid: str, user_uid: str, db: AsyncSession
) -> ChatSession:
    """SSE 連線建立前驗證 session 擁有權；不存在 / 非擁有者一律 404，不洩漏存在性差異。"""
    session = await chat_session_repository.get_by_uid(chat_session_uid, db)
    s, _ = await _ensure_session_owner(session, user_uid, db)
    return s


async def subscribe_session_events(
    chat_session_uid: str,
) -> AsyncIterator[str]:
    """訂閱 Redis pub/sub 並轉成 SSE 事件 stream。

    - 開場 yield `event: ready` 讓前端確認連線成功並停掉 polling fallback
    - 主迴圈以 `_SESSION_EVENT_PING_INTERVAL` 為 timeout：
      * 收到事件 → yield `event: <name>\\ndata: <json>\\n\\n`
      * 無事件 → yield SSE comment `: ping\\n\\n` keep-alive
    - finally 區塊 unsubscribe + close pubsub，避免 redis 連線洩漏
    """
    redis = get_redis()
    pubsub = redis.pubsub()
    channel = session_event_service.channel_for_session(chat_session_uid)
    await pubsub.subscribe(channel)
    try:
        # 開場握手：前端用 `ready` 事件停掉 polling fallback、確認 SSE 通道可用
        yield (
            f"event: {session_event_service.EVENT_READY}\n"
            f"data: {json.dumps({'session_uid': chat_session_uid})}\n\n"
        )

        while True:
            try:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=_SESSION_EVENT_PING_INTERVAL,
                )
            except asyncio.CancelledError:
                # 客戶端斷線 → 走 finally 清理
                raise
            except Exception as exc:
                logger.warning(
                    "subscribe_session_events 取訊息失敗 session=%s: %s",
                    chat_session_uid,
                    exc,
                )
                # 短暫休息避免空轉並繼續嘗試
                await asyncio.sleep(1)
                continue

            if message is None:
                # timeout：送 SSE comment 作 keep-alive（瀏覽器忽略）
                yield ": ping\n\n"
                continue

            data = message.get("data") if isinstance(message, dict) else None
            if not data:
                continue

            # decode_responses=True 已使 data 為 str；保險處理 bytes
            if isinstance(data, bytes):
                try:
                    data = data.decode("utf-8")
                except Exception:
                    continue

            try:
                payload = json.loads(data)
            except Exception:
                logger.warning(
                    "subscribe_session_events 解析 payload 失敗 session=%s: %s",
                    chat_session_uid,
                    data,
                )
                continue

            event_name = payload.get("event") or "message"
            yield f"event: {event_name}\ndata: {json.dumps(payload)}\n\n"
    finally:
        try:
            await pubsub.unsubscribe(channel)
        except Exception as exc:
            logger.warning(
                "subscribe_session_events unsubscribe 失敗 session=%s: %s",
                chat_session_uid,
                exc,
            )
        try:
            await pubsub.close()
        except Exception as exc:
            logger.warning(
                "subscribe_session_events close pubsub 失敗 session=%s: %s",
                chat_session_uid,
                exc,
            )
