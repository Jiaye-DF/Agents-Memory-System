"""v1.1.7 Agentic Skill 工廠 PoC：分析 session 記憶並產生 Skill 候選。

Pipeline（每一步都必須 log）：
1. Rule check：memory 數量、主題聚焦度、cooldown
2. Generator：呼叫 LLM structured output 產出候選
3. Redis 暫存候選（7 天）、寫 agentic:skill:log stream（30 天等效 MAXLEN）
4. approve / reject 標記並沿用 POST /skills 流程入庫
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import time
import uuid
import zipfile
from collections import Counter
from datetime import datetime
from typing import TypedDict

from fastapi import UploadFile
from starlette.datastructures import Headers
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.datetime import to_taipei_iso
from app.core.exceptions import AppError
from app.core.redis import get_redis
from app.models.chat_memory import ChatMemory
from app.repositories import chat_memory_repository, chat_session_repository
from app.services import llm_metering, skill_service, system_setting_service

logger = logging.getLogger(__name__)

# ---------- 常數 ----------

DEFAULT_MIN_MEMORY_COUNT = 10
DEFAULT_TOPIC_CONCENTRATION = 0.3
DEFAULT_ANALYZER_MODEL = "anthropic/claude-haiku-4-5"
DEFAULT_COOLDOWN_HOURS = 24
SUGGESTION_TTL_SECONDS = 7 * 24 * 3600
SIGNATURE_TTL_SECONDS = 30 * 24 * 3600  # 保留 30 天以觀察重複觸發
LOG_STREAM_KEY = "agentic:skill:log"
# 估算：每 session 每天最多數次事件，30 天約 1000 筆保守上限
LOG_STREAM_MAXLEN = 10000

SESSION_NOT_FOUND = "找不到指定的 Session"
SUGGESTION_NOT_FOUND = "找不到指定的 Skill 候選"


# ---------- Redis key helpers ----------


def _suggestion_key(user_uid: str, session_uid: str) -> str:
    return f"skill:suggestion:{user_uid}:{session_uid}"


def _signature_key(user_uid: str, session_uid: str) -> str:
    return f"skill:signature:{user_uid}:{session_uid}"


# ---------- helpers ----------


def _compute_signature(memories: list[ChatMemory]) -> str:
    topics = sorted({(m.topic or "").strip() for m in memories if m.topic})
    raw = "|".join(topics).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _topic_concentration_ratio(memories: list[ChatMemory]) -> tuple[float, list[tuple[str, int]]]:
    topics = [m.topic.strip() for m in memories if m.topic and m.topic.strip()]
    if not topics:
        return 0.0, []
    counter = Counter(topics)
    top3 = counter.most_common(3)
    ratio = sum(c for _, c in top3) / len(topics)
    return ratio, top3


def _build_llm_payload(memories: list[ChatMemory]) -> str:
    """把記憶序列化為 LLM 輸入（JSON）。"""
    payload: list[dict] = []
    for m in memories:
        payload.append(
            {
                "chat_memory_uid": str(m.chat_memory_uid),
                "topic": m.topic or "",
                "keywords": list(m.keywords or []),
                "entities": list(m.entities or []),
            }
        )
    return json.dumps({"memories": payload}, ensure_ascii=False)


async def _log_event(event: dict) -> None:
    """寫入 agentic:skill:log Redis stream（含 MAXLEN 限制）。失敗僅記 logger。"""
    try:
        redis = get_redis()
    except RuntimeError:
        logger.debug("Redis 尚未初始化，略過 skill_factory log")
        return

    payload = {
        "ts": str(event.get("ts") or time.time()),
        "payload": json.dumps(event, ensure_ascii=False),
    }
    try:
        await redis.xadd(
            LOG_STREAM_KEY,
            payload,
            maxlen=LOG_STREAM_MAXLEN,
            approximate=True,
        )
    except Exception as exc:
        logger.warning("寫入 agentic:skill:log 失敗: %s", exc)


def _suggestion_to_item(idx: int, suggestion: dict) -> dict:
    """回傳 API 可直接序列化的 item（已含 status）。"""
    return {
        "idx": idx,
        "name": suggestion.get("name") or "",
        "description": suggestion.get("description") or "",
        "system_prompt": suggestion.get("system_prompt") or "",
        "confidence": float(suggestion.get("confidence") or 0.0),
        "source_memory_uids": list(suggestion.get("source_memory_uids") or []),
        "status": suggestion.get("status") or "pending",
        "created_skill_uid": suggestion.get("created_skill_uid"),
        "created_at": suggestion.get("created_at"),
    }


async def _load_suggestions_raw(
    user_uid: str, session_uid: str
) -> list[dict]:
    redis = get_redis()
    raw = await redis.get(_suggestion_key(user_uid, session_uid))
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Skill 候選 JSON 解析失敗 session=%s", session_uid)
        return []
    if not isinstance(data, list):
        return []
    return [d for d in data if isinstance(d, dict)]


async def _save_suggestions_raw(
    user_uid: str, session_uid: str, suggestions: list[dict]
) -> None:
    redis = get_redis()
    await redis.set(
        _suggestion_key(user_uid, session_uid),
        json.dumps(suggestions, ensure_ascii=False),
        ex=SUGGESTION_TTL_SECONDS,
    )


# ---------- Analyzer ----------


async def analyze_session(
    session_uid: str,
    user_uid: str,
    db: AsyncSession,
) -> list[dict] | None:
    """Worker 呼叫的入口：判斷是否觸發並產出候選。

    Returns:
        list[dict] 候選清單（新增的），若跳過則回 None。
    """
    enabled = await system_setting_service.get_bool(
        "agentic.skill_factory.enabled", True, db
    )
    if not enabled:
        logger.info(
            "skill_factory: analyze session_uid=%s decision=skipped:disabled",
            session_uid,
        )
        return None

    min_memory = await system_setting_service.get_int(
        "agentic.skill_factory.min_memory_count",
        DEFAULT_MIN_MEMORY_COUNT,
        db,
    )
    concentration_threshold = await system_setting_service.get_float(
        "agentic.skill_factory.topic_concentration",
        DEFAULT_TOPIC_CONCENTRATION,
        db,
    )
    model = await system_setting_service.get(
        "agentic.skill_factory.analyzer_model", DEFAULT_ANALYZER_MODEL, db
    ) or DEFAULT_ANALYZER_MODEL
    cooldown_hours = await system_setting_service.get_int(
        "agentic.skill_factory.cooldown_hours", DEFAULT_COOLDOWN_HOURS, db
    )

    memories = await chat_memory_repository.list_by_session(session_uid, db)
    memory_count = len(memories)

    ratio, top3 = _topic_concentration_ratio(memories)

    logger.info(
        "skill_factory: analyze session_uid=%s memory_count=%s "
        "top3=%s ratio=%.3f threshold=%.3f min_memory=%s",
        session_uid,
        memory_count,
        top3,
        ratio,
        concentration_threshold,
        min_memory,
    )

    if memory_count < min_memory:
        logger.info(
            "skill_factory: analyze session_uid=%s decision=skipped:"
            "memory_count_below_min(%s<%s)",
            session_uid,
            memory_count,
            min_memory,
        )
        return None

    if ratio < concentration_threshold:
        logger.info(
            "skill_factory: analyze session_uid=%s decision=skipped:"
            "topic_concentration_below_threshold(%.3f<%.3f)",
            session_uid,
            ratio,
            concentration_threshold,
        )
        return None

    # Cooldown / signature dedup
    signature = _compute_signature(memories)
    try:
        redis = get_redis()
        prev_sig = await redis.get(_signature_key(user_uid, session_uid))
    except RuntimeError:
        logger.warning(
            "skill_factory: Redis 尚未初始化，跳過 session=%s", session_uid
        )
        return None

    if prev_sig and str(prev_sig) == signature:
        logger.info(
            "skill_factory: analyze session_uid=%s decision=skipped:"
            "signature_in_cooldown(sig=%s)",
            session_uid,
            signature[:12],
        )
        return None

    # LLM 生成
    llm_input = _build_llm_payload(memories)
    logger.info(
        "skill_factory: llm_input session_uid=%s model=%s payload=%s",
        session_uid,
        model,
        llm_input,
    )
    try:
        # v1.3.0：經 llm_metering 集中進入點記成本 / 延遲
        suggestion_raw = await llm_metering.call_llm_metered(
            purpose=llm_metering.PURPOSE_SKILL_FACTORY,
            session_uid=session_uid,
            user_uid=user_uid,
            memories_payload=llm_input,
            model=model,
        )
    except AppError as exc:
        logger.warning(
            "skill_factory: llm_call_failed session_uid=%s detail=%s",
            session_uid,
            exc.detail,
        )
        await _log_event(
            {
                "ts": time.time(),
                "type": "error",
                "user_uid": user_uid,
                "session_uid": session_uid,
                "signature": signature,
                "error": exc.detail,
            }
        )
        return None
    except Exception as exc:
        logger.exception(
            "skill_factory: llm_call_error session_uid=%s: %s",
            session_uid,
            exc,
        )
        return None

    logger.info(
        "skill_factory: llm_output session_uid=%s suggestion=%s",
        session_uid,
        json.dumps(suggestion_raw, ensure_ascii=False),
    )

    # name / description 缺失視為無效候選（不進入清單）
    if not suggestion_raw.get("name") or not suggestion_raw.get(
        "system_prompt"
    ):
        logger.info(
            "skill_factory: analyze session_uid=%s decision=skipped:"
            "llm_returned_empty_suggestion",
            session_uid,
        )
        return None

    now_iso = to_taipei_iso(datetime.now()) or ""
    new_item = {
        "idx": 0,  # 實際 idx 在 append 時分配
        "name": suggestion_raw["name"],
        "description": suggestion_raw["description"],
        "system_prompt": suggestion_raw["system_prompt"],
        "confidence": suggestion_raw["confidence"],
        "source_memory_uids": suggestion_raw["source_memory_uids"],
        "status": "pending",
        "created_skill_uid": None,
        "created_at": now_iso,
        "signature": signature,
    }

    existing = await _load_suggestions_raw(user_uid, session_uid)
    new_item["idx"] = len(existing)
    updated = [*existing, new_item]
    await _save_suggestions_raw(user_uid, session_uid, updated)

    # 寫入 signature cooldown（cooldown_hours 小時 TTL，但 signature 本身可留更久）
    try:
        cooldown_seconds = max(1, cooldown_hours * 3600)
        await redis.set(
            _signature_key(user_uid, session_uid),
            signature,
            ex=max(cooldown_seconds, SIGNATURE_TTL_SECONDS),
        )
    except Exception as exc:
        logger.warning(
            "skill_factory: 寫入 signature key 失敗 session=%s: %s",
            session_uid,
            exc,
        )

    await _log_event(
        {
            "ts": time.time(),
            "type": "generated",
            "user_uid": user_uid,
            "session_uid": session_uid,
            "signature": signature,
            "suggestion_snapshot": {
                "name": new_item["name"],
                "description": new_item["description"],
                "confidence": new_item["confidence"],
            },
            "source_memory_uids": new_item["source_memory_uids"],
            "idx": new_item["idx"],
        }
    )

    logger.info(
        "skill_factory: analyze session_uid=%s decision=triggered idx=%s "
        "confidence=%.3f",
        session_uid,
        new_item["idx"],
        new_item["confidence"],
    )

    return [new_item]


# ---------- API layer ----------


async def _ensure_session_owner(
    session_uid: str, user_uid: str, db: AsyncSession
) -> None:
    """驗證 session 擁有權；admin 也不能代查（40-permission 規範）。"""
    session = await chat_session_repository.get_by_uid(session_uid, db)
    if session is None or str(session.owner_user_uid) != user_uid:
        raise AppError(
            detail=SESSION_NOT_FOUND,
            response_code=404,
            status_code=404,
        )


async def list_suggestions(
    user_uid: str, session_uid: str, db: AsyncSession
) -> dict:
    await _ensure_session_owner(session_uid, user_uid, db)
    try:
        raw = await _load_suggestions_raw(user_uid, session_uid)
    except RuntimeError:
        raw = []
    items = [_suggestion_to_item(i, s) for i, s in enumerate(raw)]
    return {"items": items}


async def _ensure_idx(
    suggestions: list[dict], idx: int
) -> dict:
    if idx < 0 or idx >= len(suggestions):
        raise AppError(
            detail=SUGGESTION_NOT_FOUND,
            response_code=404,
            status_code=404,
        )
    return suggestions[idx]


def _build_single_file_zip(filename: str, content: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(filename, content)
    return buf.getvalue()


def _to_upload_file(filename: str, data: bytes) -> UploadFile:
    """把 bytes 包成 FastAPI UploadFile，給 skill_service.upload_skill 使用。"""
    headers = Headers({"content-type": "application/zip"})
    return UploadFile(
        file=io.BytesIO(data),
        filename=filename,
        headers=headers,
    )


async def approve_suggestion(
    user_uid: str, session_uid: str, idx: int, db: AsyncSession
) -> dict:
    await _ensure_session_owner(session_uid, user_uid, db)

    suggestions = await _load_suggestions_raw(user_uid, session_uid)
    target = await _ensure_idx(suggestions, idx)
    if target.get("status") in ("approved", "rejected"):
        raise AppError(
            detail=f"此候選已處理（狀態：{target.get('status')}）",
            response_code=400,
            status_code=400,
        )

    # 打包成單檔 zip（prompt.md）
    prompt_md = (
        f"# {target['name']}\n\n"
        f"{target['description']}\n\n"
        f"---\n\n"
        f"{target['system_prompt']}\n"
    )
    skill_uid = uuid.uuid4()
    zip_bytes = _build_single_file_zip("prompt.md", prompt_md)
    zip_filename = f"skill-{skill_uid}.zip"
    upload_file = _to_upload_file(zip_filename, zip_bytes)

    result = await skill_service.upload_skill(
        user_uid=user_uid,
        name=target["name"],
        description=target["description"],
        files=[upload_file],
        db=db,
    )

    target["status"] = "approved"
    target["created_skill_uid"] = result.get("skill_uid")
    await _save_suggestions_raw(user_uid, session_uid, suggestions)

    await _log_event(
        {
            "ts": time.time(),
            "type": "approved",
            "user_uid": user_uid,
            "session_uid": session_uid,
            "signature": target.get("signature"),
            "idx": idx,
            "created_skill_uid": result.get("skill_uid"),
            "suggestion_snapshot": {
                "name": target["name"],
                "description": target["description"],
                "confidence": target.get("confidence"),
            },
            "source_memory_uids": target.get("source_memory_uids", []),
        }
    )

    logger.info(
        "skill_factory: approved session_uid=%s idx=%s skill_uid=%s",
        session_uid,
        idx,
        result.get("skill_uid"),
    )

    return {
        "skill_uid": str(result.get("skill_uid")),
        "name": target["name"],
        "description": target["description"],
    }


async def reject_suggestion(
    user_uid: str, session_uid: str, idx: int, db: AsyncSession
) -> None:
    await _ensure_session_owner(session_uid, user_uid, db)

    suggestions = await _load_suggestions_raw(user_uid, session_uid)
    target = await _ensure_idx(suggestions, idx)
    if target.get("status") in ("approved", "rejected"):
        raise AppError(
            detail=f"此候選已處理（狀態：{target.get('status')}）",
            response_code=400,
            status_code=400,
        )

    target["status"] = "rejected"
    await _save_suggestions_raw(user_uid, session_uid, suggestions)

    await _log_event(
        {
            "ts": time.time(),
            "type": "rejected",
            "user_uid": user_uid,
            "session_uid": session_uid,
            "signature": target.get("signature"),
            "idx": idx,
            "suggestion_snapshot": {
                "name": target["name"],
                "description": target["description"],
                "confidence": target.get("confidence"),
            },
            "source_memory_uids": target.get("source_memory_uids", []),
        }
    )

    logger.info(
        "skill_factory: rejected session_uid=%s idx=%s",
        session_uid,
        idx,
    )


# ---------- Admin debug ----------


class _LogItem(TypedDict):
    id: str
    ts: str | None
    event: dict[str, object]


class _LogListResult(TypedDict):
    items: list[_LogItem]


async def list_recent_logs(limit: int = 50) -> _LogListResult:
    """讀取 agentic:skill:log stream 最近 N 筆事件。"""
    try:
        redis = get_redis()
    except RuntimeError:
        return {"items": []}

    try:
        entries = await redis.xrevrange(LOG_STREAM_KEY, count=limit)
    except Exception as exc:
        logger.warning("讀取 agentic:skill:log 失敗: %s", exc)
        return {"items": []}

    items: list[_LogItem] = []
    for entry_id, fields in entries:
        try:
            payload = fields.get("payload") if isinstance(fields, dict) else None
            data: dict[str, object] = json.loads(payload) if payload else {}
        except Exception:
            data = {}
        items.append(
            {
                "id": str(entry_id),
                "ts": fields.get("ts") if isinstance(fields, dict) else None,
                "event": data,
            }
        )
    return {"items": items}
