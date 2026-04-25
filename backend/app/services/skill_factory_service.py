"""Agentic Skill 工廠 Service（v1.3.6 正式版 + v1.1.7 PoC 過渡相容）。

v1.3.6 主要升級：
- analyze 入口拆三層：analyze_session / analyze_project / analyze_user
  共用 `_analyze_scope` 進行 rule 檢查、signature 去重、LLM 生成、寫入 DB
- Suggestion 從 Redis 暫存搬到 DB 表 `agentic_skill_suggestion`（30 天保留）
- LLM 呼叫一律走 v1.3.0 `llm_metering.call_llm_metered`，purpose='skill_factory'，
  route 帶 scope（'session' / 'project' / 'user'）便於 admin SQL 拆桶
- analyzer system prompt 強制繁體中文輸出（沿用 v1.1.7 既有 prompt 已含此宣告）
- v1.1.7 Redis 暫存路徑保留 7 天唯讀過渡（list_suggestions 雙讀合併）

v1.1.7 PoC 路徑保留：
- approve_suggestion / reject_suggestion / list_suggestions：給既有 chat session 側邊欄使用
  本版起 approve / reject 同步維護 DB，但 idx 介面對外不變
- agentic:skill:log Redis stream 沿用，type=generated_v2 / approved_v2 / rejected_v2
  含 scope 欄位以區分 PoC 與正式版
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
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, TypedDict

from fastapi import UploadFile
from starlette.datastructures import Headers
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.datetime import to_taipei_iso
from app.core.exceptions import AppError
from app.core.redis import get_redis
from app.models.agentic_skill_suggestion import AgenticSkillSuggestion
from app.repositories import (
    agentic_skill_suggestion_repository,
    chat_memory_repository,
    chat_session_repository,
    project_memory_repository,
    user_memory_repository,
)
from app.services import llm_metering, skill_service, system_setting_service

logger = logging.getLogger(__name__)

# ---------- 常數（沿用 v1.1.7 PoC + v1.3.6 新增）----------

# v1.1.7 PoC 預設值（fallback）
DEFAULT_MIN_MEMORY_COUNT = 10
DEFAULT_TOPIC_CONCENTRATION = 0.3
DEFAULT_ANALYZER_MODEL = "anthropic/claude-haiku-4-5"
DEFAULT_COOLDOWN_HOURS = 24

# v1.3.6 新增預設（fallback；正式以 system_setting 為準）
DEFAULT_PROJECT_MIN_MEMORY = 20
DEFAULT_PROJECT_TOPIC_CONCENTRATION = 0.4
DEFAULT_USER_MIN_MEMORY = 30
DEFAULT_USER_TOPIC_CONCENTRATION = 0.5
DEFAULT_CONFIDENCE_FLOOR = 0.6
DEFAULT_SUGGESTION_TTL_DAYS = 30

# v1.1.7 Redis 暫存（過渡相容用，計畫於 7 天後移除）
SUGGESTION_TTL_SECONDS = 7 * 24 * 3600
SIGNATURE_TTL_SECONDS = 30 * 24 * 3600  # 觀察重複觸發
LOG_STREAM_KEY = "agentic:skill:log"
LOG_STREAM_MAXLEN = 10000

# scope 字串
SCOPE_SESSION = "session"
SCOPE_PROJECT = "project"
SCOPE_USER = "user"

SESSION_NOT_FOUND = "找不到指定的 Session"
SUGGESTION_NOT_FOUND = "找不到指定的 Skill 候選"


# ---------- v1.1.7 Redis key helpers（過渡用）----------


def _suggestion_key(user_uid: str, session_uid: str) -> str:
    return f"skill:suggestion:{user_uid}:{session_uid}"


# ---------- shared helpers ----------


class _MemoryLike(TypedDict, total=False):
    """三層記憶共用的最小欄位介面（避免硬綁 model 型別）。"""

    uid: str
    topic: str | None
    keywords: list[str]
    entities: list[str]


def _to_memory_like(memory_obj: Any, scope: str) -> _MemoryLike:
    """三層記憶物件 → 共用 dict（為 signature / payload 準備）。"""
    if scope == SCOPE_SESSION:
        return {
            "uid": str(getattr(memory_obj, "chat_memory_uid", "")),
            "topic": getattr(memory_obj, "topic", None),
            "keywords": list(getattr(memory_obj, "keywords", []) or []),
            "entities": list(getattr(memory_obj, "entities", []) or []),
        }
    if scope == SCOPE_PROJECT:
        return {
            "uid": str(getattr(memory_obj, "project_memory_uid", "")),
            "topic": getattr(memory_obj, "topic", None),
            "keywords": list(getattr(memory_obj, "keywords", []) or []),
            "entities": list(getattr(memory_obj, "entities", []) or []),
        }
    # user
    return {
        "uid": str(getattr(memory_obj, "user_memory_uid", "")),
        "topic": getattr(memory_obj, "topic", None),
        "keywords": list(getattr(memory_obj, "keywords", []) or []),
        "entities": list(getattr(memory_obj, "entities", []) or []),
    }


def _compute_signature(memories: list[_MemoryLike]) -> str:
    topics = sorted(
        {(m.get("topic") or "").strip() for m in memories if m.get("topic")}
    )
    raw = "|".join(topics).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _topic_concentration_ratio(
    memories: list[_MemoryLike],
) -> tuple[float, list[tuple[str, int]]]:
    topics = [
        (m.get("topic") or "").strip()
        for m in memories
        if m.get("topic") and (m.get("topic") or "").strip()
    ]
    if not topics:
        return 0.0, []
    counter = Counter(topics)
    top3 = counter.most_common(3)
    ratio = sum(c for _, c in top3) / len(topics)
    return ratio, top3


def _build_llm_payload(memories: list[_MemoryLike], scope: str) -> str:
    """三層記憶共用的 LLM 輸入序列化。"""
    payload: list[dict] = []
    for m in memories:
        payload.append(
            {
                "memory_uid": m.get("uid"),
                "topic": m.get("topic") or "",
                "keywords": m.get("keywords") or [],
                "entities": m.get("entities") or [],
            }
        )
    return json.dumps(
        {"scope": scope, "memories": payload}, ensure_ascii=False
    )


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


# ---------- settings 取值（含 v1.1.7 fallback）----------


async def _get_scope_thresholds(
    scope: str, db: AsyncSession
) -> tuple[int, float, int, float, str]:
    """讀三 scope 的 min_memory_count / topic_concentration / cooldown / floor / model。

    Returns:
        (min_memory_count, topic_concentration, cooldown_hours,
         confidence_floor, analyzer_model)
    """
    if scope == SCOPE_SESSION:
        # session 優先抓 *.session.*；沒有則 fallback 既有 v1.1.7 key
        min_memory = await system_setting_service.get_int(
            "agentic.skill_factory.session.min_memory_count",
            await system_setting_service.get_int(
                "agentic.skill_factory.min_memory_count",
                DEFAULT_MIN_MEMORY_COUNT,
                db,
            ),
            db,
        )
        ratio = await system_setting_service.get_float(
            "agentic.skill_factory.session.topic_concentration",
            await system_setting_service.get_float(
                "agentic.skill_factory.topic_concentration",
                DEFAULT_TOPIC_CONCENTRATION,
                db,
            ),
            db,
        )
    elif scope == SCOPE_PROJECT:
        min_memory = await system_setting_service.get_int(
            "agentic.skill_factory.project.min_memory_count",
            DEFAULT_PROJECT_MIN_MEMORY,
            db,
        )
        ratio = await system_setting_service.get_float(
            "agentic.skill_factory.project.topic_concentration",
            DEFAULT_PROJECT_TOPIC_CONCENTRATION,
            db,
        )
    elif scope == SCOPE_USER:
        min_memory = await system_setting_service.get_int(
            "agentic.skill_factory.user.min_memory_count",
            DEFAULT_USER_MIN_MEMORY,
            db,
        )
        ratio = await system_setting_service.get_float(
            "agentic.skill_factory.user.topic_concentration",
            DEFAULT_USER_TOPIC_CONCENTRATION,
            db,
        )
    else:
        raise ValueError(f"unknown scope: {scope}")

    cooldown_hours = await system_setting_service.get_int(
        "agentic.skill_factory.cooldown_hours", DEFAULT_COOLDOWN_HOURS, db
    )
    confidence_floor = await system_setting_service.get_float(
        "agentic.skill_factory.confidence_floor",
        DEFAULT_CONFIDENCE_FLOOR,
        db,
    )
    model = await system_setting_service.get(
        "agentic.skill_factory.analyzer_model", DEFAULT_ANALYZER_MODEL, db
    )
    if not model:
        model = DEFAULT_ANALYZER_MODEL
    return min_memory, ratio, cooldown_hours, confidence_floor, model


# ---------- analyzer 三層入口 ----------


async def analyze_session(
    session_uid: str,
    user_uid: str,
    db: AsyncSession,
) -> list[AgenticSkillSuggestion] | None:
    """v1.1.7 入口（保留）— 改寫為呼叫共用 `_analyze_scope`。"""
    memory_objs = await chat_memory_repository.list_by_session(session_uid, db)
    memories = [_to_memory_like(m, SCOPE_SESSION) for m in memory_objs]
    return await _analyze_scope(
        scope=SCOPE_SESSION,
        scope_uid=session_uid,
        user_uid=user_uid,
        memories=memories,
        db=db,
    )


async def analyze_project(
    project_uid: str,
    user_uid: str,
    db: AsyncSession,
) -> list[AgenticSkillSuggestion] | None:
    """v1.3.6 新入口：消費該 project 全部 project_memory。"""
    memory_objs = await project_memory_repository.list_by_project(
        project_uid, db
    )
    memories = [_to_memory_like(m, SCOPE_PROJECT) for m in memory_objs]
    return await _analyze_scope(
        scope=SCOPE_PROJECT,
        scope_uid=project_uid,
        user_uid=user_uid,
        memories=memories,
        db=db,
    )


async def analyze_user(
    user_uid: str,
    db: AsyncSession,
) -> list[AgenticSkillSuggestion] | None:
    """v1.3.6 新入口：消費該 user 全部 user_memory。"""
    memory_objs = await user_memory_repository.list_by_user(user_uid, db)
    memories = [_to_memory_like(m, SCOPE_USER) for m in memory_objs]
    return await _analyze_scope(
        scope=SCOPE_USER,
        scope_uid=user_uid,
        user_uid=user_uid,
        memories=memories,
        db=db,
    )


async def _analyze_scope(
    *,
    scope: str,
    scope_uid: str,
    user_uid: str,
    memories: list[_MemoryLike],
    db: AsyncSession,
) -> list[AgenticSkillSuggestion] | None:
    """共用 analyzer 主流程（rule → signature → LLM → 寫 DB → log）。

    Returns:
        新建立的 suggestion list（單筆，與 v1.1.7 行為一致）；跳過則回 None。
    """
    enabled = await system_setting_service.get_bool(
        "agentic.skill_factory.enabled", True, db
    )
    if not enabled:
        logger.info(
            "skill_factory: analyze scope=%s scope_uid=%s decision=skipped:disabled",
            scope,
            scope_uid,
        )
        return None

    (
        min_memory,
        concentration_threshold,
        cooldown_hours,
        confidence_floor,
        model,
    ) = await _get_scope_thresholds(scope, db)

    memory_count = len(memories)
    ratio, top3 = _topic_concentration_ratio(memories)

    logger.info(
        "skill_factory: analyze scope=%s scope_uid=%s memory_count=%s "
        "top3=%s ratio=%.3f threshold=%.3f min_memory=%s",
        scope,
        scope_uid,
        memory_count,
        top3,
        ratio,
        concentration_threshold,
        min_memory,
    )

    if memory_count < min_memory:
        logger.info(
            "skill_factory: analyze scope=%s scope_uid=%s decision=skipped:"
            "memory_count_below_min(%s<%s)",
            scope,
            scope_uid,
            memory_count,
            min_memory,
        )
        return None

    if ratio < concentration_threshold:
        logger.info(
            "skill_factory: analyze scope=%s scope_uid=%s decision=skipped:"
            "topic_concentration_below_threshold(%.3f<%.3f)",
            scope,
            scope_uid,
            ratio,
            concentration_threshold,
        )
        return None

    # signature 去重：DB 為主（取代 v1.1.7 Redis signature key）
    signature = _compute_signature(memories)
    in_cooldown = (
        await agentic_skill_suggestion_repository.find_active_signature(
            owner_user_uid=user_uid,
            scope=scope,
            scope_uid=scope_uid,
            signature=signature,
            cooldown_hours=cooldown_hours,
            db=db,
        )
    )
    if in_cooldown:
        logger.info(
            "skill_factory: analyze scope=%s scope_uid=%s decision=skipped:"
            "signature_in_cooldown(sig=%s)",
            scope,
            scope_uid,
            signature[:12],
        )
        return None

    # LLM 生成
    llm_input = _build_llm_payload(memories, scope)
    logger.info(
        "skill_factory: llm_input scope=%s scope_uid=%s model=%s payload=%s",
        scope,
        scope_uid,
        model,
        llm_input,
    )
    try:
        # v1.3.0：經 llm_metering wrapper；route 帶 scope 便於 admin SQL 拆桶
        suggestion_raw = await llm_metering.call_llm_metered(
            purpose=llm_metering.PURPOSE_SKILL_FACTORY,
            route=scope,
            session_uid=scope_uid if scope == SCOPE_SESSION else None,
            user_uid=user_uid,
            memories_payload=llm_input,
            model=model,
        )
    except AppError as exc:
        logger.warning(
            "skill_factory: llm_call_failed scope=%s scope_uid=%s detail=%s",
            scope,
            scope_uid,
            exc.detail,
        )
        await _log_event(
            {
                "ts": time.time(),
                "type": "error",
                "user_uid": user_uid,
                "scope": scope,
                "scope_uid": scope_uid,
                "signature": signature,
                "error": exc.detail,
            }
        )
        return None
    except Exception as exc:
        logger.exception(
            "skill_factory: llm_call_error scope=%s scope_uid=%s: %s",
            scope,
            scope_uid,
            exc,
        )
        return None

    logger.info(
        "skill_factory: llm_output scope=%s scope_uid=%s suggestion=%s",
        scope,
        scope_uid,
        json.dumps(suggestion_raw, ensure_ascii=False),
    )

    # 基本欄位檢查
    if not suggestion_raw.get("name") or not suggestion_raw.get("system_prompt"):
        logger.info(
            "skill_factory: analyze scope=%s scope_uid=%s decision=skipped:"
            "llm_returned_empty_suggestion",
            scope,
            scope_uid,
        )
        return None

    confidence = float(suggestion_raw.get("confidence") or 0.0)
    if confidence < confidence_floor:
        logger.info(
            "skill_factory: analyze scope=%s scope_uid=%s decision=skipped:"
            "confidence_below_floor(%.3f<%.3f)",
            scope,
            scope_uid,
            confidence,
            confidence_floor,
        )
        await _log_event(
            {
                "ts": time.time(),
                "type": "skipped_low_confidence",
                "user_uid": user_uid,
                "scope": scope,
                "scope_uid": scope_uid,
                "signature": signature,
                "confidence": confidence,
                "floor": confidence_floor,
            }
        )
        return None

    # source_memory_uids 容忍 LLM 回傳格式不齊：以 LLM 回傳 + 實際參與分析的記憶 uid 取交集
    raw_source_uids = list(suggestion_raw.get("source_memory_uids") or [])
    valid_uids = {m.get("uid") for m in memories if m.get("uid")}
    cleaned_source_uids: list[uuid.UUID] = []
    for u in raw_source_uids:
        try:
            if str(u) in valid_uids:
                cleaned_source_uids.append(uuid.UUID(str(u)))
        except (TypeError, ValueError):
            continue
    # 若 LLM 沒回有效 uid，至少帶 5 筆 top topic 的記憶 uid 作 fallback
    if not cleaned_source_uids:
        # 取 top topic 對應的前 5 筆記憶 uid
        target_topics = {t for t, _ in top3}
        for m in memories:
            topic = (m.get("topic") or "").strip()
            mem_uid = m.get("uid")
            if topic in target_topics and mem_uid:
                try:
                    cleaned_source_uids.append(uuid.UUID(str(mem_uid)))
                except (TypeError, ValueError):
                    continue
            if len(cleaned_source_uids) >= 5:
                break

    # 寫入 DB
    try:
        created = await agentic_skill_suggestion_repository.create(
            {
                "owner_user_uid": uuid.UUID(user_uid),
                "scope": scope,
                "scope_uid": uuid.UUID(scope_uid),
                "name": suggestion_raw["name"][:50],
                "description": (suggestion_raw.get("description") or "")[:200],
                "system_prompt": suggestion_raw["system_prompt"],
                "confidence": Decimal(str(round(confidence, 3))),
                "source_memory_uids": cleaned_source_uids,
                "signature": signature,
            },
            db,
        )
    except Exception as exc:
        # Partial Unique 觸發代表並發生成；safe 跳過
        logger.warning(
            "skill_factory: insert_suggestion_failed scope=%s scope_uid=%s: %s",
            scope,
            scope_uid,
            exc,
        )
        return None

    # 過渡相容：session scope 同步寫入舊 Redis 暫存路徑（7 天 TTL）
    if scope == SCOPE_SESSION:
        try:
            await _legacy_save_session_suggestion(
                user_uid=user_uid,
                session_uid=scope_uid,
                created=created,
            )
        except Exception as exc:
            logger.warning(
                "skill_factory: legacy_redis_write_failed session=%s: %s",
                scope_uid,
                exc,
            )

    await _log_event(
        {
            "ts": time.time(),
            "type": "generated_v2",
            "user_uid": user_uid,
            "scope": scope,
            "scope_uid": scope_uid,
            "session_uid": scope_uid if scope == SCOPE_SESSION else None,
            "signature": signature,
            "suggestion_uid": str(created.agentic_skill_suggestion_uid),
            "suggestion_snapshot": {
                "name": created.name,
                "description": created.description,
                "confidence": float(created.confidence),
            },
            "source_memory_uids": [str(u) for u in cleaned_source_uids],
        }
    )

    logger.info(
        "skill_factory: analyze scope=%s scope_uid=%s decision=triggered "
        "uid=%s confidence=%.3f",
        scope,
        scope_uid,
        str(created.agentic_skill_suggestion_uid),
        confidence,
    )

    return [created]


# ---------- v1.1.7 Redis 過渡寫入 ----------


async def _legacy_save_session_suggestion(
    *,
    user_uid: str,
    session_uid: str,
    created: AgenticSkillSuggestion,
) -> None:
    """過渡期把新 suggestion 同步寫入 v1.1.7 Redis 路徑，讓舊 UI 能繼續看到。

    7 天觀察期後（commit 註明）移除此 helper。
    """
    try:
        redis = get_redis()
    except RuntimeError:
        return

    raw = await redis.get(_suggestion_key(user_uid, session_uid))
    existing: list[dict] = []
    if raw:
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                existing = [d for d in data if isinstance(d, dict)]
        except json.JSONDecodeError:
            existing = []

    new_idx = len(existing)
    new_item = {
        "idx": new_idx,
        # 共享 DB suggestion_uid 便於雙讀去重
        "suggestion_uid": str(created.agentic_skill_suggestion_uid),
        "name": created.name,
        "description": created.description,
        "system_prompt": created.system_prompt,
        "confidence": float(created.confidence),
        "source_memory_uids": [str(u) for u in (created.source_memory_uids or [])],
        "status": "pending",
        "created_skill_uid": None,
        "created_at": to_taipei_iso(created.created_at) or "",
        "signature": created.signature,
    }
    updated = [*existing, new_item]
    await redis.set(
        _suggestion_key(user_uid, session_uid),
        json.dumps(updated, ensure_ascii=False),
        ex=SUGGESTION_TTL_SECONDS,
    )


async def _legacy_load_session_suggestions(
    user_uid: str, session_uid: str
) -> list[dict]:
    try:
        redis = get_redis()
    except RuntimeError:
        return []
    raw = await redis.get(_suggestion_key(user_uid, session_uid))
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [d for d in data if isinstance(d, dict)]


async def _legacy_save_raw_session_suggestions(
    user_uid: str, session_uid: str, suggestions: list[dict]
) -> None:
    try:
        redis = get_redis()
    except RuntimeError:
        return
    await redis.set(
        _suggestion_key(user_uid, session_uid),
        json.dumps(suggestions, ensure_ascii=False),
        ex=SUGGESTION_TTL_SECONDS,
    )


# ---------- API layer：v1.1.7 兼容（session 視角；DB + Redis 雙讀合併）----------


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


def _db_suggestion_to_legacy_item(
    s: AgenticSkillSuggestion, idx: int
) -> dict:
    """DB suggestion → v1.1.7 idx 介面（給 chat session 側邊欄用）。"""
    return {
        "idx": idx,
        "suggestion_uid": str(s.agentic_skill_suggestion_uid),
        "name": s.name,
        "description": s.description,
        "system_prompt": s.system_prompt,
        "confidence": float(s.confidence),
        "source_memory_uids": [str(u) for u in (s.source_memory_uids or [])],
        "status": s.status,
        "created_skill_uid": (
            str(s.created_skill_uid) if s.created_skill_uid else None
        ),
        "created_at": to_taipei_iso(s.created_at),
        "signature": s.signature,
    }


async def list_suggestions(
    user_uid: str, session_uid: str, db: AsyncSession
) -> dict:
    """v1.1.7 PoC API：列出 session 候選（DB + Redis 雙讀合併，DB 優先）。

    過渡期：v1.3.6 上線後 7 天移除 Redis 讀取路徑（commit 另開）。
    """
    await _ensure_session_owner(session_uid, user_uid, db)

    # DB（v1.3.6 主路徑）
    db_items, _ = await agentic_skill_suggestion_repository.list_by_owner(
        owner_user_uid=user_uid,
        scope=SCOPE_SESSION,
        status=None,
        page=1,
        size=100,
        db=db,
    )
    db_filtered = [
        s
        for s in db_items
        if str(s.scope_uid) == session_uid
    ]
    # 依 created_at desc 已由 repository 排序；轉 idx 介面（idx 從新到舊）
    items: list[dict] = []
    seen_signatures: set[str] = set()
    seen_uids: set[str] = set()
    for i, s in enumerate(db_filtered):
        item = _db_suggestion_to_legacy_item(s, i)
        items.append(item)
        if s.signature:
            seen_signatures.add(s.signature)
        seen_uids.add(str(s.agentic_skill_suggestion_uid))

    # Redis legacy（過渡期）
    try:
        legacy = await _legacy_load_session_suggestions(user_uid, session_uid)
    except RuntimeError:
        legacy = []

    for raw in legacy:
        sig = raw.get("signature")
        legacy_uid = raw.get("suggestion_uid")
        if legacy_uid and legacy_uid in seen_uids:
            continue
        if sig and sig in seen_signatures:
            continue
        # 補 idx
        item = {
            "idx": len(items),
            "suggestion_uid": legacy_uid,
            "name": raw.get("name") or "",
            "description": raw.get("description") or "",
            "system_prompt": raw.get("system_prompt") or "",
            "confidence": float(raw.get("confidence") or 0.0),
            "source_memory_uids": list(raw.get("source_memory_uids") or []),
            "status": raw.get("status") or "pending",
            "created_skill_uid": raw.get("created_skill_uid"),
            "created_at": raw.get("created_at"),
            "signature": sig,
        }
        items.append(item)
        if sig:
            seen_signatures.add(sig)

    # v1.1.7 Schema 不含 suggestion_uid / signature；對外保留必要欄位
    public_items = [
        {
            "idx": x["idx"],
            "name": x["name"],
            "description": x["description"],
            "system_prompt": x["system_prompt"],
            "confidence": x["confidence"],
            "source_memory_uids": x["source_memory_uids"],
            "status": x["status"],
            "created_skill_uid": x["created_skill_uid"],
            "created_at": x["created_at"],
        }
        for x in items
    ]
    return {"items": public_items}


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
    headers = Headers({"content-type": "application/zip"})
    return UploadFile(
        file=io.BytesIO(data),
        filename=filename,
        headers=headers,
    )


async def _internal_resolve_session_idx(
    user_uid: str, session_uid: str, idx: int, db: AsyncSession
) -> dict:
    """以 v1.1.7 idx 介面取對應 suggestion（DB+Redis 合併）；給 approve / reject 共用。"""
    listed = await list_suggestions(user_uid, session_uid, db)
    target = await _ensure_idx(listed["items"], idx)
    return target


async def _internal_resolve_db_suggestion_for_session(
    user_uid: str,
    session_uid: str,
    target: dict,
    db: AsyncSession,
) -> AgenticSkillSuggestion | None:
    """從 v1.1.7 idx 對應 dict 嘗試找到 DB suggestion；找不到代表只在 Redis。"""
    suggestion_uid = target.get("suggestion_uid")
    signature = target.get("signature")

    if suggestion_uid:
        try:
            return await agentic_skill_suggestion_repository.get_by_uid(
                suggestion_uid, user_uid, db
            )
        except (ValueError, TypeError):
            return None

    # 透過 signature 查 DB（雙讀過渡期：Redis 內可能有 DB 沒有的）
    if signature:
        items, _ = await agentic_skill_suggestion_repository.list_by_owner(
            owner_user_uid=user_uid,
            scope=SCOPE_SESSION,
            status=None,
            page=1,
            size=100,
            db=db,
        )
        for s in items:
            if (
                str(s.scope_uid) == session_uid
                and s.signature == signature
            ):
                return s
    return None


async def approve_suggestion(
    user_uid: str, session_uid: str, idx: int, db: AsyncSession
) -> dict:
    """v1.1.7 PoC API：approve suggestion 並建立 skill。

    本版起：DB 主寫入（status=approved + created_skill_uid），Redis 同步標記。
    """
    await _ensure_session_owner(session_uid, user_uid, db)
    target = await _internal_resolve_session_idx(
        user_uid, session_uid, idx, db
    )
    if target.get("status") in ("approved", "rejected"):
        raise AppError(
            detail=f"此候選已處理（狀態：{target.get('status')}）",
            response_code=400,
            status_code=400,
        )

    name = target["name"]
    description = target.get("description") or ""
    system_prompt = target["system_prompt"]

    skill_info = await _create_skill_from_suggestion(
        user_uid=user_uid,
        name=name,
        description=description,
        system_prompt=system_prompt,
        db=db,
    )

    # DB 主寫
    db_obj = await _internal_resolve_db_suggestion_for_session(
        user_uid, session_uid, target, db
    )
    if db_obj is not None:
        await agentic_skill_suggestion_repository.mark_approved(
            db_obj, skill_info["skill_uid"], db
        )

    # Redis 同步標記（過渡相容）
    try:
        legacy = await _legacy_load_session_suggestions(user_uid, session_uid)
        if legacy and 0 <= idx < len(legacy):
            legacy[idx]["status"] = "approved"
            legacy[idx]["created_skill_uid"] = skill_info["skill_uid"]
            await _legacy_save_raw_session_suggestions(
                user_uid, session_uid, legacy
            )
    except Exception as exc:
        logger.debug("legacy approve 標記失敗（不影響主流程）: %s", exc)

    await _log_event(
        {
            "ts": time.time(),
            "type": "approved_v2",
            "user_uid": user_uid,
            "scope": SCOPE_SESSION,
            "scope_uid": session_uid,
            "session_uid": session_uid,
            "signature": target.get("signature"),
            "idx": idx,
            "suggestion_uid": target.get("suggestion_uid"),
            "created_skill_uid": skill_info["skill_uid"],
            "suggestion_snapshot": {
                "name": name,
                "description": description,
                "confidence": target.get("confidence"),
            },
            "source_memory_uids": target.get("source_memory_uids", []),
        }
    )

    logger.info(
        "skill_factory: approved session_uid=%s idx=%s skill_uid=%s",
        session_uid,
        idx,
        skill_info["skill_uid"],
    )

    return skill_info


async def reject_suggestion(
    user_uid: str, session_uid: str, idx: int, db: AsyncSession
) -> None:
    """v1.1.7 PoC API：reject suggestion。"""
    await _ensure_session_owner(session_uid, user_uid, db)
    target = await _internal_resolve_session_idx(
        user_uid, session_uid, idx, db
    )
    if target.get("status") in ("approved", "rejected"):
        raise AppError(
            detail=f"此候選已處理（狀態：{target.get('status')}）",
            response_code=400,
            status_code=400,
        )

    db_obj = await _internal_resolve_db_suggestion_for_session(
        user_uid, session_uid, target, db
    )
    if db_obj is not None:
        await agentic_skill_suggestion_repository.mark_rejected(db_obj, db)

    try:
        legacy = await _legacy_load_session_suggestions(user_uid, session_uid)
        if legacy and 0 <= idx < len(legacy):
            legacy[idx]["status"] = "rejected"
            await _legacy_save_raw_session_suggestions(
                user_uid, session_uid, legacy
            )
    except Exception as exc:
        logger.debug("legacy reject 標記失敗（不影響主流程）: %s", exc)

    await _log_event(
        {
            "ts": time.time(),
            "type": "rejected_v2",
            "user_uid": user_uid,
            "scope": SCOPE_SESSION,
            "scope_uid": session_uid,
            "session_uid": session_uid,
            "signature": target.get("signature"),
            "idx": idx,
            "suggestion_uid": target.get("suggestion_uid"),
            "suggestion_snapshot": {
                "name": target["name"],
                "description": target.get("description") or "",
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


# ---------- 共用：建立 skill from suggestion（v1.3.6 新版 + v1.1.7 共用）----------


async def _create_skill_from_suggestion(
    *,
    user_uid: str,
    name: str,
    description: str,
    system_prompt: str,
    db: AsyncSession,
) -> dict:
    """打包 system_prompt 為 prompt.md zip → 呼叫 skill_service.upload_skill。"""
    prompt_md = (
        f"# {name}\n\n"
        f"{description}\n\n"
        f"---\n\n"
        f"{system_prompt}\n"
    )
    skill_uid = uuid.uuid4()
    zip_bytes = _build_single_file_zip("prompt.md", prompt_md)
    zip_filename = f"skill-{skill_uid}.zip"
    upload_file = _to_upload_file(zip_filename, zip_bytes)

    result = await skill_service.upload_skill(
        user_uid=user_uid,
        name=name,
        description=description,
        files=[upload_file],
        db=db,
    )
    return {
        "skill_uid": str(result.get("skill_uid")),
        "name": result.get("name") or name,
        "description": result.get("description") or description,
    }


# ---------- v1.3.6 新 API：lazy expire ----------


async def lazy_expire_old_pending(db: AsyncSession) -> int:
    """list / accept / reject API 進入時 lazy 標記過期 pending → expired。"""
    try:
        ttl_days = await system_setting_service.get_int(
            "agentic.skill_factory.suggestion_ttl_days",
            DEFAULT_SUGGESTION_TTL_DAYS,
            db,
        )
    except Exception:
        ttl_days = DEFAULT_SUGGESTION_TTL_DAYS
    cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, ttl_days))
    try:
        return await agentic_skill_suggestion_repository.mark_expired_bulk(
            cutoff, db
        )
    except Exception as exc:
        logger.warning("lazy_expire_old_pending 失敗（不影響主流程）: %s", exc)
        return 0


# ---------- Admin debug ----------


class _LogItem(TypedDict):
    id: str
    ts: str | None
    event: dict[str, object]


class _LogListResult(TypedDict):
    items: list[_LogItem]


async def list_recent_logs(
    limit: int = 50, scope: str | None = None
) -> _LogListResult:
    """讀取 agentic:skill:log stream 最近 N 筆事件。

    v1.3.6：可帶 `scope=session|project|user` filter；scope=None 代表全部。
    """
    try:
        redis = get_redis()
    except RuntimeError:
        return {"items": []}

    # 拉較大量再 filter（避免 scope filter 後不足量）
    fetch_count = max(limit * 4, limit) if scope else limit
    try:
        entries = await redis.xrevrange(LOG_STREAM_KEY, count=fetch_count)
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
        if scope is not None:
            event_scope = data.get("scope")
            if event_scope != scope:
                continue
        items.append(
            {
                "id": str(entry_id),
                "ts": fields.get("ts") if isinstance(fields, dict) else None,
                "event": data,
            }
        )
        if len(items) >= limit:
            break
    return {"items": items}


async def get_skill_factory_stats(db: AsyncSession) -> dict:
    """admin 觀察 / 閾值調校：依 scope / status 拆桶計數。

    對應 task §4-3 stats API。
    """
    from sqlalchemy import func, select

    from app.models.agentic_skill_suggestion import AgenticSkillSuggestion

    stmt = select(
        AgenticSkillSuggestion.scope,
        AgenticSkillSuggestion.status,
        func.count().label("count"),
    ).where(
        AgenticSkillSuggestion.is_deleted == False  # noqa: E712
    ).group_by(
        AgenticSkillSuggestion.scope, AgenticSkillSuggestion.status
    )
    result = await db.execute(stmt)
    rows = result.all()

    breakdown: dict[str, dict[str, int]] = {}
    for scope_val, status_val, count in rows:
        breakdown.setdefault(str(scope_val), {})[str(status_val)] = int(count)

    # 計算 approve / reject 比率（給閾值調校監控用）
    summary: dict[str, dict[str, float]] = {}
    for scope_key, status_map in breakdown.items():
        total = sum(status_map.values()) or 1
        approved = status_map.get("approved", 0)
        rejected = status_map.get("rejected", 0)
        summary[scope_key] = {
            "approve_rate": round(approved / total, 3),
            "reject_rate": round(rejected / total, 3),
        }

    return {"breakdown": breakdown, "summary": summary}
